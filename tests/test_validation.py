# [AI-GENERATED] model=deepseek-flash date=2026-09-09 reviewed_by=pending
"""Unit tests for the schema validation module.

Tests cover the happy path (a fully valid record passes validation) and
the failure path (a record missing a required field is correctly
quarantined with a descriptive error reason).
"""

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import yaml

from demo_gx.ingestion.reader import read_input
from demo_gx.validation.schema_validator import SchemaValidator


@pytest.fixture
def schema_config() -> dict[str, Any]:
    """Load the schema.yaml contract for use in tests.

    Returns:
        dict: Parsed schema configuration from ``config/contract/schema.yaml``.
    """

    with open(Path(__file__).parent.parent / "config" / "contract" / "schema.yaml") as f:
        return yaml.safe_load(f)


# Fixed run instant, injected into the validator so the "<= current time" rule
# is evaluated against a known point instead of the wall clock. Fixture
# timestamps are expressed relative to it, which makes every case reproducible.
RUN_TS = pd.Timestamp("2026-09-14T00:00:00Z")


def _ts(days_ago: float) -> str:
    """Return an ISO-8601 stamp ``days_ago`` days before RUN_TS.

    Args:
        days_ago (float): Positive values are in the past; negative values
            are in the future relative to RUN_TS.

    Returns:
        str: ISO-8601 timestamp string.
    """

    return (RUN_TS - pd.Timedelta(days=days_ago)).isoformat()


def test_validation_passes(schema_config: dict[str, Any]) -> None:
    """A well-formed record should pass validation with zero invalid rows."""

    df = pd.DataFrame(
        [
            {
                "event_id": "123e4567-e89b-42d3-a456-426614174000",
                "source_system": "web",
                "customer_id": "cust_001",
                "event_type": "purchase",
                "event_timestamp": _ts(1),
                "amount": 100.0,
                "currency": "USD",
                "ingestion_timestamp": _ts(1),
            }
        ]
    )
    validator = SchemaValidator(schema_config, RUN_TS)
    valid, invalid = validator.validate(df)
    assert len(valid) == 1
    assert len(invalid) == 0


def test_validation_fails_missing_field(schema_config: dict[str, Any]) -> None:
    """A record missing event_id should be quarantined with an error reason."""

    df = pd.DataFrame(
        [
            {
                "source_system": "web",
                "customer_id": "cust_001",
                "event_type": "purchase",
                "event_timestamp": _ts(1),
                "amount": 100.0,
                "currency": "USD",
                "ingestion_timestamp": _ts(1),
            }
        ]
    )
    validator = SchemaValidator(schema_config, RUN_TS)
    valid, invalid = validator.validate(df)
    assert len(valid) == 0
    assert len(invalid) == 1
    assert "Missing required field" in invalid.iloc[0]["error_reason"]


def test_validation_fails_future_timestamp(schema_config: dict[str, Any]) -> None:
    """A record stamped in the future should be quarantined as invalid.

    The schema contract requires ``event_timestamp <= current time``
    (see docs/business/PROJECT.md); future-dated records are data-quality
    violations and must not pass into Silver.
    """

    future = _ts(-1)
    df = pd.DataFrame(
        [
            {
                "event_id": "123e4567-e89b-42d3-a456-426614174000",
                "source_system": "web",
                "customer_id": "cust_001",
                "event_type": "purchase",
                "event_timestamp": future,
                "amount": 100.0,
                "currency": "USD",
                "ingestion_timestamp": _ts(1),
            }
        ]
    )
    validator = SchemaValidator(schema_config, RUN_TS)
    valid, invalid = validator.validate(df)
    assert len(valid) == 0
    assert len(invalid) == 1
    assert "in future" in invalid.iloc[0]["error_reason"]


def _valid_row(**overrides: object) -> dict[str, Any]:
    """A well-formed v4-UUID row; override any field for edge-case tests."""

    row = {
        "event_id": "123e4567-e89b-42d3-a456-426614174000",
        "source_system": "web",
        "customer_id": "cust_001",
        "event_type": "purchase",
        "event_timestamp": _ts(1),
        "amount": 100.0,
        "currency": "USD",
        "ingestion_timestamp": _ts(1),
    }
    row.update(overrides)
    return row


