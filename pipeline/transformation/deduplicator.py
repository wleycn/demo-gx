"""Deduplication module.

Removes duplicate events based on business key (``event_id``), keeping the
row with the latest ``ingestion_timestamp``.  Superseded duplicates are
returned separately for audit logging.
"""

import pandas as pd


class Deduplicator:
    """Removes duplicate records by event_id, retaining the newest row."""

    @staticmethod
    def deduplicate(df: pd.DataFrame) -> tuple:
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
        # Ensure ingestion_timestamp is a datetime column
        if not pd.api.types.is_datetime64_any_dtype(df["ingestion_timestamp"]):
            df["ingestion_timestamp"] = pd.to_datetime(df["ingestion_timestamp"], utc=True, errors="coerce")
        # Sort by ingestion_timestamp so the last row per event_id is the newest.
        # Stable sort: on an exact timestamp tie the last-occurring input row
        # wins (documented keep-last semantics, round-2 writer QC #7)
        df_sorted = df.sort_values("ingestion_timestamp", kind="stable")
        # Mark duplicates (keep the last occurrence)
        duplicated_mask = df_sorted.duplicated(subset=["event_id"], keep="last")
        duplicates = df_sorted[duplicated_mask].copy()
        deduped = df_sorted[~duplicated_mask].copy()
        return deduped, duplicates
