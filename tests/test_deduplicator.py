"""Unit tests for the deduplication module (Deduplicator)."""

import pandas as pd
from demo_gx.transformation.deduplicator import Deduplicator


def _dup_df(*rows):
    return pd.DataFrame(list(rows))


def _row(event_id, ingestion_ts, amount=1.0):
    return {
        "event_id": event_id,
        "ingestion_timestamp": pd.Timestamp(ingestion_ts, tz="UTC"),
        "amount": amount,
    }


def test_deduplicate_keeps_newest():
    """For a duplicate event_id, only the newest ingestion_timestamp survives."""
    df = _dup_df(
        _row("e1", "2026-01-01T00:00:00Z", amount=10),
        _row("e1", "2026-01-02T00:00:00Z", amount=20),
        _row("e2", "2026-01-01T00:00:00Z", amount=30),
    )
    deduped, duplicates = Deduplicator.deduplicate(df)
    assert len(deduped) == 2
    assert len(duplicates) == 1
    assert duplicates.iloc[0]["amount"] == 10  # the older row is superseded
    e1 = deduped[deduped["event_id"] == "e1"]
    assert e1.iloc[0]["amount"] == 20


def test_deduplicate_tie_keeps_last_input_row():
    """Exact ingestion_timestamp tie: the last-occurring row wins (stable sort)."""
    df = _dup_df(
        _row("e1", "2026-01-01T00:00:00Z", amount=10),
        _row("e1", "2026-01-01T00:00:00Z", amount=99),
    )
    deduped, duplicates = Deduplicator.deduplicate(df)
    assert len(duplicates) == 1
    assert duplicates.iloc[0]["amount"] == 10
    assert deduped.iloc[0]["amount"] == 99


def test_deduplicate_early_return_on_missing_columns():
    """Missing event_id/ingestion_timestamp: return unchanged + empty log."""
    df = pd.DataFrame([{"amount": 1.0}])
    deduped, duplicates = Deduplicator.deduplicate(df)
    assert len(deduped) == 1
    assert duplicates.empty
