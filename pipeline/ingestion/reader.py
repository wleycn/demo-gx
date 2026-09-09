"""Input ingestion module.

Provides a unified reader that auto-detects file format by extension and
appends an audit column (``_raw_json``) for full replayability in the
Bronze layer.
"""

import pandas as pd
from pathlib import Path
import json


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
    # Add the raw JSON column for audit purposes
    # Note: for each DataFrame row, convert the row to a JSON string
    df["_raw_json"] = df.apply(lambda row: row.to_json(), axis=1)
    return df


def write_bronze(raw_df: pd.DataFrame, bronze_base: Path) -> None:
    """Archive raw records to the Bronze layer (JSON Lines, partitioned).

    Bronze is the immutable landing zone: **every** arrived record —
    including rows that are later quarantined at the validation gate — is
    archived here, partitioned by ``source_system`` and ingestion date, in
    the original JSON-Lines form.  No quality checks are applied at this
    stage (quality is the Silver gate's job); Bronze only preserves the raw
    facts for replay, audit, and re-processing.

    Partition layout (see ``docs/data-design.md`` §1)::

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
    """
    df = raw_df.drop(columns=["_raw_json"], errors="ignore").copy()
    # Derive the ingestion date partition from the ISO-8601 prefix
    if "ingestion_timestamp" in df.columns:
        df["_ingestion_dt"] = df["ingestion_timestamp"].astype(str).str[:10]
    else:
        df["_ingestion_dt"] = pd.Timestamp.now(tz="UTC").date().isoformat()
    if "source_system" not in df.columns:
        df["source_system"] = "unknown"
    for (source, dt), group in df.groupby(["source_system", "_ingestion_dt"]):
        part_dir = bronze_base / str(source) / f"dt={dt}"
        part_dir.mkdir(parents=True, exist_ok=True)
        out = group.drop(columns=["_ingestion_dt"])
        out.to_json(part_dir / "events.json", orient="records", lines=True, force_ascii=False)
