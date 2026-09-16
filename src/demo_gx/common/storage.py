# [AI-GENERATED] model=deepseek-flash date=2026-09-15 reviewed_by=pending
"""Table writes for the storage root, in one place.

Two invariants live here rather than at each call site, because the call sites
had drifted apart on both of them (code audit, 2026-09-15):

- A partition is written to a temporary file and then moved into place, so a
  crash mid-write cannot destroy the partition that was already there. A
  partition-level overwrite is only idempotent when it completes.
- A run rewrites the partitions it owns and clears the ones inside its scope
  that ended up with no rows, so "this run produced no errors for that day" is
  visible in the artefacts instead of an older run's rows surviving.

Both invariants are what make a partition-scoped overwrite idempotent
(AGENTS.md section 3 red line 1). A write that half-completes, or a partition
that outlives the absence of its rows, breaks that.
"""

import shutil
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

DATA_FILE = "data.parquet"


def partition_dir(table_root: Path, partition_col: str, value: str) -> Path:
    """Return the directory of one partition.

    Args:
        table_root (pathlib.Path): Root directory of the table.
        partition_col (str): Name of the partition column.
        value (str): Already-rendered partition value.

    Returns:
        pathlib.Path: ``<table_root>/<partition_col>=<value>``.
    """

    return table_root / f"{partition_col}={value}"


def partition_value(value: object) -> str:
    """Render a partition key.

    Calendar dates use the ISO day so a directory name does not depend on the
    frame that produced it; the quarantine table also carries the literal
    string ``unknown`` for rows whose timestamp does not parse, which is why
    this cannot assume a date.

    Args:
        value: A ``datetime.date``, ``datetime.datetime`` or plain value.

    Returns:
        str: ``YYYY-MM-DD`` for date-likes, ``str(value)`` otherwise.
    """

    fmt = getattr(value, "strftime", None)
    if callable(fmt):
        return str(fmt("%Y-%m-%d"))
    return str(value)


@contextmanager
def temp_then_replace(path: Path) -> Iterator[Path]:
    """Yield a temporary path that replaces ``path`` on success.

    A failure removes the temporary and re-raises, so a failed write leaves
    neither a half-written file nor a stray one beside it.

    Args:
        path (pathlib.Path): Final file path.

    Yields:
        pathlib.Path: The temporary path to write into.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        yield tmp
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    tmp.replace(path)


def write_one(df: pd.DataFrame, path: Path) -> None:
    """Write a DataFrame to ``path`` through a temporary file.

    Args:
        df (pandas.DataFrame): Frame to write.
        path (pathlib.Path): Final file path.
    """

    with temp_then_replace(path) as tmp:
        df.to_parquet(tmp, index=False)


def clear_partition(table_root: Path, partition_col: str, value: str) -> bool:
    """Remove one partition, and the table root once it holds no partition.

    Args:
        table_root (pathlib.Path): Root directory of the table.
        partition_col (str): Name of the partition column.
        value (str): Already-rendered partition value.

    Returns:
        bool: ``True`` when a partition directory was there to remove.
    """

    part = partition_dir(table_root, partition_col, value)
    if not part.exists():
        return False
    shutil.rmtree(part)
    if not any(table_root.glob(f"{partition_col}=*")):
        shutil.rmtree(table_root, ignore_errors=True)
    return True


def write_table(
    df: pd.DataFrame,
    table_root: Path,
    partition_col: str | None = None,
    scope: Iterable[str] | None = None,
) -> list[Path]:
    """Write a table, atomically, and drop the partitions the scope lost.

    With ``partition_col`` the frame is grouped and written as
    ``<table_root>/<partition_col>=<value>/data.parquet``; without it the frame
    is a single-file table at ``<table_root>/data.parquet``.

    ``scope`` is the set of partition values this run owns. Every value in it
    that produced no rows is cleared, and the table root goes away when it
    holds no partition at all, so a missing table reads as "no rows" rather
    than as a failure. Values outside the scope are left untouched, which is
    what keeps a scoped backfill from touching other days.

    Args:
        df (pandas.DataFrame): Frame to write.
        table_root (pathlib.Path): Root directory of the table.
        partition_col (str | None): Partition column, or ``None`` for a
            single-file table.
        scope (collections.abc.Iterable[str] | None): Partition values the run
            owns, already rendered. ``None`` clears nothing.

    Returns:
        list[pathlib.Path]: The files written.

    Raises:
        ValueError: If ``partition_col`` is not a column of ``df``.
    """

    written: list[Path] = []
    if partition_col is None:
        write_one(df, table_root / DATA_FILE)
        return [table_root / DATA_FILE]

    if partition_col not in df.columns:
        raise ValueError(f"partition column {partition_col!r} missing from the frame")

    for value, group in df.groupby(partition_col):
        rendered = partition_value(value)
        path = partition_dir(table_root, partition_col, rendered) / DATA_FILE
        write_one(group, path)
        written.append(path)

    produced = {partition_value(v) for v in df[partition_col].unique()}
    for value in scope or []:
        if value not in produced:
            clear_partition(table_root, partition_col, value)
    return written
