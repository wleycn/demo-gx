# [AI-GENERATED] model=deepseek-flash date=2026-09-09 reviewed_by=pending
"""Unit tests for the Gold-layer builder (GoldBuilder).

The fact/dimension/wide construction is the numeric heart of the Gold layer;
these tests protect the aggregation logic (dev-review: previously zero-tested).
"""

import pandas as pd

from demo_gx.curation.builder import GoldBuilder


def _silver_df():
    """Two customers across two event dates, one duplicate-key-free sample."""
    rows = [
        # 2026-01-01: cust_a 2 purchases, cust_b 1 purchase
        {
            "event_id": "a1",
            "event_date": pd.Timestamp("2026-01-01").date(),
            "customer_id": "cust_a",
            "event_type": "purchase",
            "event_timestamp": pd.Timestamp("2026-01-01T00:00:00Z"),
            "amount": 10.0,
        },
        {
            "event_id": "a2",
            "event_date": pd.Timestamp("2026-01-01").date(),
            "customer_id": "cust_a",
            "event_type": "purchase",
            "event_timestamp": pd.Timestamp("2026-01-01T01:00:00Z"),
            "amount": 20.0,
        },
        {
            "event_id": "b1",
            "event_date": pd.Timestamp("2026-01-01").date(),
            "customer_id": "cust_b",
            "event_type": "click",
            "event_timestamp": pd.Timestamp("2026-01-01T02:00:00Z"),
            "amount": 5.0,
        },
        # 2026-01-02: cust_a 1 purchase
        {
            "event_id": "a3",
            "event_date": pd.Timestamp("2026-01-02").date(),
            "customer_id": "cust_a",
            "event_type": "purchase",
            "event_timestamp": pd.Timestamp("2026-01-02T00:00:00Z"),
            "amount": 7.0,
        },
    ]
    return pd.DataFrame(rows)


def test_fact_table_aggregates_counts_and_amounts():
    fact = GoldBuilder.build_fact_table(_silver_df())
    key = (pd.Timestamp("2026-01-01").date(), "cust_a", "purchase")
    row = fact.set_index(["event_date", "customer_id", "event_type"]).loc[key]
    assert row["event_count"] == 2
    assert row["total_amount"] == 30.0
    assert row["avg_amount"] == 15.0
    # 4 rows collapse to 3 grain rows (cust_a@purchase@01-01 is a 2-row group)
    assert len(fact) == 3


def test_dimensions_first_seen_date():
    dims = GoldBuilder.build_dimensions(_silver_df())
    dc = dims["dim_customer"].set_index("customer_id")
    assert dc.loc["cust_a", "first_seen_date"] == pd.Timestamp("2026-01-01").date()
    assert dc.loc["cust_b", "first_seen_date"] == pd.Timestamp("2026-01-01").date()
    de = dims["dim_event_type"]
    assert set(de["event_type"]) == {"purchase", "click"}


def test_wide_table_joins_without_column_collision():
    silver = _silver_df()
    fact = GoldBuilder.build_fact_table(silver)
    dims = GoldBuilder.build_dimensions(silver)
    wide = GoldBuilder.build_wide_table(fact, dims)
    # no _x/_y suffix leakage from colliding merge keys
    assert not any("_x" in c or "_y" in c for c in wide.columns)
    assert "first_seen_date" in wide.columns
    assert len(wide) == len(fact)


def test_builder_handles_empty_input():
    empty = pd.DataFrame(columns=["event_id", "event_date", "customer_id", "event_type", "event_timestamp", "amount"])
    fact = GoldBuilder.build_fact_table(empty)
    dims = GoldBuilder.build_dimensions(empty)
    wide = GoldBuilder.build_wide_table(fact, dims)
    assert fact.empty
    assert dims["dim_customer"].empty
    assert wide.empty
