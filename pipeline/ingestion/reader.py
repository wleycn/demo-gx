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
