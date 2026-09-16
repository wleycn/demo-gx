# [AI-GENERATED] model=deepseek-flash date=2026-09-14 reviewed_by=pending
"""Bidirectional probes for ``scripts/check_data.py``.

A verifier that only ever sees compliant input proves nothing: it may be
incapable of failing. Every test below therefore pins the answer in one
direction. The compliant case must pass, and each injected defect must flip the
exit code and name the check that caught it.

The tool is pointed at a throw-away project tree, so the probes never touch
``data/``.
"""

from datetime import date
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import check_data

CONTRACT = """# Table Contract: tiny_table

## Grain

One row per group.

## Business Primary Key

Composite: (`event_date`, `customer_id`)

## Partition

`event_date` (date). Partition directory format: `event_date={YYYY-MM-DD}/data.parquet`.

## Field List

| Field | Type | Description |
|---|---|---|
| `event_date` | date | Partition column |
| `customer_id` | string | Masked customer |
| `n` | bigint | Count |
"""

SNAPSHOT_CONTRACT = CONTRACT.replace(
    "`event_date` (date). Partition directory format: `event_date={YYYY-MM-DD}/data.parquet`.",
    "None. Full snapshot, non-partitioned. Written as a single `data.parquet` file.",
)

MASKED = "h_" + "ab" * 8


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
    """A project skeleton whose root the verifier is pointed at."""

    root = tmp_path / "proj"
    (root / "docs" / "tables").mkdir(parents=True)
    output = root / "data" / "dev" / "output"
    output.mkdir(parents=True)

    # A completed run always leaves this file; its presence is what tells the
    # verifier that the environment has run at all.
    (output / "metrics.json").write_text('{"silver_rows": 1}', encoding="utf-8")
    monkeypatch.setattr(check_data, "PROJECT_ROOT", root)
    monkeypatch.setattr(check_data, "load_config", _config)
    return root


def _write_contract(root: Path, text: str = CONTRACT, name: str = "tiny_table") -> None:
    """Write one table contract under ``docs/tables``."""

    (root / "docs" / "tables" / f"{name}.md").write_text(text, encoding="utf-8")


def _write_table(
    root: Path,
    name: str = "tiny_table",
    dates: list[date] | None = None,
    customers: list[str] | None = None,
    counts: list[Any] | None = None,
    count_type: pa.DataType | None = None,
    extra: bool = False,
    omit: tuple[str, ...] = (),
    partition: bool = True,
) -> None:
    """Write a Gold Parquet table with the given shape."""

    target = root / "data" / "dev" / "output" / "gold" / name
    if partition:
        target = target / "event_date=2026-01-01"
    target.mkdir(parents=True, exist_ok=True)
    dates = dates if dates is not None else [date(2026, 1, 1)]
    customers = customers if customers is not None else [MASKED]
    counts = counts if counts is not None else [1]
    columns: dict[str, pa.Array] = {
        "event_date": pa.array(dates, type=pa.date32()),
        "customer_id": pa.array(customers, type=pa.string()),
        "n": pa.array(counts, type=count_type or pa.int64()),
    }
    if extra:
        columns["surprise"] = pa.array([0] * len(dates), type=pa.int64())
    for name in omit:
        columns.pop(name, None)
    pq.write_table(pa.table(columns), target / "data.parquet")


def _run(capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, str]:
    """Run the verifier and return its exit code with its report."""

    code = check_data.main(["--env", "dev", *args])
    return code, capsys.readouterr().out


