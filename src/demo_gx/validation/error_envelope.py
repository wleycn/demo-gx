# [AI-GENERATED] model=deepseek-flash date=2026-09-14 reviewed_by=pending
"""Error envelope construction and quarantine write for schema validation failures.

Owns two things the orchestrator must not: the mapping from a validator
``error_reason`` to the coarse ``error_type``, and the on-disk shape of
``errors/bad_schema/{timestamp}_errors.json``.

The caller supplies the target directory and the run timestamp; neither is
read from the system clock here (see AGENTS.md section 3 red line: partition
parameters are injected by the scheduler).

Contract: INTERFACE-DESIGN.md section 4.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

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


def build_error_envelope(
    invalid_df: pd.DataFrame,
    ingestion_timestamp: pd.Timestamp,
) -> pd.DataFrame:
    """Build the four-field error envelope for quarantined rows.

    Args:
        invalid_df (pandas.DataFrame): Rejected rows carrying ``error_reason``.
        ingestion_timestamp (pandas.Timestamp): Run timestamp to stamp into
            every envelope row.

    Returns:
        pandas.DataFrame: Columns ``original_json``, ``error_type``,
        ``error_details``, ``ingestion_timestamp``.
    """
    if "_raw_json" in invalid_df.columns:
        original = invalid_df["_raw_json"].astype(str)
    else:
        original = invalid_df.apply(lambda r: r.to_json(date_format="iso"), axis=1)
    return pd.DataFrame({
        "original_json": original,
        "error_type": invalid_df["error_reason"].map(classify_error),
        "error_details": invalid_df["error_reason"].str.strip(),
        "ingestion_timestamp": ingestion_timestamp.isoformat(),
    })


def write_error_envelope(
    invalid_df: pd.DataFrame,
    errors_dir: Path,
    ingestion_timestamp: pd.Timestamp,
) -> Path:
    """Write the error envelope to ``errors_dir`` as JSON Lines.

    The filename stamp is made filesystem-safe because ``isoformat`` contains
    ``:`` and ``+``, which are illegal in Windows paths. The envelope body
    still carries the full ISO stamp.

    Args:
        invalid_df (pandas.DataFrame): Rejected rows carrying ``error_reason``.
        errors_dir (pathlib.Path): Quarantine directory; created if absent.
        ingestion_timestamp (pandas.Timestamp): Run timestamp.

    Returns:
        pathlib.Path: The written file.
    """
    errors_dir.mkdir(parents=True, exist_ok=True)
    stamp = ingestion_timestamp.strftime("%Y%m%dT%H%M%S%fZ")
    path = errors_dir / f"{stamp}_errors.json"
    build_error_envelope(invalid_df, ingestion_timestamp).to_json(
        path, orient="records", lines=True, force_ascii=False, date_format="iso"
    )
    return path
