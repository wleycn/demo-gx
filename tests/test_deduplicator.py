# [AI-GENERATED] model=deepseek-flash date=2026-09-09 reviewed_by=pending
"""Unit tests for the deduplication module (Deduplicator)."""

import pandas as pd

from demo_gx.transformation.deduplicator import Deduplicator


def _dup_df(*rows: pd.Series) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


def _row(event_id: str, ingestion_ts: str, amount: float = 1.0) -> pd.Series:
    return {
        "event_id": event_id,
        "ingestion_timestamp": pd.Timestamp(ingestion_ts, tz="UTC"),
        "amount": amount,
    }


def test_deduplicate_keeps_newest() -> None:
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


def test_deduplicate_tie_keeps_last_input_row() -> None:
    """Exact ingestion_timestamp tie: the last-occurring row wins (stable sort)."""
    df = _dup_df(
        _row("e1", "2026-01-01T00:00:00Z", amount=10),
        _row("e1", "2026-01-01T00:00:00Z", amount=99),
    )
    deduped, duplicates = Deduplicator.deduplicate(df)
    assert len(duplicates) == 1
    assert duplicates.iloc[0]["amount"] == 10
    assert deduped.iloc[0]["amount"] == 99


def test_deduplicate_early_return_on_missing_columns() -> None:
    """Missing event_id/ingestion_timestamp: return unchanged + empty log."""
    df = pd.DataFrame([{"amount": 1.0}])
    deduped, duplicates = Deduplicator.deduplicate(df)
    assert len(deduped) == 1
    assert duplicates.empty


def test_a_row_without_a_usable_timestamp_never_wins_the_duplicate() -> None:
    """An unparseable ingestion_timestamp must lose to one that has a value.

    The sort left NaT last, and keep-last then promoted the row nobody could
    order over the row that carried a timestamp: the surviving record was the
    one with the least usable data.
    """
    df = pd.DataFrame(
        [
            {"event_id": "e1", "ingestion_timestamp": pd.Timestamp("2026-01-02T00:00:00Z"), "amount": 10.0},
            {"event_id": "e1", "ingestion_timestamp": pd.NaT, "amount": 99.0},
        ]
    )
    deduped, duplicates = Deduplicator.deduplicate(df)
    assert len(deduped) == 1
    assert deduped.iloc[0]["amount"] == 10.0
    assert duplicates.iloc[0]["amount"] == 99.0
