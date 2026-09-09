"""Gold-layer curation module.

Builds the star-schema data products (fact table, dimension tables, and a
denormalized wide table) from Silver-layer detail data for downstream BI
and analytics consumption.
"""

import pandas as pd


class GoldBuilder:
    """Constructs Gold-layer fact, dimension, and wide tables."""

    @staticmethod
    def build_fact_table(df: pd.DataFrame) -> pd.DataFrame:
        """Aggregate events into a daily fact table.

        Groups by ``event_date``, ``customer_id``, and ``event_type``,
        computing ``event_count``, ``total_amount``, and ``avg_amount``.

        Args:
            df (pandas.DataFrame): Silver-layer DataFrame.  Must contain
                ``event_timestamp`` (or a pre-derived ``event_date``
                column), ``event_id``, ``customer_id``, ``event_type``,
                and ``amount``.

        Returns:
            pandas.DataFrame: Aggregated fact table with one row per
            (event_date, customer_id, event_type) group.
        """
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
        """Extract dimension tables from Silver-layer data.

        Builds ``dim_customer`` (unique customer IDs with first-seen date)
        and ``dim_event_type`` (unique event types).

        Args:
            df (pandas.DataFrame): Silver-layer DataFrame containing at
                least ``customer_id`` and ``event_type`` columns.  If
                ``event_date`` is present, ``first_seen_date`` is derived.

        Returns:
            dict: A mapping from dimension table name to DataFrame.  Keys
            are ``"dim_customer"`` and ``"dim_event_type"``.
        """
        dim_customer = df[["customer_id"]].drop_duplicates().reset_index(drop=True)
        # Add first_seen_date (currently the minimum event_date available)
        if "event_date" in df.columns:
            first_seen = df.groupby("customer_id")["event_date"].min().reset_index(name="first_seen_date")
            dim_customer = dim_customer.merge(first_seen, on="customer_id", how="left")
        # Dimension table: event_type
        dim_event_type = df[["event_type"]].drop_duplicates().reset_index(drop=True)
        # Could add category etc., but currently left empty
        return {"dim_customer": dim_customer, "dim_event_type": dim_event_type}

    @staticmethod
    def build_wide_table(fact_df: pd.DataFrame, dims: dict) -> pd.DataFrame:
        """Build a denormalized wide table via left joins.

        Left-joins the fact table with ``dim_customer`` (on ``customer_id``)
        and ``dim_event_type`` (on ``event_type``) to produce a single
        flat table for direct BI consumption, avoiding runtime joins.

        Args:
            fact_df (pandas.DataFrame): The fact table produced by
                :meth:`build_fact_table`.
            dims (dict): Dimension dictionary produced by
                :meth:`build_dimensions`, containing ``dim_customer`` and
                ``dim_event_type`` keys.

        Returns:
            pandas.DataFrame: A denormalized wide table containing all
            fact and dimension columns.
        """
        wide = fact_df.merge(dims["dim_customer"], on="customer_id", how="left", validate="many_to_one")
        wide = wide.merge(dims["dim_event_type"], on="event_type", how="left", validate="many_to_one")
        return wide
