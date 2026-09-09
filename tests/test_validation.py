import pytest
import pandas as pd
from validation.schema_validator import SchemaValidator
import yaml
from pathlib import Path

@pytest.fixture
def schema_config():
    with open(Path(__file__).parent.parent / "config" / "schema.yaml", "r") as f:
        return yaml.safe_load(f)

def test_validation_passes(schema_config):
    df = pd.DataFrame([{
        "event_id": "123e4567-e89b-12d3-a456-426614174000",
        "source_system": "web",
        "customer_id": "cust_001",
        "event_type": "purchase",
        "event_timestamp": "2026-01-01T00:00:00Z",
        "amount": 100.0,
        "currency": "USD",
        "ingestion_timestamp": "2026-01-01T00:00:00Z"
    }])
    validator = SchemaValidator(schema_config)
    valid, invalid = validator.validate(df)
    assert len(valid) == 1
    assert len(invalid) == 0

def test_validation_fails_missing_field(schema_config):
    df = pd.DataFrame([{
        "source_system": "web",
        "customer_id": "cust_001",
        "event_type": "purchase",
        "event_timestamp": "2026-01-01T00:00:00Z",
        "amount": 100.0,
        "currency": "USD",
        "ingestion_timestamp": "2026-01-01T00:00:00Z"
    }])
    validator = SchemaValidator(schema_config)
    valid, invalid = validator.validate(df)
    assert len(valid) == 0
    assert len(invalid) == 1
    assert "Missing required field" in invalid.iloc[0]["error_reason"]

