"""Input ingestion module.

Provides a unified reader that auto-detects file format by extension and
appends an audit column (``_raw_json``) for full replayability in the
Bronze layer.
"""

import pandas as pd
from pathlib import Path
import json

from common.time_utils import parse_utc_mixed


def read_input(file_path: str) -> pd.DataFrame:
    """Read a structured input file into a DataFrame.

    Supports ``.json`` (read line-by-line with ``lines=True``), ``.csv``,
    and ``.parquet`` formats.  A ``_raw_json`` column is appended to every
    row containing the row's original JSON string, enabling audit and
    replay in the Bronze layer.

    Args:
        file_path (str): Path to the input file.  May be a string or
            ``pathlib.Path``.

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
    if suffix == ".json":
        df = pd.read_json(path, lines=True)
    elif suffix == ".csv":
        df = pd.read_csv(path)
    elif suffix == ".parquet":
        df = pd.read_parquet(path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")
    # Add the raw JSON column for audit purposes. If the input already
    # carries an internal column name (_raw_json), preserve the user column
    # under a distinct name instead of silently overwriting it
    # (dev-review: input-column collision).
    if "_raw_json" in df.columns:
        df = df.rename(columns={"_raw_json": "_raw_json_user"})
    # date_format="iso": without it, datetime columns serialize to epoch
    # milliseconds and replay silently lands in 1970 (dev-review critical)
    df["_raw_json"] = df.apply(lambda row: row.to_json(date_format="iso"), axis=1)
    return df


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
        part_dir = bronze_base / str(source) / f"dt={dt}"
        part_dir.mkdir(parents=True, exist_ok=True)
        out = group.drop(columns=["_ingestion_dt"])
        out.to_json(part_dir / "events.json", orient="records", lines=True, force_ascii=False, date_format="iso")
        written += len(group)
    return written
