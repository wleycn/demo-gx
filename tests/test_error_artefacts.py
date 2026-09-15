# [AI-GENERATED] model=deepseek-flash date=2026-09-15 reviewed_by=pending
"""Layout and idempotency of the error artefacts: the quarantine and the duplicates.

Both used to be one new file per run (an envelope stamped with the run instant)
and an appended plain-text log. Every rerun therefore changed the artefacts, and
the counts the verifier reported were sums across runs: the same repository state
reported different numbers depending on how often the pipeline had been run.

They are now partitioned tables under ``errors/``, overwritten per partition like
every other artefact. The partition key is the record's own event date, so a
scoped backfill replaces one day and leaves the others alone.

INTERFACE-DESIGN.md section 4 is the single source for the envelope fields.

Each case runs the real entry point in a subprocess with ``STORAGE_BASE_PATH``
pointed at a temporary directory, so the test reads and writes its own artefacts
and never touches ``data/dev/output``.
"""

import json
import os
import pathlib
import subprocess
import sys

import pandas as pd

REPO = pathlib.Path(__file__).resolve().parent.parent
RUN_TS = "2026-09-15T12:00:00Z"
ENVELOPE_FIELDS = ("original_json", "error_type", "error_details", "ingestion_timestamp")


def _row(**overrides) -> dict:
    """One well-formed record; override any field for edge cases."""
    row = {
        "event_id": "123e4567-e89b-42d3-a456-426614174000",
        "source_system": "web",
        "customer_id": "cust_001",
        "event_type": "purchase",
        "event_timestamp": "2026-09-10T10:00:00Z",
        "amount": 100.0,
        "currency": "USD",
        "ingestion_timestamp": "2026-09-10T10:01:00Z",
    }
    row.update(overrides)
    return row


def _run(tmp_path: pathlib.Path, rows: list[dict], *args: str) -> subprocess.CompletedProcess:
    """Run the pipeline over ``rows`` with every artefact kept in ``tmp_path``."""
    source = tmp_path / "input.json"
    source.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    env = dict(os.environ)
    env["STORAGE_BASE_PATH"] = str(tmp_path / "storage")
    return subprocess.run(
        [sys.executable, "-m", "demo_gx.cli", "--env", "dev", "--input", str(source), "--run-timestamp", RUN_TS, *args],
        cwd=REPO,
        capture_output=True,
        text=True,
        env=env,
    )


def _partitions(tmp_path: pathlib.Path, name: str) -> dict[str, pd.DataFrame]:
    """Read one partitioned error table, keyed by partition directory name."""
    root = tmp_path / "storage" / "output" / "errors" / name
    return {path.parent.name: pd.read_parquet(path) for path in sorted(root.glob("event_date=*/data.parquet"))}


def _batch() -> list[dict]:
    """Two quarantined rows on different dates plus one superseded duplicate."""
    return [
        _row(event_id="323e4567-e89b-42d3-a456-426614174001", customer_id=None),
        _row(
            event_id="423e4567-e89b-42d3-a456-426614174002",
            event_timestamp="2026-09-11T10:00:00Z",
            ingestion_timestamp="2026-09-11T10:01:00Z",
            source_system="nope",
        ),
        _row(event_id="523e4567-e89b-42d3-a456-426614174003"),
        _row(event_id="523e4567-e89b-42d3-a456-426614174003", ingestion_timestamp="2026-09-10T10:02:00Z"),
    ]


def test_a_second_identical_run_does_not_grow_the_error_artefacts(tmp_path: pathlib.Path) -> None:
    """A rerun of the same batch leaves the quarantine and the duplicates unchanged."""
    result = _run(tmp_path, _batch())
    assert result.returncode == 0, result.stdout + result.stderr
    quarantine = {name: len(frame) for name, frame in _partitions(tmp_path, "quarantine").items()}
    duplicates = {name: len(frame) for name, frame in _partitions(tmp_path, "duplicates").items()}
    assert quarantine and duplicates, "the batch should produce both artefacts"
    envelope = _partitions(tmp_path, "quarantine")["event_date=2026-09-10"]
    assert set(ENVELOPE_FIELDS).issubset(envelope.columns), envelope.columns.tolist()

    _run(tmp_path, _batch())

    assert {name: len(frame) for name, frame in _partitions(tmp_path, "quarantine").items()} == quarantine
    assert {name: len(frame) for name, frame in _partitions(tmp_path, "duplicates").items()} == duplicates


def test_a_scoped_run_leaves_another_dates_quarantine_alone(tmp_path: pathlib.Path) -> None:
    """`--event-date` replaces its own partition and touches no other date."""
    _run(tmp_path, _batch())
    before = {name: len(frame) for name, frame in _partitions(tmp_path, "quarantine").items()}
    assert set(before) == {"event_date=2026-09-10", "event_date=2026-09-11"}, before

    _run(tmp_path, _batch(), "--event-date", "2026-09-10")

    after = {name: len(frame) for name, frame in _partitions(tmp_path, "quarantine").items()}
    assert after["event_date=2026-09-11"] == before["event_date=2026-09-11"]
    assert after["event_date=2026-09-10"] == before["event_date=2026-09-10"]


def test_a_row_with_an_unparseable_timestamp_gets_its_own_partition(tmp_path: pathlib.Path) -> None:
    """A record with no usable event date is quarantined, never dropped."""
    result = _run(tmp_path, [_row(event_id="623e4567-e89b-42d3-a456-426614174004", event_timestamp="not-a-timestamp")])
    assert result.returncode == 3, result.stdout + result.stderr
    partitions = _partitions(tmp_path, "quarantine")
    assert set(partitions) == {"event_date=unknown"}, partitions
    assert len(partitions["event_date=unknown"]) == 1
