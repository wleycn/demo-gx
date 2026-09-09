import pandas as pd

class GoldBuilder:
    @staticmethod
    def build_fact_table(df: pd.DataFrame) -> pd.DataFrame:
        """按 event_date, customer_id, event_type 聚合"""
        if "event_date" not in df.columns:
            df["event_date"] = pd.to_datetime(df["event_timestamp"]).dt.date
        fact = df.groupby(["event_date", "customer_id", "event_type"], as_index=False).agg(
            event_count=("event_id", "count"),
            total_amount=("amount", "sum"),
            avg_amount=("amount", "mean")
        )
        return fact

    @staticmethod
    def build_dimensions(df: pd.DataFrame) -> dict:
        dim_customer = df[["customer_id"]].drop_duplicates().reset_index(drop=True)
        # 添加 first_seen_date（当前可用 min event_date）
        if "event_date" in df.columns:
            first_seen = df.groupby("customer_id")["event_date"].min().reset_index()
            dim_customer = dim_customer.merge(first_seen, on="customer_id", how="left")
        # 维度表：event_type
        dim_event_type = df[["event_type"]].drop_duplicates().reset_index(drop=True)
        # 可添加category等，但当前留空
        return {"dim_customer": dim_customer, "dim_event_type": dim_event_type}

    @staticmethod
    def build_wide_table(fact_df: pd.DataFrame, dims: dict) -> pd.DataFrame:
        wide = fact_df.merge(dims["dim_customer"], on="customer_id", how="left")
        wide = wide.merge(dims["dim_event_type"], on="event_type", how="left")
        return wide

