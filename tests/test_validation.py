"""Unit tests for the schema validation module.

Tests cover the happy path (a fully valid record passes validation) and
the failure path (a record missing a required field is correctly
quarantined with a descriptive error reason).
"""

import pytest
import pandas as pd
from validation.schema_validator import SchemaValidator
import yaml
from pathlib import Path


@pytest.fixture
def schema_config():
    """Load the schema.yaml contract for use in tests.

    Returns:
        dict: Parsed schema configuration from ``config/schema.yaml``.
    """
    with open(Path(__file__).parent.parent / "config" / "schema.yaml", "r") as f:
        return yaml.safe_load(f)


def test_validation_passes(schema_config):
    """A well-formed record should pass validation with zero invalid rows."""
    df = pd.DataFrame([{
        "event_id": "123e4567-e89b-42d3-a456-426614174000",
        "source_system": "web",
        "customer_id": "cust_001",
        "event_type": "purchase",
        "event_timestamp": (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=1)).isoformat(),
        "amount": 100.0,
        "currency": "USD",
        "ingestion_timestamp": (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=1)).isoformat()
    }])
    validator = SchemaValidator(schema_config)
    valid, invalid = validator.validate(df)
    assert len(valid) == 1
    assert len(invalid) == 0


def test_validation_fails_missing_field(schema_config):
    """A record missing event_id should be quarantined with an error reason."""
    df = pd.DataFrame([{
        "source_system": "web",
        "customer_id": "cust_001",
        "event_type": "purchase",
        "event_timestamp": (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=1)).isoformat(),
        "amount": 100.0,
        "currency": "USD",
        "ingestion_timestamp": (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=1)).isoformat()
    }])
    validator = SchemaValidator(schema_config)
    valid, invalid = validator.validate(df)
    assert len(valid) == 0
    assert len(invalid) == 1
    assert "Missing required field" in invalid.iloc[0]["error_reason"]


def test_validation_fails_future_timestamp(schema_config):
    """A record stamped in the future should be quarantined as invalid.

    The schema contract requires ``event_timestamp <= current time``
    (see docs/business/PROJECT.md); future-dated records are data-quality
    violations and must not pass into Silver.
    """
    future = (pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=1)).isoformat()
    df = pd.DataFrame([{
        "event_id": "123e4567-e89b-42d3-a456-426614174000",
        "source_system": "web",
        "customer_id": "cust_001",
        "event_type": "purchase",
        "event_timestamp": future,
        "amount": 100.0,
        "currency": "USD",
        "ingestion_timestamp": (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=1)).isoformat()
    }])
    validator = SchemaValidator(schema_config)
    valid, invalid = validator.validate(df)
    assert len(valid) == 0
    assert len(invalid) == 1
    assert "in future" in invalid.iloc[0]["error_reason"]


def _valid_row(**overrides):
    """A well-formed v4-UUID row; override any field for edge-case tests."""
    row = {
        "event_id": "123e4567-e89b-42d3-a456-426614174000",
        "source_system": "web",
        "customer_id": "cust_001",
        "event_type": "purchase",
        "event_timestamp": (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=1)).isoformat(),
        "amount": 100.0,
        "currency": "USD",
        "ingestion_timestamp": (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=1)).isoformat(),
    }
    row.update(overrides)
    return row


def test_validation_fails_non_numeric_amount(schema_config):
    """A non-numeric amount must quarantine that row, not crash the batch."""
    df = pd.DataFrame([
        _valid_row(),
        _valid_row(event_id="223e4567-e89b-42d3-a456-426614174000",
                   customer_id="cust_002", amount="abc"),
    ])
    validator = SchemaValidator(schema_config)
    valid, invalid = validator.validate(df)
    assert len(valid) == 1
    assert len(invalid) == 1
    assert "not numeric" in invalid.iloc[0]["error_reason"]


def test_validation_fails_extra_field(schema_config):
    """Strict mode: a row with an undeclared field must be quarantined."""
    df = pd.DataFrame([_valid_row(surprise="boom")])
    validator = SchemaValidator(schema_config)
    valid, invalid = validator.validate(df)
    assert len(valid) == 0
    assert len(invalid) == 1
    assert "Extra fields" in invalid.iloc[0]["error_reason"]


def test_validation_fails_non_v4_uuid(schema_config):
    """event_id must be a UUID v4 (version nibble = 4); v1 UUIDs are rejected."""
    df = pd.DataFrame([_valid_row(event_id="550e8400-e29b-11d4-a716-446655440000")])
    validator = SchemaValidator(schema_config)
    valid, invalid = validator.validate(df)
    assert len(valid) == 0
    assert len(invalid) == 1
    assert "pattern mismatch" in invalid.iloc[0]["error_reason"]


