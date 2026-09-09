import pandas as pd

class Deduplicator:
    @staticmethod
    def deduplicate(df: pd.DataFrame) -> tuple:
        """
        按 event_id 去重，保留 ingestion_timestamp 最新的行。
        返回 (deduplicated_df, duplicates_log_df)
        """
        if "event_id" not in df.columns or "ingestion_timestamp" not in df.columns:
            return df, pd.DataFrame()
        # 确保 ingestion_timestamp 是 datetime
        if not pd.api.types.is_datetime64_any_dtype(df["ingestion_timestamp"]):
            df["ingestion_timestamp"] = pd.to_datetime(df["ingestion_timestamp"], utc=True, errors="coerce")
        # 按 event_id 排序，保留最后一条（最新）
        df_sorted = df.sort_values("ingestion_timestamp")
        # 标记重复
        duplicated_mask = df_sorted.duplicated(subset=["event_id"], keep="last")
        duplicates = df_sorted[duplicated_mask].copy()
        deduped = df_sorted[~duplicated_mask].copy()
        return deduped, duplicates