def test_an_undeclared_key_quarantines_only_its_own_record(schema_config: dict[str, Any], tmp_path: Path) -> None:
    """Strict mode judges the record, not the batch: one stray key does not sink the file.

    Before the audit copy kept each record's own key set, pandas turned the stray
    key into a column and every row's ``_raw_json`` then carried it, so a single
    bad record quarantined the whole batch.
    """

    rows = [
        _valid_row(surprise="boom"),
        _valid_row(event_id="223e4567-e89b-42d3-a456-426614174000", customer_id="cust_002"),
    ]
    source = tmp_path / "input.json"
    source.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    df = read_input(str(source), masked_fields=[])
    valid, invalid = SchemaValidator(schema_config, RUN_TS).validate(df)
    assert len(invalid) == 1, invalid["error_reason"].tolist()
    assert len(valid) == 1
    assert "Extra fields" in invalid.iloc[0]["error_reason"]
    assert "surprise" not in valid.columns


def test_an_input_that_carries_its_own_raw_json_column_still_flows(
    schema_config: dict[str, Any], tmp_path: Path
) -> None:
    """A source column named ``_raw_json`` is preserved and dropped, not a contract breach."""

    source = tmp_path / "input.json"
    source.write_text(json.dumps(_valid_row(_raw_json='{"k": 1}')) + "\n", encoding="utf-8")
    df = read_input(str(source), masked_fields=[])
    assert df["_raw_json_user"].iloc[0] == '{"k": 1}'
    valid, invalid = SchemaValidator(schema_config, RUN_TS).validate(df)
    assert len(invalid) == 0, invalid["error_reason"].tolist()
    assert len(valid) == 1
    assert "_raw_json_user" not in valid.columns


def test_validation_fails_non_numeric_amount(schema_config: dict[str, Any]) -> None:
    """A non-numeric amount must quarantine that row, not crash the batch."""

    df = pd.DataFrame(
        [
            _valid_row(),
            _valid_row(event_id="223e4567-e89b-42d3-a456-426614174000", customer_id="cust_002", amount="abc"),
        ]
    )
    validator = SchemaValidator(schema_config, RUN_TS)
    valid, invalid = validator.validate(df)
    assert len(valid) == 1
    assert len(invalid) == 1
    assert "not numeric" in invalid.iloc[0]["error_reason"]


def test_validation_fails_extra_field(schema_config: dict[str, Any]) -> None:
    """Strict mode: a row with an undeclared field must be quarantined."""

    df = pd.DataFrame([_valid_row(surprise="boom")])
    validator = SchemaValidator(schema_config, RUN_TS)
    valid, invalid = validator.validate(df)
    assert len(valid) == 0
    assert len(invalid) == 1
    assert "Extra fields" in invalid.iloc[0]["error_reason"]


def test_validation_fails_non_v4_uuid(schema_config: dict[str, Any]) -> None:
    """event_id must be a UUID v4 (version nibble = 4); v1 UUIDs are rejected."""

    df = pd.DataFrame([_valid_row(event_id="550e8400-e29b-11d4-a716-446655440000")])
    validator = SchemaValidator(schema_config, RUN_TS)
    valid, invalid = validator.validate(df)
    assert len(valid) == 0
    assert len(invalid) == 1
    assert "pattern mismatch" in invalid.iloc[0]["error_reason"]


def test_validation_passes_mixed_timestamp_formats(schema_config: dict[str, Any]) -> None:
    """A column mixing timezones/precisions must parse every row (format='mixed')."""

    df = pd.DataFrame(
        [
            _valid_row(event_id="123e4567-e89b-42d3-a456-426614174010", event_timestamp="2026-01-01T00:00:00Z"),
            _valid_row(event_id="223e4567-e89b-42d3-a456-426614174011", event_timestamp="2026-01-01T00:00:00+08:00"),
            _valid_row(event_id="323e4567-e89b-42d3-a456-426614174012", event_timestamp="2026-01-01T00:00:00.123456"),
        ]
    )
    validator = SchemaValidator(schema_config, RUN_TS)
    valid, invalid = validator.validate(df)
    assert len(invalid) == 0
    assert len(valid) == 3


