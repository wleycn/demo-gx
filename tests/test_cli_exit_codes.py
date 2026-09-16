# [AI-GENERATED] model=deepseek-flash date=2026-09-15 reviewed_by=pending
"""Exit-code contract of the pipeline entry point.

INTERFACE-DESIGN.md section 1 is the single source for these codes. A scheduler
has to tell "ran and processed nothing" apart from "ran fine": without that, a
scope that matches no rows looks exactly like a successful run.

Every case runs the real entry point in a subprocess with ``STORAGE_BASE_PATH``
pointed at a temporary directory, so the test reads and writes its own artefacts
and never touches ``data/dev/output``.
"""

import json
import os
import pathlib
import subprocess
import sys
from typing import Any

REPO = pathlib.Path(__file__).resolve().parent.parent
RUN_TS = "2026-09-15T12:00:00Z"


def _row(**overrides: object) -> dict[str, Any]:
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


def _run(tmp_path: pathlib.Path, rows: list[dict[str, Any]], *args: str) -> subprocess.CompletedProcess[str]:
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


def test_a_clean_run_exits_zero(tmp_path: pathlib.Path) -> None:
    """The control case: every row survives and the artefacts are written."""

    result = _run(tmp_path, [_row()])
    assert result.returncode == 0, result.stdout + result.stderr
    metrics = json.loads((tmp_path / "storage" / "output" / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["silver_rows"] == 1


def test_a_date_scope_that_matches_nothing_exits_two(tmp_path: pathlib.Path) -> None:
    """Nothing in scope is not success: the caller must be able to see it."""

    result = _run(tmp_path, [_row()], "--event-date", "1999-01-01")
    assert result.returncode == 2, result.stdout + result.stderr


def test_a_run_where_every_row_is_quarantined_exits_three(tmp_path: pathlib.Path) -> None:
    """Zero valid rows means no Silver and no Gold, so it is not a plain success."""

    result = _run(tmp_path, [_row(customer_id=None), _row(event_id="223e4567-e89b-42d3-a456-426614174000", amount=-1)])
    assert result.returncode == 3, result.stdout + result.stderr
