# [AI-GENERATED] model=deepseek-flash date=2026-09-15 reviewed_by=pending
"""The two invariants that make a partition-level overwrite idempotent.

A scan of the write sites found six of them and two rules:

* Four wrote straight to the final path, so a crash mid-write destroyed the
  partition that was already there — and a reader cannot tell a truncated
  table from a complete one. Two others (the duplicates table and the error
  envelope) wrote through a temporary file.
* None of them cleared the partitions its run covered but produced no rows
  for, so a rerun that found no errors left the previous run's rows in place
  and the verifier kept reporting them.

Both live in ``demo_gx.common.storage`` now. These cases pin them: the
temporary-file move, the scope clearing, and the fact that a scope never
reaches outside itself (a scoped backfill must not touch other days).
"""

import pathlib
from datetime import date

import pandas as pd
import pytest

from demo_gx.common import storage


def _frame(dates: list[date], values: list[float]) -> pd.DataFrame:
    """A frame partitioned by ``event_date``."""

    return pd.DataFrame({"event_date": dates, "amount": values})


def _empty_frame() -> pd.DataFrame:
    """A frame with the partition column and no rows."""

    return pd.DataFrame({"event_date": pd.Series([], dtype="object"), "amount": pd.Series([], dtype="float64")})


def test_partition_value_renders_days_and_literals() -> None:
    """Dates render as ISO days; the quarantine's ``unknown`` stays a literal."""

    assert storage.partition_value(date(2026, 9, 10)) == "2026-09-10"
    assert storage.partition_value("unknown") == "unknown"


def test_single_file_table_leaves_no_temporary(tmp_path: pathlib.Path) -> None:
    """A single-file table is written through a temporary that is then moved."""

    root = tmp_path / "dim_customer"
    written = storage.write_table(_frame([date(2026, 9, 10)], [1.0]).drop(columns="event_date"), root)
    assert written == [root / "data.parquet"]
    assert (root / "data.parquet").exists()
    assert not list(root.rglob("*.tmp"))


def test_crash_mid_write_keeps_the_previous_partition(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A write that fails leaves the partition that was already there intact.

    Without the temporary-file move the failing write truncates the target
    first, which is exactly the state a partition overwrite must never leave.
    """

    root = tmp_path / "silver"
    storage.write_table(_frame([date(2026, 9, 10)], [1.0]), root, "event_date")
    target = root / "event_date=2026-09-10" / "data.parquet"
    before = target.read_bytes()

    def truncate_then_fail(self: pd.DataFrame, path: str | pathlib.Path, index: bool = False) -> None:
        pathlib.Path(path).write_bytes(b"")
        raise RuntimeError("disk full")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", truncate_then_fail)
    with pytest.raises(RuntimeError):
        storage.write_table(_frame([date(2026, 9, 10)], [2.0]), root, "event_date")

    assert target.read_bytes() == before
    assert pd.read_parquet(target)["amount"].tolist() == [1.0]
    assert not list(root.rglob("*.tmp"))


def test_scope_clears_the_partitions_that_lost_their_rows(tmp_path: pathlib.Path) -> None:
    """A partition inside the scope with no rows this run is removed."""

    root = tmp_path / "quarantine"
    storage.write_table(_frame([date(2026, 9, 10), date(2026, 9, 11)], [1.0, 2.0]), root, "event_date")
    storage.write_table(
        _frame([date(2026, 9, 10)], [3.0]),
        root,
        "event_date",
        scope=["2026-09-10", "2026-09-11"],
    )
    assert (root / "event_date=2026-09-10" / "data.parquet").exists()
    assert not (root / "event_date=2026-09-11").exists()


def test_scope_never_reaches_outside_itself(tmp_path: pathlib.Path) -> None:
    """A scoped run leaves other days alone (scoped backfill, DATA-DESIGN 2.6)."""

    root = tmp_path / "quarantine"
    storage.write_table(
        _frame([date(2026, 9, 10), date(2026, 9, 12)], [1.0, 2.0]),
        root,
        "event_date",
    )
    storage.write_table(_frame([date(2026, 9, 10)], [3.0]), root, "event_date", scope=["2026-09-10"])
    assert (root / "event_date=2026-09-12" / "data.parquet").exists()


def test_a_run_with_no_rows_leaves_no_table(tmp_path: pathlib.Path) -> None:
    """An empty scope-cleared table reads as absent, not as an empty directory."""

    root = tmp_path / "quarantine"
    storage.write_table(_frame([date(2026, 9, 10)], [1.0]), root, "event_date")
    written = storage.write_table(_empty_frame(), root, "event_date", scope=["2026-09-10"])
    assert written == []
    assert not root.exists()


def test_a_missing_partition_column_is_an_error(tmp_path: pathlib.Path) -> None:
    """Failing to partition is loud, because a silent one writes to one directory."""

    with pytest.raises(ValueError, match="partition column"):
        storage.write_table(_frame([date(2026, 9, 10)], [1.0]), tmp_path / "silver", "event_date_x")