def test_validation_fails_amount_too_precise(schema_config: dict[str, Any]) -> None:
    """Amount with >2 decimal places violates the max_decimals contract."""

    df = pd.DataFrame([_valid_row(amount=10.999)])
    validator = SchemaValidator(schema_config, RUN_TS)
    valid, invalid = validator.validate(df)
    assert len(valid) == 0
    assert len(invalid) == 1
    assert "decimal places" in invalid.iloc[0]["error_reason"]


def test_validation_passes_a_large_amount_with_two_decimals(schema_config: dict[str, Any]) -> None:
    """A two-decimal amount must not be quarantined for its magnitude.

    Scaling a large value multiplies its float error with it, so an absolute
    epsilon ends up flagging valid money: the tolerance has to be relative.
    """

    df = pd.DataFrame([_valid_row(amount=10000000000000.12)])
    validator = SchemaValidator(schema_config, RUN_TS)
    valid, invalid = validator.validate(df)
    assert len(invalid) == 0, invalid.iloc[0]["error_reason"]
    assert len(valid) == 1


def test_validation_fails_infinite_amount(schema_config: dict[str, Any]) -> None:
    """An amount that coerces to infinity must be quarantined, not summed."""

    df = pd.DataFrame([_valid_row(amount="1e309")])
    validator = SchemaValidator(schema_config, RUN_TS)
    valid, invalid = validator.validate(df)
    assert len(valid) == 0
    assert len(invalid) == 1
    assert "not finite" in invalid.iloc[0]["error_reason"]


def test_validation_fails_extra_null_field(schema_config: dict[str, Any]) -> None:
    """Strict mode: an undeclared key with a null value is still a breach."""

    df = pd.DataFrame([_valid_row(surprise=None)])
    validator = SchemaValidator(schema_config, RUN_TS)
    valid, invalid = validator.validate(df)
    assert len(valid) == 0
    assert len(invalid) == 1


def test_validation_fails_dict_string_field(schema_config: dict[str, Any]) -> None:
    """A compound (dict) value must not pass as a string via str() repr."""

    df = pd.DataFrame([_valid_row(customer_id={"$oid": "abc"})])
    validator = SchemaValidator(schema_config, RUN_TS)
    valid, invalid = validator.validate(df)
    assert len(valid) == 0
    assert len(invalid) == 1
    assert "not a scalar string" in invalid.iloc[0]["error_reason"]


def test_validation_fails_negative_amount(schema_config: dict[str, Any]) -> None:
    """Amount below the schema minimum must be quarantined."""

    df = pd.DataFrame([_valid_row(amount=-1.0)])
    validator = SchemaValidator(schema_config, RUN_TS)
    valid, invalid = validator.validate(df)
    assert len(valid) == 0
    assert "below minimum" in invalid.iloc[0]["error_reason"]


def test_validation_fails_enum_violation(schema_config: dict[str, Any]) -> None:
    """A source_system outside the enum must be quarantined."""

    df = pd.DataFrame([_valid_row(source_system="desktop")])
    validator = SchemaValidator(schema_config, RUN_TS)
    valid, invalid = validator.validate(df)
    assert len(valid) == 0
    assert "not in enum" in invalid.iloc[0]["error_reason"]


def test_validation_fails_event_type_too_long(schema_config: dict[str, Any]) -> None:
    """event_type beyond max_length must be quarantined."""

    df = pd.DataFrame([_valid_row(event_type="x" * 65)])
    validator = SchemaValidator(schema_config, RUN_TS)
    valid, invalid = validator.validate(df)
    assert len(valid) == 0
    assert "max length" in invalid.iloc[0]["error_reason"]


def test_validation_fails_unparseable_timestamp(schema_config: dict[str, Any]) -> None:
    """A timestamp string that cannot be parsed must be quarantined."""

    df = pd.DataFrame([_valid_row(event_timestamp="not-a-date")])
    validator = SchemaValidator(schema_config, RUN_TS)
    valid, invalid = validator.validate(df)
    assert len(valid) == 0
    assert "parse failed" in invalid.iloc[0]["error_reason"]


def test_validation_passes_exact_two_decimal_amount(schema_config: dict[str, Any]) -> None:
    """Boundary: 10.0 (2 decimals) passes; only >2 decimals are rejected."""

    df = pd.DataFrame([_valid_row(amount=10.0)])
    validator = SchemaValidator(schema_config, RUN_TS)
    valid, invalid = validator.validate(df)
    assert len(valid) == 1
    assert len(invalid) == 0
