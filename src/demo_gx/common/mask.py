# [AI-GENERATED] model=deepseek-flash date=2026-09-14 reviewed_by=Rocky
"""PII masking for the ingestion boundary.

Direct identifiers are replaced by a keyed digest as records enter the
pipeline. Everything downstream of ingestion therefore carries the masked
value: the ``_raw_json`` audit copy, Bronze, Silver, Gold, the quarantine
envelopes and the logs. This is the single masking entry point; no other module
may build its own mask (AGENTS.md section 3 red line 4).

The mask is a keyed digest rather than a partial redaction on purpose. Gold
groups events by ``customer_id`` and ``dim_customer`` holds one row per distinct
value, so each distinct input must map to exactly one stable output. A
redaction such as ``cust_***`` would collapse every customer into one bucket and
silently change the Gold row counts.
"""

import hashlib
import hmac
from collections.abc import Iterable

import pandas as pd

MASK_PREFIX = "h_"
MASK_HEX_LEN = 16


def mask_value(value: str, pepper: str = "") -> str:
    """Return the masked form of one identifier.

    Args:
        value (str): The clear-text identifier.
        pepper (str): Key for the HMAC. The demo config leaves it empty. A real
            deployment injects it from the configuration single entry point, so
            the digest cannot be reproduced without the key.

    Returns:
        str: ``h_`` followed by 16 hex characters of the HMAC-SHA256 digest.
        The same input always produces the same output for a given key.
    """
    digest = hmac.new(pepper.encode("utf-8"), str(value).encode("utf-8"), hashlib.sha256)
    return MASK_PREFIX + digest.hexdigest()[:MASK_HEX_LEN]


def mask_columns(df: pd.DataFrame, columns: Iterable[str], pepper: str = "") -> pd.DataFrame:
    """Return a copy of ``df`` with every named column masked.

    A configured column that the frame does not carry is skipped, so a partial
    input still flows to the validator and gets quarantined there rather than
    failing at the read boundary.

    A missing value stays missing. Masking it would hash the string ``"nan"``,
    which turns every null identifier into the same well-formed digest: the row
    then passes the required-field gate and every such row collapses into one
    phantom customer in ``dim_customer`` and in the Gold groups.

    Args:
        df (pandas.DataFrame): The frame to mask.
        columns (Iterable[str]): Column names to replace with their masked form.
        pepper (str): Key for the HMAC, see :func:`mask_value`.

    Returns:
        pandas.DataFrame: A new frame; the input frame is left untouched.
    """
    masked = df.copy()
    for column in columns:
        if column in masked.columns:
            masked[column] = masked[column].map(lambda value: mask_value(value, pepper) if pd.notna(value) else value)
    return masked
