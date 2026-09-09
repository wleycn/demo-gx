"""Sample data generator for the pipeline.

Generates a representative JSON Lines file with valid records plus
intentionally anomalous records (missing field, negative amount, invalid
enum, future timestamp, duplicate event_id) for testing validation,
cleaning, and deduplication logic.
"""

import json
import uuid
from datetime import datetime, timedelta
import random
from pathlib import Path


def generate_sample_data(num_records=100, output_path="sample_data.json"):
    """Generate sample event records and write them as JSON Lines.

    Produces ``num_records`` valid random records, then appends several
    intentionally anomalous records to exercise the pipeline's error
    handling:
    1. A record missing ``event_id``.
    2. A record with a negative ``amount``.
    3. A record with an invalid ``source_system``.
    4. A record with a future ``event_timestamp``.
    5. Two records sharing a duplicate ``event_id``.
    6. A record with a non-numeric ``amount`` (type-coercion failure).

    Args:
        num_records (int): Number of valid random records to generate.
            Defaults to 100.
        output_path (str): Path to the output JSON Lines file.  Defaults
            to ``"sample_data.json"``.
    """
    records = []
    random.seed(42)  # reproducible sample (dev-review: CI smoke must be stable)
    now = datetime.utcnow()
    systems = ["web", "mobile", "api"]
    # XXX passes the schema's ^[A-Z]{3}$ format check but is not in the
    # cleaner whitelist → it exercises the normalize-to-USD + flag path
    currencies = ["USD", "EUR", "GBP", "CNY", "JPY", "XXX"]
    event_types = ["purchase", "view", "click", "signup", "login"]
    for _ in range(num_records):
        rec = {
            "event_id": str(uuid.uuid4()),
            "source_system": random.choice(systems),
            "customer_id": f"cust_{random.randint(1, 50):03d}",
            "event_type": random.choice(event_types),
            "event_timestamp": (now - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))).isoformat(),
            "amount": round(random.uniform(0, 1000), 2),
            "currency": random.choice(currencies),
            "ingestion_timestamp": now.isoformat(),
        }
        records.append(rec)
    # Intentionally add some anomalous records
    # 1. Missing event_id
    records.append({"source_system": "web", "customer_id": "cust_999", "event_type": "purchase", "event_timestamp": now.isoformat(), "amount": 10, "currency": "USD", "ingestion_timestamp": now.isoformat()})
    # 2. Invalid amount (negative)
    records.append({"event_id": str(uuid.uuid4()), "source_system": "api", "customer_id": "cust_888", "event_type": "view", "event_timestamp": now.isoformat(), "amount": -5, "currency": "USD", "ingestion_timestamp": now.isoformat()})
    # 3. Invalid source_system
    records.append({"event_id": str(uuid.uuid4()), "source_system": "unknown", "customer_id": "cust_777", "event_type": "click", "event_timestamp": now.isoformat(), "amount": 20, "currency": "EUR", "ingestion_timestamp": now.isoformat()})
    # 4. Future timestamp
    records.append({"event_id": str(uuid.uuid4()), "source_system": "mobile", "customer_id": "cust_666", "event_type": "login", "event_timestamp": (now + timedelta(days=1)).isoformat(), "amount": 0, "currency": "GBP", "ingestion_timestamp": now.isoformat()})
    # 5. Duplicate event_id
    dup_id = str(uuid.uuid4())
    records.append({"event_id": dup_id, "source_system": "web", "customer_id": "cust_555", "event_type": "signup", "event_timestamp": (now - timedelta(hours=1)).isoformat(), "amount": 0, "currency": "USD", "ingestion_timestamp": now.isoformat()})
    records.append({"event_id": dup_id, "source_system": "web", "customer_id": "cust_555", "event_type": "signup", "event_timestamp": (now - timedelta(hours=2)).isoformat(), "amount": 0, "currency": "USD", "ingestion_timestamp": (now - timedelta(hours=1)).isoformat()})
    # 6. Non-numeric amount (exercises error_type=type_coercion_failed)
    records.append({"event_id": str(uuid.uuid4()), "source_system": "api", "customer_id": "cust_444", "event_type": "purchase", "event_timestamp": now.isoformat(), "amount": "not_a_number", "currency": "USD", "ingestion_timestamp": now.isoformat()})

    with open(output_path, "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")
    print(f"Generated {len(records)} records to {output_path}")

if __name__ == "__main__":
    generate_sample_data()
