import pandas as pd
from datetime import datetime

class DataCleaner:
    @staticmethod
    def standardize_timestamps(df: pd.DataFrame) -> pd.DataFrame:
        """转换 event_timestamp 和 ingestion_timestamp 为 UTC，失败时生成 _raw_* 列"""
        for col in ["event_timestamp", "ingestion_timestamp"]:
            if col in df.columns:
                # 备份原始字符串
                df[f"_raw_{col}"] = df[col].astype(str)
                try:
                    dt_series = pd.to_datetime(df[col], utc=True, errors="coerce")
                except:
                    dt_series = pd.Series([pd.NaT] * len(df), index=df.index)
                # 标记转换失败
                failed = df[col].notna() & dt_series.isna()
                df["_validation_status"] = df.get("_validation_status", "passed")
                df.loc[failed, "_validation_status"] = "type_mismatch"
                df[col] = dt_series
        return df

    @staticmethod
    def normalize_currency(df: pd.DataFrame) -> pd.DataFrame:
        """currency 转为大写，非法值修正为 USD 并标记"""
        if "currency" in df.columns:
            df["currency"] = df["currency"].astype(str).str.upper()
            valid_currencies = {"USD", "EUR", "GBP", "CNY", "JPY"}
            df["_is_invalid_currency"] = ~df["currency"].isin(valid_currencies)
            df.loc[df["_is_invalid_currency"], "currency"] = "USD"
        return df

    @staticmethod
    def check_amount(df: pd.DataFrame) -> pd.DataFrame:
        """确保 amount >= 0，负值标记为异常"""
        if "amount" in df.columns:
            # 转为数值
            df["_raw_amount"] = df["amount"]
            try:
                df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
            except:
                df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
            # 标记负数
            negative = df["amount"] < 0
            df.loc[negative, "_validation_status"] = df.get("_validation_status", "passed")
            df.loc[negative, "_validation_status"] = "type_mismatch"
            # 负数置为 0？或保留？我们保留负值但标记，由下游决定
            # 但为了符合设计（amount ≥ 0），我们可将负值设为 0 并标记？
            # 设计文档要求隔离，但我们这里只标记，让curation层决定？为简化，我们置为 NaN 并隔离？
            # 但根据错误处理策略，金额负数应隔离（在validator中已做 minimum 检查）
            # 所以此处不再处理，已由validator处理。
            pass
        return df
