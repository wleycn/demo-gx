# [AI-GENERATED] model=qianfan-code-latest date=2026-09-15 reviewed_by=pending
"""Read-only verifier for the artefacts a pipeline run produced.

What it answers
---------------
"What did the last run write, and does it match the table contract?" It
discovers what exists on disk, pairs each table with its contract under
``docs/tables/``, and prints one block per table.

How the layer and the table are chosen
-------------------------------------
The **layer is a parameter**: ``--layer all|bronze|silver|gold|errors``.
Layers are structural, so they are listed here. Each layer root is built from
the environment config and never from a path literal (AGENTS.md section 3 red
line 5): ``storage.output_root`` plus that layer's ``*_subpath``.

The **table is discovered, never listed here**. Under Gold every
sub-directory is one table, so a table added to the pipeline is checked
without editing this file. Silver holds a single dataset and Bronze a single
raw archive, so those layers report one block each. Contracts are paired in
both directions: a contract under ``docs/tables/`` with nothing on disk is
reported too.

Checks per layer
----------------
Every layer: artefact presence, file and partition counts, row counts.
Parquet layers add column parity against the contract field list, logical type
parity, the declared partition key, business primary key uniqueness, and a mask
check for every field named in ``pii.masked_fields``. Bronze adds a
JSON-per-line parse. The quarantine layer reports the envelope record count and
the ``error_type`` split.

Deliberate limits
-----------------
* Read-only: nothing under ``data/`` is written, moved or deleted.
* Counts and partition lists come from Parquet footers. Row-level checks read
  only the columns they need, one partition at a time, and ``--event-date``
  narrows them to a single partition.
* No clock is read, so two runs over unchanged artefacts print the same report
  (AGENTS.md section 3 red line 10).
* Contract prose is never treated as a machine claim. Volume statements such as
  "about 16 KB per partition" stay human-read; the report prints the measured
  value beside it.

Requires the editable install (``make setup``), exactly like
``python -m demo_gx.cli``.
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from demo_gx.common.config import PROJECT_ROOT, load_config

LAYERS = ("bronze", "silver", "gold", "errors")

# Each of these layers holds one dataset. Silver's name is its contract file
# name; Bronze has no contract, so its name is a label.
SINGLE_TABLE = {"silver": "silver_events", "bronze": "bronze_events"}

# The errors layer holds two partitioned Parquet tables.
ERRORS_TABLES = ("quarantine", "duplicates")
PARTITION_KEY = {"bronze": "dt", "silver": "event_date", "gold": "event_date", "errors": "event_date"}

FIELD_ROW_RX = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*([^|]+?)\s*\|", re.M)
BACKTICK_RX = re.compile(r"`([^`]+)`")
PARTITION_RX = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)=\{")
MASK_RX = re.compile(r"^h_[0-9a-f]{16}$")
NON_PARTITIONED_RX = re.compile(r"^\s*None\b")

# A contract states a logical type; Parquet stores a physical one. Only the
# variants inside one set are accepted, so a real type drift still fails.
TYPE_EQUIV = {
    "string": {"string", "large_string"},
    "date": {"date32[day]", "date64[ms]"},
    "bigint": {"int64"},
    "int": {"int64", "int32"},
    "double": {"double", "float64"},
    "boolean": {"bool", "boolean"},
    "timestamp (us, utc)": {"timestamp[us, tz=UTC]"},
    "timestamp (us)": {"timestamp[us]"},
}

OK, WARN, FAIL = "ok", "warn", "fail"
LABEL_WIDTH = 14

# Counters a run writes into metrics.json, in the order they are reported.
RUN_METRIC_KEYS = (
    "input_rows",
    "bronze_rows",
    "valid_rows",
    "invalid_rows",
    "duplicates_removed",
    "silver_rows",
    "gold_rows",
)


@dataclass
class Contract:
    """The machine-readable part of one ``docs/tables/{table}.md`` file."""

    name: str
    path: Path
    fields: list[tuple[str, str]]
    primary_key: list[str]
    partition_key: str | None
    partition_readable: bool


@dataclass
class Finding:
    """One check result. ``label`` is the left column of the report."""

    label: str
    status: str
    detail: str


def _section(text: str, title: str) -> str:
    """Return the body of a level-two section, or an empty string."""

    match = re.search(rf"^## {re.escape(title)}\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    return match.group(1) if match else ""


def parse_contract(table: str) -> Contract | None:
    """Read the field list, primary key and partition key from a contract."""

    path = PROJECT_ROOT / "docs" / "tables" / f"{table}.md"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    fields = [(name, kind.strip().lower()) for name, kind in FIELD_ROW_RX.findall(_section(text, "Field List"))]

    pk_text = _section(text, "Business Primary Key")
    primary_key = [] if pk_text.strip().lower().startswith("not applicable") else BACKTICK_RX.findall(pk_text)

    partition_text = _section(text, "Partition")
    key_match = PARTITION_RX.search(partition_text)
    non_partitioned = bool(NON_PARTITIONED_RX.match(partition_text.strip()))
    return Contract(
        name=table,
        path=path,
        fields=fields,
        primary_key=primary_key,
        partition_key=key_match.group(1) if key_match else None,
        partition_readable=bool(key_match) or non_partitioned,
    )


def resolve_path(value: str) -> Path:
    """Resolve a configured path.

    Relative values are anchored at the project root, so the report describes
    the same tree whatever directory the verifier was started from.
    """

    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def partition_dirs(root: Path, key: str, event_date: str | None) -> list[Path]:
    """Return the hive-style ``key=value`` directories under ``root``."""

    dirs = sorted(p for p in root.glob(f"{key}=*") if p.is_dir())
    if event_date:
        dirs = [p for p in dirs if p.name == f"{key}={event_date}"]
    return dirs


def parquet_files(root: Path, key: str, event_date: str | None) -> list[Path]:
    """The Parquet files to read, resolved from the on-disk layout.

    A partitioned table holds one ``data.parquet`` inside each partition
    directory, so choosing the directories is what prunes the read. A snapshot
    table holds bare ``*.parquet`` files instead. Both shapes are resolved here
    and nowhere else: the verifier and the viewer must never disagree about
    where the data lives.
    """

    dirs = partition_dirs(root, key, event_date)
    files = sorted(path / "data.parquet" for path in dirs if (path / "data.parquet").is_file())
    if files:
        return files
    return sorted(path for path in root.glob("*.parquet") if path.stat().st_size)


def _schema_of(files: list[Path]) -> dict[str, str]:
    """Column name to physical type, taken from the first file."""

    schema = pq.ParquetFile(files[0]).schema_arrow
    return {name: str(schema.field(name).type) for name in schema.names}


def _read_columns(files: list[Path], columns: list[str]) -> list[pa.Table]:
    """Read only the named columns, one file at a time.

    Column projection plus per-file reads stay inside the partition-pruning
    rule (AGENTS.md section 3 red line 2): no full-width read, and no
    whole-table frame is built. ``--event-date`` narrows it to one partition.
    """

    return [pq.read_table(path, columns=columns) for path in files]


def _check_fields(contract: Contract, actual: dict[str, str]) -> Finding:
    """Compare column names and logical types against the contract."""

    declared = [name for name, _ in contract.fields]
    missing = [name for name in declared if name not in actual]
    extra = [name for name in actual if name not in declared]
    if missing or extra:
        parts = []
        if missing:
            parts.append(f"missing {missing}")
        if extra:
            parts.append(f"undeclared {extra}")
        return Finding("columns", FAIL, f"{len(declared)} declared / {len(actual)} found; " + "; ".join(parts))

    mismatched = []
    for name, kind in contract.fields:
        allowed = TYPE_EQUIV.get(kind)
        if allowed is None:
            mismatched.append(f"{name}: contract type '{kind}' is not in the type map")
        elif actual[name] not in allowed:
            mismatched.append(f"{name}: {actual[name]} not in {sorted(allowed)}")
    if mismatched:
        return Finding("types", FAIL, "; ".join(mismatched))
    return Finding("columns", OK, f"{len(declared)} names and types match the contract")


def _check_primary_key(files: list[Path], key: list[str], actual: dict[str, str]) -> Finding:
    """Assert the business primary key is unique across the whole table."""

    absent = [name for name in key if name not in actual]
    if absent:
        return Finding("primary key", FAIL, f"contract key column(s) {absent} are absent from the artefact")

    seen: set[tuple[Any, ...]] = set()
    rows = 0
    duplicates = 0
    for table in _read_columns(files, key):
        columns = [table.column(name).to_pylist() for name in key]
        for values in zip(*columns, strict=True):
            rows += 1
            if values in seen:
                duplicates += 1
            else:
                seen.add(values)
    shown = "(" + ", ".join(key) + ")"
    if duplicates:
        return Finding("primary key", FAIL, f"{shown} has {duplicates} duplicate row(s) over {rows}")
    return Finding("primary key", OK, f"{shown} unique over {rows} rows")


def _check_masked(files: list[Path], fields: list[str]) -> Finding:
    """Every value of a configured PII field must be a keyed digest."""

    leaked: list[str] = []
    distinct = 0
    for table in _read_columns(files, fields):
        for name in fields:
            values = set(table.column(name).to_pylist())
            distinct += len(values)

            # A missing identifier is not a leak: the mask leaves nulls alone
            # (see mask.mask_columns), so there is nothing to match.
            leaked.extend(v for v in values if v is not None and (not isinstance(v, str) or not MASK_RX.match(v)))
    if leaked:
        return Finding("pii", FAIL, f"{len(leaked)} value(s) of {fields} are not masked, e.g. {leaked[:3]}")
    return Finding("pii", OK, f"{fields} all masked, {distinct} distinct values of the form h_ + 16 hex")


def _check_currency_corrections(files: list[Path], rows: int) -> Finding:
    """Report how many amounts had an invalid currency code replaced.

    The cleaner substitutes ``USD`` for a code that fails the contract's
    pattern and flags the row in ``_is_invalid_currency``; the contract
    documents that flag (`docs/tables/silver_events.md`). Nothing reported it,
    so the substitution was invisible. No threshold is invented here: the count
    and its share are the fact the flag exists for.
    """

    corrected = 0
    for table in _read_columns(files, ["_is_invalid_currency"]):
        corrected += sum(1 for value in table.column("_is_invalid_currency").to_pylist() if value)
    share = f", {corrected * 100 / rows:.1f}% of rows" if rows else ""
    return Finding("currency", OK, f"{corrected} row(s) had an invalid code{share}; corrected to USD and flagged")


def check_parquet_table(
    root: Path, contract: Contract | None, masked: list[str], event_date: str | None
) -> list[Finding]:
    """Checks for a partitioned Parquet table or a single-file snapshot."""

    key = PARTITION_KEY["gold"]
    dirs = partition_dirs(root, key, event_date)
    files = parquet_files(root, key, event_date)
    if not files:
        return [Finding("artefact", FAIL, f"no Parquet file under {root}")]

    findings = [Finding("files", OK, f"{len(files)} file(s)")]
    rows = sum(pq.ParquetFile(path).metadata.num_rows for path in files)
    if dirs:
        per_partition = [pq.ParquetFile(path / "data.parquet").metadata.num_rows for path in dirs]
        spread = f"{min(per_partition)}..{max(per_partition)} rows each"
        findings.append(Finding("rows", OK, f"{rows} rows over {len(dirs)} partitions, {spread}"))
    else:
        findings.append(Finding("rows", OK, f"{rows} rows in a single snapshot file"))

    if contract is None:
        findings.append(Finding("contract", WARN, "no docs/tables document, structural checks only"))
        return findings

    findings.append(Finding("contract", OK, str(contract.path.relative_to(PROJECT_ROOT))))
    actual = _schema_of(files)
    findings.append(_check_fields(contract, actual))

    if dirs and contract.partition_key == key:
        findings.append(Finding("partition", OK, f"{key}, {len(dirs)} partitions"))
    elif dirs:
        detail = f"contract declares no partition, found {len(dirs)} {key} directories"
        findings.append(Finding("partition", FAIL, detail))
    elif contract.partition_key:
        detail = f"contract declares {contract.partition_key}, found no partition directory"
        findings.append(Finding("partition", FAIL, detail))
    elif contract.partition_readable:
        findings.append(Finding("partition", OK, "none, as declared"))
    else:
        findings.append(Finding("partition", WARN, "contract partition section is not machine-readable"))

    if contract.primary_key:
        findings.append(_check_primary_key(files, contract.primary_key, actual))
    else:
        findings.append(Finding("primary key", WARN, "contract declares no primary key"))

    if "_is_invalid_currency" in actual:
        findings.append(_check_currency_corrections(files, rows))

    present = [name for name in masked if name in actual]
    if present:
        findings.append(_check_masked(files, present))
    elif masked:
        findings.append(Finding("pii", OK, f"none of {masked} is a column here"))
    return findings


def check_bronze(root: Path, masked: list[str], event_date: str | None) -> list[Finding]:
    """Checks for the raw archive: JSON Lines, partitioned by source and date."""

    files = sorted(root.glob("*/dt=*/events.json"))
    if event_date:
        files = [path for path in files if path.parent.name == f"dt={event_date}"]
    if not files:
        return [Finding("artefact", FAIL, f"no events.json under {root}")]

    sources = sorted({path.parent.parent.name for path in files})
    lines = 0
    broken: list[str] = []
    leaked: set[str] = set()
    for path in files:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            lines += 1
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                broken.append(f"{path.name}:{number} {exc.msg}")
                continue
            for name in masked:
                value = record.get(name)
                if value is not None and (not isinstance(value, str) or not MASK_RX.match(value)):
                    leaked.add(str(value))

    findings = [
        Finding("files", OK, f"{len(files)} file(s) over {len(sources)} source systems: {sources}"),
        Finding("rows", OK, f"{lines} JSON Lines records"),
    ]
    if broken:
        findings.append(Finding("json", FAIL, f"{len(broken)} unparseable line(s), e.g. {broken[:2]}"))
    else:
        findings.append(Finding("json", OK, "every line parses"))
    if masked:
        if leaked:
            detail = f"{len(leaked)} plaintext value(s) of {masked}, e.g. {sorted(leaked)[:3]}"
            findings.append(Finding("pii", FAIL, detail))
        else:
            findings.append(Finding("pii", OK, f"{masked} masked in the archive"))
    findings.append(Finding("contract", OK, "none by design, Bronze carries no table contract"))
    return findings


def check_quarantine(root: Path, event_date: str | None, table_name: str) -> list[Finding]:
    """Checks one of the two error tables: the quarantine, or the duplicates.

    Both are partitioned Parquet tables under ``errors/``, partitioned by
    ``event_date``. With ``event_date`` the check scopes to one partition.
    """

    table_root = root / table_name
    key = PARTITION_KEY["errors"]
    dirs = partition_dirs(table_root, key, event_date)
    files = parquet_files(table_root, key, event_date)
    if not files:
        # An absent error table means the run found nothing to put in it: the
        # pipeline clears the days a run covers that produced no errors, so "no
        # file" reads as "no records". Reporting it as a failure would make the
        # cleanest possible run — nothing rejected, nothing duplicated — the one
        # that fails, and a false red teaches the reader to ignore this tool.
        scope = f" for event_date={event_date}" if event_date else ""
        findings = [Finding(table_name, OK, f"no records{scope}; no table under {table_root}")]
        if table_name == "quarantine":
            findings.append(Finding("error types", OK, "none"))
        return findings
    rows = sum(pq.ParquetFile(path).metadata.num_rows for path in files)
    if dirs:
        spread = [pq.ParquetFile(path / "data.parquet").metadata.num_rows for path in dirs]
        findings = [
            Finding(
                table_name,
                OK,
                f"{rows} records over {len(dirs)} partition(s), {min(spread)}..{max(spread)} rows each",
            )
        ]
    else:
        findings = [Finding(table_name, OK, f"{rows} records in a single file")]

    if table_name == "quarantine":
        # Report the error_type breakdown for the quarantine table.
        kinds: dict[str, int] = {}
        for path in files:
            table = pq.read_table(path, columns=["error_type"])
            for value in table.column("error_type").to_pylist():
                name = str(value)
                kinds[name] = kinds.get(name, 0) + 1
        findings.append(
            Finding(
                "error types",
                OK,
                ", ".join(f"{name}={count}" for name, count in sorted(kinds.items())) or "none",
            )
        )
    return findings


def discover(cfg: dict[str, Any], layer: str) -> list[tuple[str, Path]]:
    """Return the ``(table, root)`` pairs a layer holds right now.

    Gold is read off the filesystem, so a table added to the pipeline needs no
    edit here.
    """

    storage = cfg["storage"]
    output = resolve_path(storage["output_root"])
    if layer == "gold":
        root = output / storage["gold_subpath"]
        if not root.is_dir():
            return []
        return [(path.name, path) for path in sorted(root.iterdir()) if path.is_dir()]
    if layer == "silver":
        return [(SINGLE_TABLE["silver"], output / storage["silver_subpath"])]
    if layer == "bronze":
        return [(SINGLE_TABLE["bronze"], output / storage["bronze_subpath"])]

    # The errors layer holds two partitioned Parquet tables.
    errors_root = output / storage["errors_subpath"]
    return [(name, errors_root) for name in ERRORS_TABLES]


def missing_tables(cfg: dict[str, Any]) -> list[str]:
    """Contracts that name a table with no artefact on disk.

    A run is expected to write every table its contract describes, so this is a
    failure once the environment has run.
    """

    gold_root = resolve_path(cfg["storage"]["output_root"]) / cfg["storage"]["gold_subpath"]
    on_disk = {path.name for path in gold_root.iterdir() if path.is_dir()} if gold_root.is_dir() else set()
    declared = {path.stem for path in (PROJECT_ROOT / "docs" / "tables").glob("*.md")}

    # quarantine and duplicates live under errors/, not Gold.
    return sorted(declared - on_disk - {SINGLE_TABLE["silver"]} - set(ERRORS_TABLES))


def run_marker(cfg: dict[str, Any]) -> Path:
    """The file a completed run always leaves behind.

    Its absence means the environment has never run, which is a skip rather
    than a failure. Reporting an unrun environment as broken would be a false
    red, and a false red teaches the reader to ignore the tool.
    """

    return resolve_path(cfg["metrics"]["output_file"])


def report_run(cfg: dict[str, Any]) -> None:
    """Print the run envelope: where the input came from and what metrics say."""

    storage = cfg["storage"]
    metrics_file = resolve_path(cfg["metrics"]["output_file"])
    if metrics_file.is_file():
        data = json.loads(metrics_file.read_text(encoding="utf-8"))
        print("  metrics   " + "  ".join(f"{key}={data.get(key)}" for key in RUN_METRIC_KEYS if key in data))
    else:
        print(f"  metrics   not found: {metrics_file.relative_to(PROJECT_ROOT)}")
    print(f"  input     {resolve_path(storage['input_root'])}")


def main(argv: list[str] | None = None) -> int:
    """Run the verifier over the selected layers and tables."""

    parser = argparse.ArgumentParser(description="Verify the artefacts a pipeline run produced. Read-only.")
    parser.add_argument("--env", default="dev", choices=["dev", "test", "prod"], help="Environment to inspect")
    parser.add_argument("--layer", default="all", choices=[*LAYERS, "all"], help="Layer to inspect")
    parser.add_argument("--table", default="", help="Only this table; Gold tables take the directory name")
    parser.add_argument("--event-date", default="", help="Only this partition, YYYY-MM-DD")
    args = parser.parse_args(argv)

    cfg = load_config(args.env)
    masked = list(cfg.get("pii", {}).get("masked_fields", []))
    wanted = list(LAYERS) if args.layer == "all" else [args.layer]
    only = args.table.strip()
    event_date = args.event_date.strip() or None

    suffix = f"  event_date={event_date}" if event_date else ""
    print(f"check-data  env={args.env}  layer={args.layer}  table={only or 'all'}{suffix}")
    report_run(cfg)
    if not run_marker(cfg).is_file():
        print(f"\nNOT SCANNED  env={args.env} has never run, so there is no output to check")
        return 3

    checked = 0
    matched = False
    failures: list[str] = []
    warnings: list[str] = []
    for layer in wanted:
        pairs = discover(cfg, layer)
        if only:
            pairs = [(name, root) for name, root in pairs if name == only]
        matched = matched or bool(pairs)
        print(f"\n{layer.upper()}")
        if not pairs:
            print(f"  nothing on disk{f' named {only}' if only else ''}")
            continue
        for name, root in pairs:
            checked += 1
            findings: list[Finding]
            try:
                if layer == "bronze":
                    findings = check_bronze(root, masked, event_date)
                elif layer == "errors":
                    findings = check_quarantine(root, event_date, name)
                else:
                    findings = check_parquet_table(root, parse_contract(name), masked, event_date)
            except Exception as exc:  # noqa: BLE001 - one broken table must not hide the others
                findings = [Finding("error", FAIL, f"{type(exc).__name__}: {exc}")]
            if any(finding.status == FAIL for finding in findings):
                worst = FAIL
            elif any(finding.status == WARN for finding in findings):
                worst = WARN
            else:
                worst = OK
            print(f"  {name}  [{worst.upper()}]")
            for finding in findings:
                print(f"    {finding.label:<{LABEL_WIDTH}}{finding.detail}")
            if worst == FAIL:
                failures.append(f"{layer}/{name}")
            elif worst == WARN:
                warnings.append(f"{layer}/{name}")

    if only and not matched:
        print(f"\nno table named '{only}' exists on disk")
        return 2
    if "gold" in wanted and not only:
        # The run reached this point, so every table its contract describes
        # should be on disk. A contract with no table is a failure.
        for name in missing_tables(cfg):
            failures.append(f"gold/{name}")
            print(f"  FAIL  gold/{name}: docs/tables/{name}.md declares it, nothing on disk")
    if checked == 0 and not failures:
        # Zero scanned objects is not a pass: a run that inspected nothing must
        # never look like a run that inspected everything (gate-design skill).
        print(f"\nNOT SCANNED  no artefact found for env={args.env} layer={args.layer}")
        return 3

    print(f"\nSUMMARY  {checked} table(s) checked  |  {len(failures)} FAIL  {len(warnings)} WARN")
    if failures:
        print("  FAIL: " + ", ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
