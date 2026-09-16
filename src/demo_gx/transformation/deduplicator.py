# [AI-GENERATED] model=deepseek-flash date=2026-09-09 reviewed_by=pending
"""Deduplication module.

Removes duplicate events based on business key (``event_id``), keeping the
row with the latest ``ingestion_timestamp``.  Superseded duplicates are
returned separately for audit logging.
"""

import pandas as pd

from demo_gx.common.time_utils import parse_utc_mixed


class Deduplicator:
    """Removes duplicate records by event_id, retaining the newest row."""

    @staticmethod
    def deduplicate(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Deduplicate by event_id, keeping the latest ingestion_timestamp.

        If either ``event_id`` or ``ingestion_timestamp`` is missing from
        the DataFrame, no deduplication is performed and an empty duplicates
        DataFrame is returned.

        Args:
            df (pandas.DataFrame): Cleaned DataFrame containing at least
                ``event_id`` and ``ingestion_timestamp`` columns.

        Returns:
            tuple: A pair ``(deduplicated_df, duplicates_log_df)``.  The
            first element contains the deduplicated rows; the second
            contains the superseded duplicates for audit logging.
        """
        if "event_id" not in df.columns or "ingestion_timestamp" not in df.columns:
            return df, pd.DataFrame()
        # Ensure ingestion_timestamp is a datetime column. The parsing policy
        # lives in one place (common.time_utils), so this defensive path cannot
        # drift from the validator's own parsing.
        if not pd.api.types.is_datetime64_any_dtype(df["ingestion_timestamp"]):
            df["ingestion_timestamp"] = parse_utc_mixed(df["ingestion_timestamp"])
        # Sort by ingestion_timestamp so the last row per event_id is the newest.
        # Stable sort: on an exact timestamp tie the last-occurring input row
        # wins (documented keep-last semantics, round-2 writer QC #7).
        # Unparseable timestamps sort to the front, which keeps such a row out
        # of the winning seat: keep-last would otherwise promote the row that
        # carries no usable timestamp over the one that does.
        df_sorted = df.sort_values("ingestion_timestamp", kind="stable", na_position="first")
        # Mark duplicates (keep the last occurrence)
        duplicated_mask = df_sorted.duplicated(subset=["event_id"], keep="last")
        duplicates = df_sorted[duplicated_mask].copy()
        deduped = df_sorted[~duplicated_mask].copy()
        return deduped, duplicates
