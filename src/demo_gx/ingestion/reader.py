# [AI-GENERATED] model=deepseek-flash date=2026-09-09 reviewed_by=Rocky
"""Input ingestion module.

Provides a unified reader that auto-detects file format by extension,
masks direct identifiers at the ingestion boundary and appends an audit column
(``_raw_json``) for full replayability in the Bronze layer.
"""

import json
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from demo_gx.common.mask import mask_columns
from demo_gx.common.storage import temp_then_replace
from demo_gx.common.time_utils import parse_utc_mixed


def read_input(file_path: str, masked_fields: Iterable[str] | None = None, pepper: str = "") -> pd.DataFrame:
    """Read a structured input file into a DataFrame.

    Supports ``.json`` (read line-by-line with ``lines=True``), ``.csv``,
    and ``.parquet`` formats.  A ``_raw_json`` column is appended to every
    row containing the row's original JSON string, enabling audit and
    replay in the Bronze layer.

    Masking happens before that audit copy is built, so the masked value is
    what Bronze, Silver, Gold, the quarantine envelopes and the logs all carry.

    Args:
        file_path (str): Path to the input file.  May be a string or
            ``pathlib.Path``.
        masked_fields (Iterable[str] | None): Columns to replace with a keyed
            digest.  Supplied by the caller from configuration.
        pepper (str): Key for the mask digest, see
            :func:`demo_gx.common.mask.mask_value`.

    Returns:
        pandas.DataFrame: The loaded data with an additional ``_raw_json``
        column.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file extension is not one of ``.json``,
            ``.csv``, or ``.parquet``.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Input file {file_path} not found")
    suffix = path.suffix.lower()
    # Records are kept for JSON input: the audit copy is built per record, and
    # a key that only some records carry has to stay missing on the others (see
    # _audit_copies). A tabular source has no per-record shape, so it yields None.
    records: list[dict] | None = None
    if suffix == ".json":
        records = _read_json_lines(path)
        df = pd.DataFrame(records)
    elif suffix == ".csv":
        df = pd.read_csv(path)
    elif suffix == ".parquet":
        df = pd.read_parquet(path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")
    # If the input already carries an internal column name (_raw_json), preserve
    # the user column under a distinct name instead of silently overwriting it
    # (dev-review: input-column collision).
    if "_raw_json" in df.columns:
        df = df.rename(columns={"_raw_json": "_raw_json_user"})
    # Mask direct identifiers before the audit copy below is built. This is the
    # ingestion boundary the table contracts name, so no clear-text identifier
    # reaches Bronze, Silver, Gold, the quarantine or the logs.
    if masked_fields:
        df = mask_columns(df, masked_fields, pepper)
    df["_raw_json"] = _audit_copies(df, records, masked_fields)
    return df


def _read_json_lines(path: Path) -> list[dict]:
    """Parse a JSON-Lines file into one record per line, in file order.

    ``records[i]`` corresponds to row ``i`` of the frame built from it, so the
    audit copy can be rebuilt from the record's own keys rather than from the
    frame's column union.

    Args:
        path (pathlib.Path): The JSON-Lines file.

    Returns:
        list[dict]: One dictionary per non-empty line.
    """
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _audit_copies(df: pd.DataFrame, records: list[dict] | None, masked_fields: Iterable[str] | None) -> list[str]:
    """Build the ``_raw_json`` audit copy for every row.

    With the source records in hand, each copy carries exactly the keys that
    record had, with the masked value substituted for each masked column. A
    frame rebuilt copy would instead give every row the union of all keys, with
    nulls where the key was never there, and strict mode could no longer tell
    "key absent" from "key present and null" — one stray key would then
    quarantine the whole batch.

    For tabular sources (CSV, Parquet) there is no per-record shape, so the copy
    is the frame row serialized. ``date_format="iso"`` keeps datetime columns as
    ISO strings; without it they serialize to epoch milliseconds and a replay
    silently lands in 1970 (dev-review critical).

    Args:
        df (pandas.DataFrame): The (already masked) frame.
        records (list[dict] | None): Source records, or ``None`` for tabular input.
        masked_fields (Iterable[str] | None): Columns whose frame value is the
            masked form.

    Returns:
        list[str]: One JSON string per row, aligned with the frame index.
    """
    if records is None:
        return list(df.apply(lambda row: row.to_json(date_format="iso"), axis=1))
    assert len(records) == len(df), "record count and frame row count diverged"
    masked = set(masked_fields or ())
    copies = []
    for position, record in enumerate(records):
        row = {}
        for key, value in record.items():
            if key in masked and key in df.columns:
                value = df[key].iloc[position]  # the masked form
                if pd.isna(value):
                    value = None  # a missing identifier stays missing, not "NaN"
            row[key] = value
        copies.append(json.dumps(row, ensure_ascii=False, default=str))
    return copies


def write_bronze(raw_df: pd.DataFrame, bronze_base: Path, run_ts: pd.Timestamp) -> int:
    """Archive raw records to the Bronze layer (JSON Lines, partitioned).

    Bronze is the immutable landing zone: **every** arrived record —
    including rows that are later quarantined at the validation gate — is
    archived here, partitioned by ``source_system`` and ingestion date, in
    the original JSON-Lines form.  No quality checks are applied at this
    stage (quality is the Silver gate's job); Bronze only preserves the raw
    facts for replay, audit, and re-processing.

    Partition layout (see ``docs/business/DATA-DESIGN.md`` section 1)::

        {bronze_base}/{source_system}/dt={YYYY-MM-DD}/events.json

    The write is partition-scoped and overwrites an existing ``events.json``
    for the same partition, keeping re-runs of the same batch idempotent
    (matching the Silver/Gold overwrite semantics in this single-machine
    demo; a production Bronze would append new files instead).

    Args:
        raw_df (pandas.DataFrame): DataFrame as read from the input file,
            containing at least ``source_system`` and
            ``ingestion_timestamp`` columns.  The ``_raw_json`` audit
            column is excluded from the archive.
        bronze_base (pathlib.Path): Root path of the Bronze layer, e.g.
            ``Path("data") / "bronze"``.
        run_ts (pandas.Timestamp): The run instant, injected by the caller.
            Used as the partition-date fallback for rows with no parseable
            ``ingestion_timestamp``, so the partition does not depend on the
            wall clock (AGENTS.md section 3 red line 10).

    Returns:
        int: The number of records actually written to disk (the caller
        should report this count in metrics rather than assuming the full
        input batch was archived).
    """
    df = raw_df.drop(columns=["_raw_json"], errors="ignore").copy()
    # Partition keys must never drop a record: Bronze archives EVERY
    # arriving row, so a missing source/ingestion timestamp falls back to a
    # dedicated partition instead of being silently lost (groupby drops NaN
    # keys by default — round-2 QC #8).
    if "source_system" in df.columns:
        df["source_system"] = df["source_system"].fillna("unknown")
    else:
        df["source_system"] = "unknown"
    run_date = run_ts.strftime("%Y-%m-%d")
    if "ingestion_timestamp" in df.columns:
        ts = parse_utc_mixed(df["ingestion_timestamp"])
        df["_ingestion_dt"] = run_date
        valid_dt = ts.notna()
        df.loc[valid_dt, "_ingestion_dt"] = ts[valid_dt].dt.strftime("%Y-%m-%d")
    else:
        df["_ingestion_dt"] = run_date
    written = 0
    for (source, dt), group in df.groupby(["source_system", "_ingestion_dt"], dropna=False):
        out = group.drop(columns=["_ingestion_dt"])
        # Same temporary-then-replace as every other table write: a crash must
        # not truncate the archive that is already on disk.
        with temp_then_replace(bronze_base / str(source) / f"dt={dt}" / "events.json") as target:
            out.to_json(target, orient="records", lines=True, force_ascii=False, date_format="iso")
        written += len(group)
    return written