def test_compliant_artefact_passes(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The control case: a clean table must report zero failures."""

    _write_contract(project)
    _write_table(project)
    code, out = _run(capsys, "--layer", "gold")
    assert code == 0
    assert "0 FAIL" in out
    assert "1 table(s) checked" in out


def test_undeclared_column_fails(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A column the contract does not declare must fail, not pass quietly."""

    _write_contract(project)
    _write_table(project, extra=True)
    code, out = _run(capsys, "--layer", "gold")
    assert code == 1
    assert "undeclared ['surprise']" in out


def test_declared_column_missing_fails(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The reverse direction: a contract field with no column must fail too."""

    _write_contract(project)
    _write_table(project, omit=("n",))
    code, out = _run(capsys, "--layer", "gold")
    assert code == 1
    assert "missing ['n']" in out


def test_type_drift_fails(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A stored type outside the contract's equivalence set must fail."""

    _write_contract(project)
    _write_table(project, counts=["1"], count_type=pa.string())
    code, out = _run(capsys, "--layer", "gold")
    assert code == 1
    assert "n: string not in ['int64']" in out


def test_duplicate_primary_key_fails(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The declared business primary key must be unique over the table."""

    _write_contract(project)
    _write_table(project, dates=[date(2026, 1, 1)] * 2, customers=[MASKED] * 2, counts=[1, 2])
    code, out = _run(capsys, "--layer", "gold")
    assert code == 1
    assert "1 duplicate row(s)" in out


def test_plaintext_pii_fails(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A configured PII column that is not a digest must fail."""

    _write_contract(project)
    _write_table(project, customers=["cust_001"])
    code, out = _run(capsys, "--layer", "gold")
    assert code == 1
    assert "not masked" in out


def test_snapshot_contract_with_partitions_fails(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A snapshot contract that meets partition directories must fail."""

    _write_contract(project, SNAPSHOT_CONTRACT)
    _write_table(project, partition=True)
    code, out = _run(capsys, "--layer", "gold")
    assert code == 1
    assert "declares no partition" in out


def test_missing_contract_warns_without_failing(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """No contract is a warning: the artefacts are still worth reporting."""

    _write_table(project)
    code, out = _run(capsys, "--layer", "gold")
    assert code == 0
    assert "no docs/tables document" in out
    assert "1 WARN" in out


def test_empty_scope_is_not_a_pass(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Scanning nothing must not look like scanning everything."""

    code, out = _run(capsys, "--layer", "gold")
    assert code == 3
    assert "NOT SCANNED" in out


def test_environment_without_a_run_is_skipped(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """An environment that never ran is a skip, not a failure."""

    (project / "data" / "dev" / "output" / "metrics.json").unlink()
    code, out = _run(capsys, "--layer", "all")
    assert code == 3
    assert "has never run" in out


def test_contract_without_an_artefact_fails(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Once a run happened, a declared table that is absent must fail."""

    _write_contract(project)
    _write_contract(project, CONTRACT, name="ghost_table")
    _write_table(project)
    code, out = _run(capsys, "--layer", "gold")
    assert code == 1
    assert "gold/ghost_table" in out


def test_unknown_table_is_reported(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Asking for a table that does not exist must not exit zero."""

    _write_contract(project)
    _write_table(project)
    code, out = _run(capsys, "--layer", "gold", "--table", "ghost")
    assert code == 2
    assert "no table named 'ghost'" in out


def test_an_absent_error_table_reports_no_records(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """No error table means no errors, which is a pass.

    The pipeline clears the days a run covers that produced no errors, so an
    absent table is the normal state of a clean run. Failing it made the best
    possible outcome — nothing rejected, nothing duplicated — the one that
    broke CI (audit finding, 2026-09-15).
    """

    code, out = _run(capsys, "--layer", "errors")
    assert code == 0, out
    assert "no records" in out
    assert "0 FAIL" in out


def test_a_scoped_absent_error_table_is_also_a_pass(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The same rule holds when the check names one partition."""

    code, out = _run(capsys, "--layer", "errors", "--event-date", "2026-01-01")
    assert code == 0, out
    assert "no records for event_date=2026-01-01" in out


def test_currency_corrections_are_reported(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The cleaning step's own flag is reported, not just written.

    ``normalize_currency`` replaces an invalid code with USD and sets
    ``_is_invalid_currency``, and the contract documents that column. Nothing
    reported it, so the substitution was invisible to whoever reads the report.
    """

    contract = CONTRACT.replace(
        "| `n` | bigint | Count |",
        "| `n` | bigint | Count |\n| `_is_invalid_currency` | boolean | Corrected code |",
    )
    _write_contract(project, contract)
    target = project / "data" / "dev" / "output" / "gold" / "tiny_table" / "event_date=2026-01-01"
    target.mkdir(parents=True)
    pq.write_table(
        pa.table(
            {
                "event_date": pa.array([date(2026, 1, 1)], type=pa.date32()),
                "customer_id": pa.array([MASKED], type=pa.string()),
                "n": pa.array([1], type=pa.int64()),
                "_is_invalid_currency": pa.array([True], type=pa.bool_()),
            }
        ),
        target / "data.parquet",
    )
    code, out = _run(capsys, "--layer", "gold")
    assert code == 0, out
    assert "1 row(s) had an invalid code" in out
    assert "100.0% of rows" in out
