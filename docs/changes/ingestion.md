# ingestion changes (`src/demo_gx/ingestion/`)

> Format and discipline: see `docs/rules/DEVELOP-FLOW.md` section 4. Append-only; never rewrite past entries.

(no entries yet: this directory records changes from its establishment onward; for prior history see `git log`)

## 20260914 · inject-run-timestamp — Bronze partition fallback no longer reads the clock

- **Motivation**: part of the `#now-timestamp` migration. Full entry lives in `docs/changes/engineering.md`.
- **Scope**: `pipeline/ingestion/reader.py` only — `write_bronze` takes `run_ts` and uses it as the partition-date fallback for rows with no parseable `ingestion_timestamp`.
- **Behaviour and contract changes**: `write_bronze` gains a required third parameter. Partition layout and the fallback value are unchanged; only its source moved from the wall clock to the injected run instant.
- **Verification**: see the full entry in `docs/changes/engineering.md`.
- **Rollback**: revert the commit.
- **Related**: `docs/changes/engineering.md` (same date) / `KNOWN-ISSUE.md#now-timestamp`.

## 20260914 · english-doc-assets — Pointer

- The change-entry field labels in this file were translated to English as part of the repository-wide language migration. The full entry lives in `docs/changes/engineering.md`.
