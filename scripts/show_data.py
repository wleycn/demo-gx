# [AI-GENERATED] model=qianfan-code-latest date=2026-09-15 reviewed_by=pending
"""Read-only viewer for the artefacts a pipeline run produced.

What it answers
---------------
"Show me the data." Where ``check_data.py`` judges whether a run is compliant,
this tool only displays: the columns, the partitions the shown rows came from,
and the rows themselves. It is the answer to "how do I look at what landed in
the Parquet files".

Why it is a separate tool
-------------------------
Showing data and judging data are two jobs with two contracts. The verifier
must exit non-zero on a defect, because CI reads its status. A viewer must
never do that: a table that violates its contract is exactly the table someone
wants to look at. Merging them would put two output shapes and two exit
conventions in one file. The two tools share the discovery code, so they can
never disagree about where the data lives.

Streams
-------
Table format prints the whole report on stdout. With ``--format json`` or
``--format csv`` the rows go to stdout and the report moves to stderr, so a
pipe carries data and nothing else. Usage errors always go to stdout, so they
stay visible when stderr is redirected.

Exit status
-----------
* 0 - something was shown, including "no rows to show"
* 2 - the request does not match the data: unknown table, unknown column, or a
      machine format with more than one table in scope
* 3 - there is nothing to look at, because the environment has never run

There is deliberately no failure status.

Reading
-------
Files come from ``check_data.parquet_files``, so partitions are chosen before
any file is opened and a small ``--limit`` stops after the batches it needs.
Rows are read batch by batch, never as one frame (AGENTS.md section 3 red line
2: partition pruning, no full pull to the driver). No clock is read (red line
10), so the same artefacts always print the same rows: without
``--event-date``, partitions are read in name order and the report names every
partition the shown rows came from.

Requires the editable install (``make setup``), exactly like
``python -m demo_gx.cli``.
"""

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from check_data import (
    LAYERS,
    PARTITION_KEY,
    discover,
    parquet_files,
    parse_contract,
    partition_dirs,
    run_marker,
)
from demo_gx.common.config import PROJECT_ROOT, load_config

DEFAULT_LIMIT = 10
BATCH_ROWS = 256
LABEL_WIDTH = 11
INDENT = "    "

# Bronze is the only JSON Lines layer. The error tables are Parquet, the same
# layout Silver and Gold use.
JSON_LAYERS = ("bronze",)
BRONZE_GLOB = "*/dt=*/events.json"


def _cell(value: Any) -> str:
    """Render one value the way it would be typed."""

    return "" if value is None else str(value)


def _columns_of(path: Path) -> dict[str, str]:
    """Column name to physical type, from the file metadata alone."""

    schema = pq.ParquetFile(path).schema_arrow
    return {name: str(schema.field(name).type) for name in schema.names}


def _read_rows(files: list[Path], columns: list[str], limit: int) -> tuple[list[dict[str, Any]], list[Path], bool]:
    """Read at most ``limit`` rows, stopping as soon as the limit is met.

    Returns the rows, the files that were opened, and whether the limit cut the
    read short. Batches keep the peak memory flat and let a small limit stop
    after one batch instead of after the whole table.
    """

    rows: list[dict[str, Any]] = []
    opened: list[Path] = []
    for path in files:
        if len(rows) >= limit:
            return rows, opened, True
        opened.append(path)
        for batch in pq.ParquetFile(path).iter_batches(batch_size=BATCH_ROWS, columns=columns):
            for record in batch.to_pylist():
                if len(rows) >= limit:
                    return rows, opened, True
                rows.append(record)
    return rows, opened, False


def _read_lines(files: list[Path], limit: int) -> tuple[list[str], int, bool]:
    """The JSON Lines equivalent of ``_read_rows``, with the same early stop."""

    lines: list[str] = []
    opened = 0
    for path in files:
        if len(lines) >= limit:
            return lines, opened, True
        opened += 1
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            if len(lines) >= limit:
                return lines, opened, True
            lines.append(line)
    return lines, opened, False


def _json_files(layer: str, root: Path, event_date: str) -> list[Path]:
    """The text files a JSON Lines layer holds."""

    files = sorted(root.glob(BRONZE_GLOB))
    if event_date:
        files = [path for path in files if path.parent.name == f"dt={event_date}"]
    return files


