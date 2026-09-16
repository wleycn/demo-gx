# [AI-GENERATED] model=deepseek-flash date=2026-09-14 reviewed_by=pending
"""Bidirectional probes for ``scripts/show_data.py``.

A viewer that is never pointed at real data proves nothing: it may print the
same header whatever it reads. Every test below therefore pins the answer in
one direction. The compliant case must show the stored values, and each change
to the selection, the projection or the shape of the data must change what
appears on screen.

The probes also pin the two behaviours that separate this tool from
``check_data``: a contract deviation must *not* fail it, and an empty result
must *not* look like an error.

The tool is pointed at a throw-away project tree, so the probes never touch
``data/``.
"""

import json
from datetime import date
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import check_data
import show_data

CONTRACT = """# Table Contract: tiny_table

## Grain

One row per group.

## Field List

| Field | Type | Description |
|---|---|---|
| `event_date` | date | Partition column |
| `customer_id` | string | Masked customer |
| `n` | bigint | Count |
"""

FIRST = "h_" + "aa" * 8
SECOND = "h_" + "bb" * 8
THIRD = "h_" + "cc" * 8


def _config(env: str = "dev") -> dict[str, Any]:
    """Stand-in for ``load_config``: paths only, no filesystem read."""
    return {
        "storage": {
            "output_root": "data/dev/output",
            "input_root": "data/dev/input",
            "silver_subpath": "silver",
            "bronze_subpath": "bronze",
            "gold_subpath": "gold",
            "errors_subpath": "errors",
        },
        "metrics": {"output_file": "data/dev/output/metrics.json"},
        "pii": {"masked_fields": ["customer_id"]},
    }


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A project skeleton whose root the viewer is pointed at."""
    root = tmp_path / "proj"
    (root / "docs" / "tables").mkdir(parents=True)
    output = root / "data" / "dev" / "output"
    output.mkdir(parents=True)
    # A completed run always leaves this file; its presence is what tells the
    # viewer that there is anything to look at.
    (output / "metrics.json").write_text('{"silver_rows": 1}', encoding="utf-8")
    # Both modules resolve paths, so both roots must point at the throw-away
    # tree. They are one module attribute each, not two sources of truth.
    monkeypatch.setattr(show_data, "PROJECT_ROOT", root)
    monkeypatch.setattr(show_data, "load_config", _config)
    monkeypatch.setattr(check_data, "PROJECT_ROOT", root)
    monkeypatch.setattr(check_data, "load_config", _config)
    return root


def _output(project: Path) -> Path:
    return project / "data" / "dev" / "output"


def _write_contract(root: Path, name: str = "tiny_table") -> None:
    """Write one table contract under ``docs/tables``."""
    (root / "docs" / "tables" / f"{name}.md").write_text(CONTRACT, encoding="utf-8")


def _write_table(
    root: Path,
    name: str = "tiny_table",
    partitions: dict[date, list[str]] | None = None,
    rows: int = 5,
) -> None:
    """Write a partitioned Gold Parquet table, one masked id per partition."""
    partitions = partitions if partitions is not None else {date(2026, 1, 1): [FIRST] * rows}
    for day, ids in partitions.items():
        target = _output(root) / "gold" / name / f"event_date={day.isoformat()}"
        target.mkdir(parents=True, exist_ok=True)
        table = pa.table(
            {
                "event_date": pa.array([day] * len(ids), type=pa.date32()),
                "customer_id": pa.array(ids, type=pa.string()),
                "n": pa.array(range(1, len(ids) + 1), type=pa.int64()),
            }
        )
        pq.write_table(table, target / "data.parquet")


def _run(capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, str, str]:
    """Run the viewer and return its exit code with both output streams."""
    code = show_data.main(["--env", "dev", *args])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_stored_values_reach_the_screen(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The control case: the rows on disk must appear, not just a summary."""
    _write_contract(project)
    _write_table(project)
    code, out, _ = _run(capsys, "--layer", "gold", "--table", "tiny_table")
    assert code == 0
    assert FIRST in out
    assert "docs/tables/tiny_table.md" in out


