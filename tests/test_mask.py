# [AI-GENERATED] model=deepseek-flash date=2026-09-14 reviewed_by=pending
"""Unit tests for the PII masking policy at the ingestion boundary.

The mask must be stable and injective: Gold groups events by ``customer_id`` and
``dim_customer`` holds one row per distinct value, so two distinct inputs may
never collapse into one output.
"""

import json
import pathlib

import pandas as pd

from demo_gx.common.config import load_schema
from demo_gx.common.mask import MASK_HEX_LEN, MASK_PREFIX, mask_columns, mask_value
from demo_gx.ingestion.reader import read_input
from demo_gx.validation.schema_validator import SchemaValidator


def test_mask_is_deterministic() -> None:
    """The same input produces the same output, which keeps joins working."""
    assert mask_value("cust_001") == mask_value("cust_001")


def test_mask_keeps_distinct_inputs_distinct() -> None:
    """Two different identifiers must not collapse into one masked value."""
    values = {mask_value(f"cust_{i:03d}") for i in range(200)}
    assert len(values) == 200


def test_mask_shape_is_prefix_and_hex_digest() -> None:
    """The masked value states that it is a digest and leaks no input text."""
    masked = mask_value("cust_001")
    assert masked.startswith(MASK_PREFIX)
    assert len(masked) == len(MASK_PREFIX) + MASK_HEX_LEN
    assert all(c in "0123456789abcdef" for c in masked[len(MASK_PREFIX) :])
    assert "cust_001" not in masked


def test_pepper_changes_the_digest() -> None:
    """A deployment-injected key produces a different mask for the same input."""
    assert mask_value("cust_001") != mask_value("cust_001", pepper="secret")


def test_mask_columns_replaces_only_the_named_column() -> None:
    """Other columns pass through and the caller's frame is left untouched."""
    df = pd.DataFrame({"customer_id": ["cust_001"], "amount": [12.5]})
    masked = mask_columns(df, ["customer_id"])
    assert masked["customer_id"].iloc[0] == mask_value("cust_001")
    assert masked["amount"].equals(df["amount"])
    assert df["customer_id"].iloc[0] == "cust_001"


def test_mask_columns_skips_a_column_the_frame_does_not_carry() -> None:
    """A partial input still reaches the validator instead of failing here."""
    df = pd.DataFrame({"event_id": ["abc"]})
    masked = mask_columns(df, ["customer_id"])
    assert list(masked.columns) == ["event_id"]


def test_mask_columns_leaves_a_missing_identifier_missing() -> None:
    """A null identifier stays null, so the required-field gate can still see it.

    Hashing ``"nan"`` would turn every null into one well-formed digest: the row
    would pass validation and every such row would collapse into a single
    phantom customer.
    """
    df = pd.DataFrame({"customer_id": ["cust_001", None], "amount": [1.0, 2.0]})
    masked = mask_columns(df, ["customer_id"])
    assert masked["customer_id"].iloc[0] == mask_value("cust_001")
    assert pd.isna(masked["customer_id"].iloc[1])


def test_read_input_keeps_a_null_identifier_null(tmp_path: pathlib.Path) -> None:
    """The audit copy must show the missing identifier, not a digest of ``"nan"``."""
    source = tmp_path / "input.json"
    source.write_text(
        json.dumps(
            {
                "event_id": "bdd640fb-0667-4ad1-9c80-317fa3b1799d",
                "source_system": "web",
                "customer_id": None,
                "event_type": "view",
                "amount": 1.5,
                "currency": "USD",
            }
        )
        + "\n"
    )
    df = read_input(str(source), masked_fields=["customer_id"])
    assert pd.isna(df["customer_id"].iloc[0])
    assert json.loads(df["_raw_json"].iloc[0])["customer_id"] is None


def test_a_null_identifier_is_quarantined_and_not_hashed(tmp_path: pathlib.Path) -> None:
    """End to end: the row lands in the quarantine and the reason names the field.

    Before the null rule, this row passed validation and reached Silver with a
    digest of the string ``"nan"`` as its customer id.
    """
    source = tmp_path / "input.json"
    source.write_text(
        json.dumps(
            {
                "event_id": "bdd640fb-0667-4ad1-9c80-317fa3b1799d",
                "source_system": "web",
                "customer_id": None,
                "event_type": "view",
                "event_timestamp": "2026-09-10T10:00:00Z",
                "amount": 1.5,
                "currency": "USD",
                "ingestion_timestamp": "2026-09-10T10:01:00Z",
            }
        )
        + "\n"
    )
    df = read_input(str(source), masked_fields=["customer_id"])
    validator = SchemaValidator(load_schema(), pd.Timestamp("2026-09-15T00:00:00Z"))
    valid, invalid = validator.validate(df)
    assert len(valid) == 0
    assert len(invalid) == 1
    assert "customer_id is null" in invalid.iloc[0]["error_reason"]


def test_read_input_masks_before_the_audit_copy(tmp_path: pathlib.Path) -> None:
    """The clear value must not survive in the column or in `_raw_json`."""
    source = tmp_path / "input.json"
    source.write_text(
        json.dumps(
            {
                "event_id": "bdd640fb-0667-4ad1-9c80-317fa3b1799d",
                "source_system": "web",
                "customer_id": "cust_001",
                "event_type": "view",
                "amount": 1.5,
                "currency": "USD",
            }
        )
        + "\n"
    )
    df = read_input(str(source), masked_fields=["customer_id"])
    assert df["customer_id"].iloc[0] == mask_value("cust_001")
    assert "cust_001" not in df["_raw_json"].iloc[0]


def test_read_input_keeps_the_clear_value_when_masking_is_not_configured(tmp_path: pathlib.Path) -> None:
    """An empty mask list leaves the input untouched, so the demo can show both."""
    source = tmp_path / "input.json"
    source.write_text(json.dumps({"customer_id": "cust_001", "amount": 1.5}) + "\n")
    df = read_input(str(source), masked_fields=[])
    assert df["customer_id"].iloc[0] == "cust_001"