def test_validation_passes_mixed_timestamp_formats(schema_config):
    """A column mixing timezones/precisions must parse every row (format='mixed')."""
    df = pd.DataFrame([
        _valid_row(event_id="123e4567-e89b-42d3-a456-426614174010",
                   event_timestamp="2026-01-01T00:00:00Z"),
        _valid_row(event_id="223e4567-e89b-42d3-a456-426614174011",
                   event_timestamp="2026-01-01T00:00:00+08:00"),
        _valid_row(event_id="323e4567-e89b-42d3-a456-426614174012",
                   event_timestamp="2026-01-01T00:00:00.123456"),
    ])
    validator = SchemaValidator(schema_config)
    valid, invalid = validator.validate(df)
    assert len(invalid) == 0
    assert len(valid) == 3


def test_validation_fails_amount_too_precise(schema_config):
    """amount with >2 decimal places violates the max_decimals contract."""
    df = pd.DataFrame([_valid_row(amount=10.999)])
    validator = SchemaValidator(schema_config)
    valid, invalid = validator.validate(df)
    assert len(valid) == 0
    assert len(invalid) == 1
    assert "decimal places" in invalid.iloc[0]["error_reason"]


def test_validation_fails_infinite_amount(schema_config):
    """An amount that coerces to infinity must be quarantined, not summed."""
    df = pd.DataFrame([_valid_row(amount="1e309")])
    validator = SchemaValidator(schema_config)
    valid, invalid = validator.validate(df)
    assert len(valid) == 0
    assert len(invalid) == 1
    assert "not finite" in invalid.iloc[0]["error_reason"]


def test_validation_fails_extra_null_field(schema_config):
    """Strict mode: an undeclared key with a null value is still a breach."""
    df = pd.DataFrame([_valid_row(surprise=None)])
    validator = SchemaValidator(schema_config)
    valid, invalid = validator.validate(df)
    assert len(valid) == 0
    assert len(invalid) == 1


def test_validation_fails_dict_string_field(schema_config):
    """A compound (dict) value must not pass as a string via str() repr."""
    df = pd.DataFrame([_valid_row(customer_id={"$oid": "abc"})])
    validator = SchemaValidator(schema_config)
    valid, invalid = validator.validate(df)
    assert len(valid) == 0
    assert len(invalid) == 1
    assert "not a scalar string" in invalid.iloc[0]["error_reason"]


def test_validation_fails_negative_amount(schema_config):
    """amount below the schema minimum must be quarantined."""
    df = pd.DataFrame([_valid_row(amount=-1.0)])
    validator = SchemaValidator(schema_config)
    valid, invalid = validator.validate(df)
    assert len(valid) == 0
    assert "below minimum" in invalid.iloc[0]["error_reason"]


def test_validation_fails_enum_violation(schema_config):
    """A source_system outside the enum must be quarantined."""
    df = pd.DataFrame([_valid_row(source_system="desktop")])
    validator = SchemaValidator(schema_config)
    valid, invalid = validator.validate(df)
    assert len(valid) == 0
    assert "not in enum" in invalid.iloc[0]["error_reason"]


def test_validation_fails_event_type_too_long(schema_config):
    """event_type beyond max_length must be quarantined."""
    df = pd.DataFrame([_valid_row(event_type="x" * 65)])
    validator = SchemaValidator(schema_config)
    valid, invalid = validator.validate(df)
    assert len(valid) == 0
    assert "max length" in invalid.iloc[0]["error_reason"]


def test_validation_fails_unparseable_timestamp(schema_config):
    """A timestamp string that cannot be parsed must be quarantined."""
    df = pd.DataFrame([_valid_row(event_timestamp="not-a-date")])
    validator = SchemaValidator(schema_config)
    valid, invalid = validator.validate(df)
    assert len(valid) == 0
    assert "parse failed" in invalid.iloc[0]["error_reason"]


def test_validation_passes_exact_two_decimal_amount(schema_config):
    """Boundary: 10.0 (2 decimals) passes; only >2 decimals are rejected."""
    df = pd.DataFrame([_valid_row(amount=10.0)])
    validator = SchemaValidator(schema_config)
    valid, invalid = validator.validate(df)
    assert len(valid) == 1
    assert len(invalid) == 0