def test_row_limit_is_respected(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """``--limit`` caps the rows shown, and says that it capped them."""
    _write_table(project)
    code, out, _ = _run(capsys, "--layer", "gold", "--table", "tiny_table", "--limit", "2")
    assert code == 0
    assert out.count(FIRST) == 2
    assert "stopped at the row limit" in out


def test_partitions_are_read_in_name_order_and_reported(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Read every partition when no date is given.

    The read starts at the first partition, and the line that names the source of
    the rows must not claim a single partition when more than one was read.
    """
    _write_table(project, partitions={date(2026, 1, 1): [FIRST], date(2026, 1, 2): [SECOND]})
    code, out, _ = _run(capsys, "--layer", "gold", "--table", "tiny_table")
    assert code == 0
    assert "2 partition(s) on disk; first event_date=2026-01-01" in out
    assert "rows from  event_date=2026-01-01 .. event_date=2026-01-02" in out
    assert FIRST in out
    assert SECOND in out


def test_event_date_selects_one_partition(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """``--event-date`` reads that partition and reports the selection."""
    _write_table(project, partitions={date(2026, 1, 1): [FIRST], date(2026, 1, 2): [SECOND]})
    code, out, _ = _run(capsys, "--layer", "gold", "--table", "tiny_table", "--event-date", "2026-01-02")
    assert code == 0
    assert "selected event_date=2026-01-02" in out
    assert SECOND in out
    assert FIRST not in out


def test_columns_are_projected(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """``--columns`` narrows what is read and what is shown."""
    _write_table(project)
    code, out, _ = _run(capsys, "--layer", "gold", "--table", "tiny_table", "--columns", "customer_id")
    assert code == 0
    assert "customer_id(string)" in out
    assert "n(int64)" not in out


def test_unknown_column_is_reported(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A column the artefact does not have must not print an empty table."""
    _write_table(project)
    code, out, _ = _run(capsys, "--layer", "gold", "--table", "tiny_table", "--columns", "ghost")
    assert code == 2
    assert "unknown column" in out


def test_unknown_table_is_reported(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Asking for a table that does not exist must not exit zero."""
    _write_table(project)
    code, out, _ = _run(capsys, "--layer", "gold", "--table", "ghost")
    assert code == 2
    assert "no table named 'ghost'" in out


def test_schema_mode_reads_no_rows(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """``--schema`` prints names and types, and no stored value at all."""
    _write_table(project)
    code, out, _ = _run(capsys, "--layer", "gold", "--table", "tiny_table", "--schema")
    assert code == 0
    assert "int64" in out
    assert "no rows read" in out
    assert FIRST not in out


def test_json_output_is_parseable(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """``--format json`` writes rows to stdout and the report to stderr."""
    _write_table(project)
    code, out, err = _run(capsys, "--layer", "gold", "--table", "tiny_table", "--limit", "2", "--format", "json")
    assert code == 0
    rows = json.loads(out)
    assert len(rows) == 2
    assert rows[0]["customer_id"] == FIRST
    assert "show-data" in err


def test_csv_output_has_a_header(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """``--format csv`` writes a header line the reader can rely on."""
    _write_table(project)
    code, out, _ = _run(capsys, "--layer", "gold", "--table", "tiny_table", "--format", "csv")
    assert code == 0
    assert out.splitlines()[0] == "event_date,customer_id,n"


def test_machine_format_needs_a_single_table(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Two tables in scope cannot share one JSON array, so that is refused."""
    _write_table(project)
    _write_table(project, name="other_table")
    code, out, _ = _run(capsys, "--layer", "gold", "--format", "json")
    assert code == 2
    assert "needs a single table" in out


def test_empty_partition_is_not_an_error(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """No matching rows is an answer, not a failure."""
    _write_table(project, partitions={date(2026, 1, 1): []})
    code, out, _ = _run(capsys, "--layer", "gold", "--table", "tiny_table")
    assert code == 0
    assert "no rows to show" in out


def test_environment_without_a_run_is_reported(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Nothing was ever written, so there is nothing to look at."""
    (_output(project) / "metrics.json").unlink()
    code, out, _ = _run(capsys, "--layer", "gold")
    assert code == 3
    assert "NOTHING TO SHOW" in out


def test_a_contract_deviation_does_not_fail_the_viewer(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Showing data and judging data are different jobs: this tool only shows."""
    _write_table(project, partitions={date(2026, 1, 1): ["cust_001"]})
    code, out, _ = _run(capsys, "--layer", "gold", "--table", "tiny_table")
    assert code == 0
    assert "cust_001" in out


def test_only_the_partitions_needed_are_read(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A small limit must stop early instead of reading every partition."""
    _write_table(
        project,
        partitions={
            date(2026, 1, 1): [FIRST],
            date(2026, 1, 2): [SECOND],
            date(2026, 1, 3): [THIRD],
        },
    )
    code, out, _ = _run(capsys, "--layer", "gold", "--table", "tiny_table", "--limit", "1")
    assert code == 0
    assert "1 of 3 file(s) read" in out


def test_bronze_layer_shows_raw_lines(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The raw archive is data too, so the viewer shows its lines."""
    target = _output(project) / "bronze" / "api" / "dt=2026-01-01"
    target.mkdir(parents=True)
    (target / "events.json").write_text('{"customer_id": "h_aaaa", "amount": 12.34}\n', encoding="utf-8")
    code, out, _ = _run(capsys, "--layer", "bronze")
    assert code == 0
    assert '"amount": 12.34' in out


def test_overview_covers_every_table(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """With no table named, every table in the layer is shown."""
    _write_table(project, partitions={date(2026, 1, 1): [FIRST]})
    _write_table(project, name="other_table", partitions={date(2026, 1, 1): [SECOND]})
    code, out, _ = _run(capsys, "--layer", "gold")
    assert code == 0
    assert "tiny_table" in out
    assert "other_table" in out
    assert FIRST in out
    assert SECOND in out
