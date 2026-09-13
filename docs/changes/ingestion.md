# ingestion changes (`pipeline/ingestion/`)

> Format and discipline: see `docs/rules/DEVELOP-FLOW.md` section 4. Append-only; never rewrite past entries.

(no entries yet: this directory records changes from its establishment onward; for prior history see `git log`)

## 20260914 · inject-run-timestamp — Bronze partition fallback no longer reads the clock

- **动机**: part of the `#now-timestamp` migration. Full entry lives in `docs/changes/engineering.md`.
- **范围**: `pipeline/ingestion/reader.py` only — `write_bronze` takes `run_ts` and uses it as the partition-date fallback for rows with no parseable `ingestion_timestamp`.
- **行为与契约变化**: `write_bronze` gains a required third parameter. Partition layout and the fallback value are unchanged; only its source moved from the wall clock to the injected run instant.
- **验证**: see the full entry in `docs/changes/engineering.md`.
- **回滚**: revert the commit.
- **关联**: `docs/changes/engineering.md` (same date) / `KNOWN-ISSUE.md#now-timestamp`.
