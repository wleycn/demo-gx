# [AI-GENERATED] model=deepseek-flash date=2026-09-09 reviewed_by=Rocky
"""Shared time-parsing utilities for the pipeline.

Timestamp-parsing policy lives in ONE place so the validator, cleaner, CLI,
and Bronze writer cannot drift apart (dev-review: triplicated
``pd.to_datetime`` calls with diverging failure semantics).
"""

import pandas as pd


def parse_utc_mixed(series: pd.Series) -> pd.Series:
    """Parse an ISO-8601 series to UTC datetimes, tolerating mixed formats.

    ``format="mixed"`` makes pandas parse each element in its own format
    (mixed timezones / precisions), instead of applying the first row's
    format to every row — which silently NaTs all other formats.
    Unparseable values become NaT; this function never raises.

    Args:
        series (pandas.Series): Object/string series of ISO-8601 timestamps.

    Returns:
        pandas.Series: ``datetime64[ns, UTC]`` with NaT for unparseable
        values.
    """

    return pd.to_datetime(series, utc=True, errors="coerce", format="mixed")
