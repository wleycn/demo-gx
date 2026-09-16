# [AI-GENERATED] model=qianfan-code-latest date=2026-09-15 reviewed_by=pending
"""Error envelope construction and partitioned quarantine write.

Owns two things the orchestrator must not: the mapping from a validator
``error_reason`` to the coarse ``error_type``, and the on-disk shape of
``errors/quarantine/event_date=<YYYY-MM-DD|unknown>/data.parquet``.

The caller supplies the target directory and the run timestamp; neither is
read from the system clock here (see AGENTS.md section 3 red line: partition
parameters are injected by the scheduler).

The partition key is the record's own event date, derived from
``event_timestamp``. A record whose ``event_timestamp`` does not parse
goes to ``event_date=unknown``. Each partition is overwritten, so a rerun
of the same batch leaves the artefact unchanged (AGENTS.md red line 1).

Contract: INTERFACE-DESIGN.md section 4.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from demo_gx.common.storage import write_table
from demo_gx.common.time_utils import parse_utc_mixed

# Reason fragments that mark a type-coercion failure rather than a contract
# mismatch. INTERFACE-DESIGN.md section 4 is the single source for this list.
TYPE_COERCION_HINTS = ("not numeric", "not string", "parse failed")


def classify_error(reason: str) -> str:
    """Map a validator ``error_reason`` to the coarse ``error_type``.

    Args:
        reason (str): The per-row reason text produced by ``SchemaValidator``.

    Returns:
        str: ``"type_coercion_failed"`` when the reason mentions a coercion
        failure, otherwise ``"schema_mismatch"``.
    """
    return "type_coercion_failed" if any(h in reason for h in TYPE_COERCION_HINTS) else "schema_mismatch"


def _derive_event_date(invalid_df: pd.DataFrame) -> pd.Series:
    """Derive the partition key from each row's ``event_timestamp``.

    Returns a string Series: ``YYYY-MM-DD`` for parseable timestamps,
    ``"unknown"`` for unparseable ones.
    """
    if "event_timestamp" not in invalid_df.columns:
        return pd.Series(["unknown"] * len(invalid_df), index=invalid_df.index)
    # One parsing policy for the whole pipeline: parse_utc_mixed tolerates mixed
    # formats, where a plain pd.to_datetime would apply the first row's format
    # to every row and silently NaT the rest.
    parsed = parse_utc_mixed(invalid_df["event_timestamp"])
    dates = parsed.dt.strftime("%Y-%m-%d")
    dates = dates.where(parsed.notna(), "unknown")
    return dates


def build_error_envelope(
    invalid_df: pd.DataFrame,
    ingestion_timestamp: pd.Timestamp,
) -> pd.DataFrame:
    """Build the five-field error envelope for quarantined rows.

    Args:
        invalid_df (pandas.DataFrame): Rejected rows carrying ``error_reason``.
        ingestion_timestamp (pandas.Timestamp): Run timestamp to stamp into
            every envelope row.

    Returns:
        pandas.DataFrame: Columns ``original_json``, ``error_type``,
        ``error_details``, ``ingestion_timestamp``, ``event_date``.
    """
    if "_raw_json" in invalid_df.columns:
        original = invalid_df["_raw_json"].astype(str)
    else:
        original = invalid_df.apply(lambda r: r.to_json(date_format="iso"), axis=1)
    return pd.DataFrame(
        {
            "original_json": original,
            "error_type": invalid_df["error_reason"].map(classify_error),
            "error_details": invalid_df["error_reason"].str.strip(),
            "ingestion_timestamp": ingestion_timestamp.isoformat(),
            "event_date": _derive_event_date(invalid_df),
        }
    )


def write_error_envelope(
    invalid_df: pd.DataFrame,
    errors_dir: Path,
    ingestion_timestamp: pd.Timestamp,
    scope: Iterable[str] | None = None,
) -> list[Path]:
    """Write the error envelope as a partitioned Parquet table.

    Partitions are keyed by ``event_date`` (``YYYY-MM-DD`` or ``unknown``).
    Each partition directory ``event_date=<value>/data.parquet`` is overwritten,
    so a rerun replaces one day and leaves the others alone.

    ``scope`` carries the partition values the run covers. A covered day that
    produced no invalid rows is cleared, so a rerun after a fix does not leave
    the earlier run's rows behind for the verifier to report.

    Args:
        invalid_df (pandas.DataFrame): Rejected rows carrying ``error_reason``.
        errors_dir (pathlib.Path): Quarantine table root
            (``errors/quarantine``); created if absent.
        ingestion_timestamp (pandas.Timestamp): Run timestamp.
        scope (collections.abc.Iterable[str] | None): Partition values this run
            owns, already rendered. ``None`` clears nothing.

    Returns:
        list[pathlib.Path]: The written partition files, one per event date.
    """
    envelope = build_error_envelope(invalid_df, ingestion_timestamp)
    return write_table(envelope, errors_dir, partition_col="event_date", scope=scope)