def _partition_note(labels: list[str], key: str, event_date: str, note: str) -> str:
    """State which partitions exist, without claiming which ones were read."""

    if not labels:
        return note
    if event_date:
        return f"{key}, selected {key}={event_date}"
    return f"{key}, {len(labels)} partition(s) on disk; first {labels[0]}"


def _rows_note(opened: list[Path]) -> str:
    """Name the partitions the shown rows came from, and no more than that."""

    labels: list[str] = []
    for path in opened:
        label = path.parent.name if "=" in path.parent.name else "the table directory"
        if label not in labels:
            labels.append(label)
    if len(labels) == 1:
        return labels[0]
    return f"{labels[0]} .. {labels[-1]} ({len(labels)} partitions)"


def _contract_label(name: str) -> str:
    """The contract path when there is one, so the reader can jump to it."""

    contract = parse_contract(name)
    return "none" if contract is None else str(contract.path.relative_to(PROJECT_ROOT))


def _render_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    """Render rows as an aligned text table, one line per row."""

    widths = {name: max(len(name), *(len(_cell(row.get(name))) for row in rows)) for name in columns}
    lines = [
        "  ".join(name.ljust(widths[name]) for name in columns),
        "  ".join("-" * widths[name] for name in columns),
    ]
    lines.extend("  ".join(_cell(row.get(name)).ljust(widths[name]) for name in columns) for row in rows)

    # Right-trim: padding the last column leaves trailing blanks in the file
    # when the report is redirected.
    return "\n".join(INDENT + line.rstrip() for line in lines)


def _write_machine(rows: list[dict[str, Any]], columns: list[str], fmt: str) -> None:
    """Write the rows to stdout in the shape the caller asked for."""

    if fmt == "json":
        print(json.dumps(rows, default=str))
        return
    writer = csv.writer(sys.stdout)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_cell(row.get(name)) for name in columns])


def show_parquet(
    layer: str,
    name: str,
    root: Path,
    event_date: str,
    columns_arg: list[str],
    limit: int,
    schema_only: bool,
    machine: str,
    report: Any,
) -> int | None:
    """Show the columns and rows of one Parquet table.

    Returns 2 when a requested column does not exist, otherwise None.
    """

    key = PARTITION_KEY[layer]
    files = parquet_files(root, key, event_date)
    if not files:
        print(f"{INDENT}{'artefact':<{LABEL_WIDTH}}no Parquet file under {root}", file=report)
        return None

    schema = _columns_of(files[0])
    unknown = [wanted for wanted in columns_arg if wanted not in schema]
    if unknown:
        print(f"unknown column {unknown} for {layer}/{name}; available: {list(schema)}")
        return 2
    selected = columns_arg or list(schema)

    dirs = partition_dirs(root, key, event_date)
    note = "none, the files sit directly under the table directory"
    print(f"{INDENT}{'contract':<{LABEL_WIDTH}}{_contract_label(name)}", file=report)
    print(f"{INDENT}{'columns':<{LABEL_WIDTH}}" + "  ".join(f"{c}({schema[c]})" for c in selected), file=report)
    print(
        f"{INDENT}{'partition':<{LABEL_WIDTH}}" + _partition_note([d.name for d in dirs], key, event_date, note),
        file=report,
    )

    if schema_only:
        print(f"{INDENT}{'files':<{LABEL_WIDTH}}{len(files)} file(s) on disk, no rows read (--schema)", file=report)
        return None

    rows, opened, stopped = _read_rows(files, selected, limit)
    how = "stopped at the row limit" if stopped else "read to the end"
    print(f"{INDENT}{'files':<{LABEL_WIDTH}}{len(opened)} of {len(files)} file(s) read, {how}", file=report)
    if not rows:
        print(f"\n{INDENT}no rows to show", file=report)
        return None
    print(f"{INDENT}{'rows from':<{LABEL_WIDTH}}{_rows_note(opened)}", file=report)
    if machine:
        _write_machine(rows, selected, machine)
    else:
        print(file=report)
        print(_render_table(rows, selected), file=report)
    return None


