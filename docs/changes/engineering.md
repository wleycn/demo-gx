# engineering changes (build / deps / config / docs / tooling / gate)

> Format and discipline: see `docs/rules/DEVELOP-FLOW.md` section 4. Append-only; never rewrite past entries.

## 20260914 · extract-error-envelope — Pipeline entry point change

- **动机**: part of the `#cli-holds-transform` migration. Full entry lives in `docs/changes/validation.md`.
- **范围**: `pipeline/cli.py` only — the inline error-envelope construction was replaced by a call to `validation.error_envelope.write_error_envelope`, plus one import. `cli.py` is the pipeline entry point and has no module directory of its own, so the pointer is recorded here.
- **行为与契约变化**: none.
- **验证**: see the full entry in `docs/changes/validation.md`.
- **回滚**: revert the commit.
- **关联**: `docs/changes/validation.md` (same date) / `KNOWN-ISSUE.md#cli-holds-transform`.

## 20260914 · inject-run-timestamp — Inject the run timestamp at the entry boundary

- **动机**: close the registered deviation "partition parameter injection" (`AGENTS.md` section 10). Four places stamped data from the system clock, so re-running the same batch was not reproducible and the validator's future-timestamp rule depended on when it ran. Two of those four were outside the originally reported site; the whole class was fixed rather than only the reported pair.
- **范围**: `pipeline/cli.py` (new `--run-timestamp` flag, the run instant resolved once at the top of `main()` and threaded down); `pipeline/ingestion/reader.py` (`write_bronze(raw_df, bronze_base, run_ts)`); `pipeline/validation/schema_validator.py` (`SchemaValidator(schema_config, run_ts)`); `tests/test_validation.py` (fixed `RUN_TS` constant, `_ts(days_ago)` fixture helper, 16 constructor call sites, 8 timestamp literals); `docs/business/INTERFACE-DESIGN.md` section 1; `docs/business/MODULE-DESIGN.md` sections 1, 2.1, 2.2 and 2.9; `docs/business/KNOWN-ISSUE.md`; `docs/business/PROJECT.md`; `AGENTS.md` sections 1 and 10; `docs/changes/ingestion.md` and `docs/changes/validation.md` (pointer entries).
- **行为与契约变化**: two module signatures changed and are now required parameters. `write_bronze` takes `run_ts`; `SchemaValidator.__init__` takes `run_ts`. The CLI gains an optional `--run-timestamp`. Omitting the flag preserves the previous behaviour, apart from the read happening once at the boundary instead of at each stamp site. No output column, partition scheme, or file naming changed.
- **验证**: `.venv/bin/python -m pytest tests/ -q` → 27 passed. Behaviour equivalence against the previous revision: 100 artefact fingerprints identical after dropping run-timestamp columns. Reproducibility proved: two runs with `--run-timestamp 2026-09-14T00:00:00Z` produced byte-identical data artefacts (single aggregate hash `13d48407e55bdb13`); two runs without the flag differed, as expected. Injected value confirmed present in Silver `_processed_timestamp`, envelope `ingestion_timestamp`, and the envelope filename `20260914T000000000000Z_errors.json`.
- **回滚**: revert the commit. The `--run-timestamp` flag disappears with it and callers go back to the wall clock. No data repair needed.
- **关联**: `CHANGELOG.md` entry for this date / `KNOWN-ISSUE.md#now-timestamp` / commit hash in `git log`.
