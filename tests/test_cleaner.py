# [AI-GENERATED] model=deepseek-flash date=2026-09-09 reviewed_by=pending
"""Unit tests for the cleaning module (DataCleaner)."""

import pandas as pd
from demo_gx.transformation.cleaner import DataCleaner


def _clean_df(**overrides):
    row = {
        "event_id": "123e4567-e89b-42d3-a456-426614174000",
        "source_system": "web",
        "customer_id": "cust_001",
        "event_type": "purchase",
        "event_timestamp": "2026-01-01T00:00:00+08:00",
        "amount": 100.0,
        "currency": "usd",
        "ingestion_timestamp": "2026-01-02T00:00:00Z",
    }
    row.update(overrides)
    return pd.DataFrame([row])


def test_standardize_timestamps_utc_conversion():
    """Timestamps parse to UTC and the raw string is backed up unchanged."""
    df = _clean_df()
    out = DataCleaner.standardize_timestamps(df.copy())
    ts = pd.Timestamp("2026-01-01T00:00:00+08:00", tz="UTC")
    assert out["event_timestamp"].iloc[0] == ts  # +08:00 -> 07:00 UTC prior day
    assert out["_raw_event_timestamp"].iloc[0] == "2026-01-01T00:00:00+08:00"


def test_standardize_timestamps_keeps_existing_raw_backup():
    """If the validator already backed up the raw string, do not overwrite it."""
    df = _clean_df(event_timestamp="2026-01-01T07:00:00Z")
    df["_raw_event_timestamp"] = "ORIGINAL-RAW"
    out = DataCleaner.standardize_timestamps(df)
    assert out["_raw_event_timestamp"].iloc[0] == "ORIGINAL-RAW"


def test_normalize_currency_uppercases_and_flags_non_whitelist():
    """Lowercase codes uppercase; codes outside the whitelist become USD+flag."""
    df = pd.DataFrame([
        _clean_df().iloc[0].to_dict(),
    ])
    df["currency"] = "usd"
    out = DataCleaner.normalize_currency(df)
    assert out["currency"].iloc[0] == "USD"
    assert not bool(out["_is_invalid_currency"].iloc[0])

    df2 = pd.DataFrame([_clean_df(currency="XXX").iloc[0].to_dict()])
    out2 = DataCleaner.normalize_currency(df2)
    assert out2["currency"].iloc[0] == "USD"
    assert bool(out2["_is_invalid_currency"].iloc[0]) is True


def test_check_amount_backs_up_and_coerces():
    """_raw_amount preserves the pre-coercion value; amount becomes numeric."""
    df = pd.DataFrame([_clean_df(amount="12.5").iloc[0].to_dict()])
    out = DataCleaner.check_amount(df)
    assert out["_raw_amount"].iloc[0] == "12.5"
    assert out["amount"].iloc[0] == 12.5