def show_json(layer: str, name: str, root: Path, event_date: str, limit: int, schema_only: bool, report: Any) -> None:
    """Show the lines of one JSON Lines layer."""

    files = _json_files(layer, root, event_date)
    if not files:
        print(f"{INDENT}{'artefact':<{LABEL_WIDTH}}no JSON Lines file under {root}", file=report)
        return

    key = "dt" if layer == "bronze" else "partition"
    labels = sorted({path.parent.name for path in files if "=" in path.parent.name})
    note = "none, the lines sit directly under the layer directory"
    print(f"{INDENT}{'contract':<{LABEL_WIDTH}}none, {layer} carries no table contract", file=report)
    print(f"{INDENT}{'columns':<{LABEL_WIDTH}}not applicable, JSON Lines", file=report)
    print(f"{INDENT}{'partition':<{LABEL_WIDTH}}" + _partition_note(labels, key, event_date, note), file=report)

    if schema_only:
        print(f"{INDENT}{'files':<{LABEL_WIDTH}}{len(files)} file(s) on disk, no lines read (--schema)", file=report)
        return
    lines, opened, stopped = _read_lines(files, limit)
    how = "stopped at the row limit" if stopped else "read to the end"
    print(f"{INDENT}{'files':<{LABEL_WIDTH}}{opened} of {len(files)} file(s) read, {how}", file=report)
    if not lines:
        print(f"\n{INDENT}no lines to show", file=report)
        return
    print(file=report)
    for line in lines:
        print(INDENT + line, file=report)
    print(file=report)
    print(f"{INDENT}({name}, {len(lines)} line(s) shown)", file=report)


def main(argv: list[str] | None = None) -> int:
    """Show the selected rows. See the module docstring for the exit statuses."""

    parser = argparse.ArgumentParser(
        description="Show the rows a pipeline run produced. Read-only.",
        epilog="Exit 0 shown, 2 the request does not match the data, 3 nothing to look at.",
    )
    parser.add_argument("--env", default="dev", choices=["dev", "test", "prod"], help="Environment to inspect")
    parser.add_argument("--layer", default="all", choices=[*LAYERS, "all"], help="Layer to inspect")
    parser.add_argument("--table", default="", help="Only this table; Gold tables take the directory name")
    parser.add_argument("--event-date", default="", help="Only this partition, YYYY-MM-DD")
    parser.add_argument(
        "--limit", type=int, default=DEFAULT_LIMIT, help=f"Rows or lines to show (default {DEFAULT_LIMIT})"
    )
    parser.add_argument("--columns", default="", help="Comma-separated columns to read and show")
    parser.add_argument("--schema", action="store_true", help="Names and types only, no rows read")
    parser.add_argument("--format", default="table", choices=["table", "json", "csv"], help="Output shape")
    args = parser.parse_args(argv)

    machine = args.format if args.format in ("json", "csv") else ""
    report = sys.stderr if machine else sys.stdout
    only = args.table.strip()
    event_date = args.event_date.strip()
    columns_arg = [name.strip() for name in args.columns.split(",") if name.strip()]
    layers = list(LAYERS) if args.layer == "all" else [args.layer]

    cfg = load_config(args.env)
    suffix = f"  event_date={event_date}" if event_date else ""
    header = f"show-data  env={args.env}  layer={args.layer}  table={only or 'all'}  limit={args.limit}{suffix}"
    print(header, file=report)

    if not run_marker(cfg).is_file():
        print(f"NOTHING TO SHOW  env={args.env} has never run, so there is no output to show", file=report)
        return 3

    targets = [
        (layer, name, root) for layer in layers for name, root in discover(cfg, layer) if not only or name == only
    ]
    if only and not targets:
        print(f"no table named '{only}' exists on disk")
        return 2
    if machine and len(targets) != 1:
        print(f"--format {args.format} needs a single table in scope, found {len(targets)}; name one with --table")
        return 2
    if not targets:
        print(f"NOTHING TO SHOW  layer={args.layer} holds no table on disk", file=report)
        return 3

    for layer, name, root in targets:
        if not machine:
            print(f"\n{layer.upper()}")
            print(f"  {name}")
        if layer in JSON_LAYERS:
            show_json(layer, name, root, event_date, args.limit, args.schema, report)
            continue

        # The errors layer root is errors/, but each table lives one level
        # deeper: errors/quarantine/ and errors/duplicates/.
        table_root = root / name if layer == "errors" else root
        code = show_parquet(layer, name, table_root, event_date, columns_arg, args.limit, args.schema, machine, report)
        if code is not None:
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
