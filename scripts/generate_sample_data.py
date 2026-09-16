# [AI-GENERATED] model=deepseek-flash date=2026-09-09 reviewed_by=pending
"""Sample data generator for the pipeline.

Generates a representative JSON Lines file with valid records plus
intentionally anomalous records (missing field, negative amount, invalid
enum, future timestamp, duplicate event_id) for testing validation,
cleaning, and deduplication logic.

The output is byte-stable: it is derived from a seeded generator and a fixed
base instant, so regenerating it never produces a spurious diff and the
pinned-timestamp commands in the docs stay reproducible.
"""

import argparse
import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# Base instant for every generated timestamp. Fixed on purpose: a sample built
# from the wall clock cannot be committed (it would show a diff on every
# regeneration) and cannot be replayed by a command that pins --run-timestamp.
# The instant is deliberately offset-free: the input contract carries the raw
# timestamp as a string and the Silver layer types it as UTC, so a tzinfo here
# would change the generated payload.
_BASE_TS = datetime(2026, 9, 14, 0, 0, 0)  # noqa: DTZ001


def _det_uuid(rng: random.Random) -> str:
    """Return a version-4 UUID drawn from ``rng`` instead of the OS entropy pool.

    The schema requires the v4 shape (``^[0-9a-f]{8}-...-4...-[89ab]...$``);
    ``UUID(int=..., version=4)`` stamps the version and variant bits, so the
    value stays schema-valid while remaining reproducible.
    """

    return str(uuid.UUID(int=rng.getrandbits(128), version=4))


def generate_sample_data(
    num_records: int = 100,
    output_path: str | None = None,
    env: str = "dev",
    seed: int = 42,
) -> None:
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
        output_path (str | None): Path to the output JSON Lines file.
            Defaults to ``data/{env}/input/sample_data.json`` — the inbound
            drop location of the selected environment.
        env (str): Environment whose input directory receives the file when
            ``output_path`` is omitted.  One of ``dev``, ``test``, ``prod``.
        seed (int): Seed for the private generator instance that drives every
            random draw.  Defaults to 42.  Changing it changes the sample.

    Note:
        The ``ingestion_timestamp`` of every record is ``_BASE_TS``, which is
        earlier than the ``--run-timestamp`` used in the docs.  That ordering
        matters: the validator rejects records ingested later than the run
        instant, so a sample stamped with the wall clock would be rejected
        wholesale by any replay command that pins an older timestamp.
    """

    if output_path is None:
        output_path = f"data/{env}/input/sample_data.json"
    records = []

    # A private generator instance: importing this module must never disturb
    # the global random state that a caller may rely on.
    rng = random.Random(seed)
    base = _BASE_TS
    systems = ["web", "mobile", "api"]

    # XXX passes the schema's ^[A-Z]{3}$ format check but is not in the
    # cleaner whitelist → it exercises the normalize-to-USD + flag path
    currencies = ["USD", "EUR", "GBP", "CNY", "JPY", "XXX"]
    event_types = ["purchase", "view", "click", "signup", "login"]
    for _ in range(num_records):
        rec = {
            "event_id": _det_uuid(rng),
            "source_system": rng.choice(systems),
            "customer_id": f"cust_{rng.randint(1, 50):03d}",
            "event_type": rng.choice(event_types),
            "event_timestamp": (base - timedelta(days=rng.randint(0, 30), hours=rng.randint(0, 23))).isoformat(),
            "amount": round(rng.uniform(0, 1000), 2),
            "currency": rng.choice(currencies),
            "ingestion_timestamp": base.isoformat(),
        }
        records.append(rec)

    # Intentionally add some anomalous records
    # 1. Missing event_id
    records.append(
        {
            "source_system": "web",
            "customer_id": "cust_999",
            "event_type": "purchase",
            "event_timestamp": base.isoformat(),
            "amount": 10,
            "currency": "USD",
            "ingestion_timestamp": base.isoformat(),
        }
    )

    # 2. Invalid amount (negative)
    records.append(
        {
            "event_id": _det_uuid(rng),
            "source_system": "api",
            "customer_id": "cust_888",
            "event_type": "view",
            "event_timestamp": base.isoformat(),
            "amount": -5,
            "currency": "USD",
            "ingestion_timestamp": base.isoformat(),
        }
    )

    # 3. Invalid source_system
    records.append(
        {
            "event_id": _det_uuid(rng),
            "source_system": "unknown",
            "customer_id": "cust_777",
            "event_type": "click",
            "event_timestamp": base.isoformat(),
            "amount": 20,
            "currency": "EUR",
            "ingestion_timestamp": base.isoformat(),
        }
    )

    # 4. Future timestamp
    records.append(
        {
            "event_id": _det_uuid(rng),
            "source_system": "mobile",
            "customer_id": "cust_666",
            "event_type": "login",
            "event_timestamp": (base + timedelta(days=1)).isoformat(),
            "amount": 0,
            "currency": "GBP",
            "ingestion_timestamp": base.isoformat(),
        }
    )

    # 5. Duplicate event_id
    dup_id = _det_uuid(rng)
    records.append(
        {
            "event_id": dup_id,
            "source_system": "web",
            "customer_id": "cust_555",
            "event_type": "signup",
            "event_timestamp": (base - timedelta(hours=1)).isoformat(),
            "amount": 0,
            "currency": "USD",
            "ingestion_timestamp": base.isoformat(),
        }
    )
    records.append(
        {
            "event_id": dup_id,
            "source_system": "web",
            "customer_id": "cust_555",
            "event_type": "signup",
            "event_timestamp": (base - timedelta(hours=2)).isoformat(),
            "amount": 0,
            "currency": "USD",
            "ingestion_timestamp": (base - timedelta(hours=1)).isoformat(),
        }
    )

    # 6. Non-numeric amount (exercises error_type=type_coercion_failed)
    records.append(
        {
            "event_id": _det_uuid(rng),
            "source_system": "api",
            "customer_id": "cust_444",
            "event_type": "purchase",
            "event_timestamp": base.isoformat(),
            "amount": "not_a_number",
            "currency": "USD",
            "ingestion_timestamp": base.isoformat(),
        }
    )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")
    print(f"Generated {len(records)} records to {output_path}")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the generator's command-line arguments."""

    parser = argparse.ArgumentParser(description="Generate sample pipeline input.")
    parser.add_argument(
        "--env", default="dev", choices=["dev", "test", "prod"], help="Environment input directory to write into"
    )
    parser.add_argument("--output", help="Explicit output path; overrides --env")
    parser.add_argument("--records", type=int, default=100, help="Number of valid random records to generate")
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()
    generate_sample_data(num_records=args.records, output_path=args.output, env=args.env)
