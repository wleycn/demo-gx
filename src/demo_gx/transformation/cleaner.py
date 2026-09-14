# [AI-GENERATED] model=deepseek-flash date=2026-09-09 reviewed_by=pending
"""Data cleaning and normalization module.

Provides transformations that standardize timestamps, normalize currency
codes, and flag anomalous amount values.  All transformations add metadata
columns (prefixed with ``_``) rather than silently overwriting data.
"""

import pandas as pd
from datetime import datetime

from demo_gx.common.time_utils import parse_utc_mixed


class DataCleaner:
    """Performs timestamp, currency, and amount cleaning on validated data."""

    @staticmethod
    def standardize_timestamps(df: pd.DataFrame) -> pd.DataFrame:
        """Convert event_timestamp and ingestion_timestamp columns to UTC.

        The validator has already parsed these columns to UTC datetimes and
        backed up the raw string into ``_raw_<column>``; this method only
        fills a missing backup and normalizes columns that somehow arrived
        unparsed (defensive; parse failures never reach this stage).

        Args:
            df (pandas.DataFrame): Validated DataFrame containing timestamp
                columns.

        Returns:
            pandas.DataFrame: The DataFrame with timestamp columns as UTC
            datetimes and raw-string backups present.
        """
        for col in ["event_timestamp", "ingestion_timestamp"]:
            if col in df.columns:
                # Back up the raw string only if the validator has not
                # already preserved it (never overwrite the raw pre-parse
                # value with a normalized string)
                raw_col = f"_raw_{col}"
                if raw_col not in df.columns:
                    df[raw_col] = df[col].astype(str)
                if not pd.api.types.is_datetime64_any_dtype(df[col]):
                    df[col] = parse_utc_mixed(df[col])
        return df

    @staticmethod
    def normalize_currency(df: pd.DataFrame) -> pd.DataFrame:
        """Upper-case currency codes and correct invalid values to USD.

        Non-standard ISO codes (not in ``{USD, EUR, GBP, CNY, JPY}``) are
        replaced with ``"USD"`` and the row is flagged via the
        ``_is_invalid_currency`` boolean column.

        Args:
            df (pandas.DataFrame): DataFrame containing a ``currency``
                column.

        Returns:
            pandas.DataFrame: The DataFrame with normalized currency values
            and an added ``_is_invalid_currency`` column.
        """
        if "currency" in df.columns:
            df["currency"] = df["currency"].astype(str).str.upper()
            valid_currencies = {"USD", "EUR", "GBP", "CNY", "JPY"}
            df["_is_invalid_currency"] = ~df["currency"].isin(valid_currencies)
            df.loc[df["_is_invalid_currency"], "currency"] = "USD"
        return df

    @staticmethod
    def check_amount(df: pd.DataFrame) -> pd.DataFrame:
        """Ensure amount is numeric and back up the pre-cleaner value.

        The original amount value is backed up to ``_raw_amount``, and the
        column is coerced to numeric.  Negative values never reach this
        method: the validator's minimum check quarantines them first.

        Args:
            df (pandas.DataFrame): DataFrame containing an ``amount``
                column.

        Returns:
            pandas.DataFrame: The DataFrame with ``amount`` coerced to
            numeric and a ``_raw_amount`` numeric backup column (the raw
            input word is preserved in ``_raw_json``).
        """
        if "amount" in df.columns:
            # Backup the pre-cleaner value (the validator has already coerced
            # it to numeric, so this is a numeric backup, not the raw input
            # string — the full raw word is preserved in _raw_json)
            if "_raw_amount" not in df.columns:
                df["_raw_amount"] = df["amount"]
            # Defensive numeric coercion (never raises; NaN stays NaN).
            # Negative / non-numeric / over-precision amounts were already
            # quarantined by the validator before this stage.
            df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        return df
