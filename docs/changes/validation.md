# validation changes (`src/demo_gx/validation/`)

> Format and discipline: see `docs/rules/DEVELOP-FLOW.md` section 4. Append-only; never rewrite past entries.

## 20260914 · extract-error-envelope — Move the quarantine error envelope out of the CLI

- **动机**: close the registered deviation "orchestration and transformation separation" (`AGENTS.md` section 10). `cli.py` was building the error envelope in place, so the entry point carried transformation logic.
- **范围**: new `pipeline/validation/error_envelope.py`; `pipeline/cli.py` (the 24-line inline construction replaced by one call plus one import); `docs/business/MODULE-DESIGN.md` (section 1 module table, section 2.9 step 5, new section 2.10); `docs/business/INTERFACE-DESIGN.md` (section 4 classification owner); `docs/business/KNOWN-ISSUE.md` (entry `#cli-holds-transform` closed); `docs/business/PROJECT.md` and `AGENTS.md` section 10 (index rows removed).
- **行为与契约变化**: none. Envelope field names, field order, the two-value classification rule, the filename stamp format, and the on-disk location are all unchanged. The log line still reports the directory rather than the file. `write_error_envelope` is a new module-level interface.
- **验证**: `.venv/bin/python -m pytest tests/ -q` → 27 passed. End-to-end run `.venv/bin/python pipeline/cli.py --input data/sample_data.json --env test` → exit 0, envelope written with 4 rows and both `error_type` values present. Behaviour equivalence proved against the pre-change revision: 100 artefact fingerprints identical after dropping run-timestamp columns (`git stash` A/B run).
- **回滚**: revert the commit. No data repair needed, because no output shape changed.
- **关联**: `CHANGELOG.md` entry for this date / `KNOWN-ISSUE.md#cli-holds-transform` / commit hash in `git log`.

## 20260914 · inject-run-timestamp — Future-timestamp rule uses the injected run instant

- **动机**: part of the `#now-timestamp` migration. Full entry lives in `docs/changes/engineering.md`.
- **范围**: `pipeline/validation/schema_validator.py` only — `SchemaValidator.__init__` takes `run_ts`; the `<= current time` rule compares against it.
- **行为与契约变化**: the constructor gains a required second parameter. The rule and its quarantine behaviour are unchanged; only its reference instant moved from the wall clock to the injected value.
- **验证**: see the full entry in `docs/changes/engineering.md`.
- **回滚**: revert the commit.
- **关联**: `docs/changes/engineering.md` (same date) / `KNOWN-ISSUE.md#now-timestamp`.

## 20260914 · verification-correction — Correct the first entry's envelope row count

- **动机**: the first entry above states the envelope held "4 rows". An independent audit re-ran it and measured 5. Neither number is a reproducible quantity: `scripts/generate_sample_data.py` varies `event_id` and every timestamp per run, so the row count tracks the fixture, not the code. Entry bodies stay untouched because this directory is append-only.
- **范围**: documentation only. No code changed.
- **行为与契约变化**: none.
- **验证**: with the fixture held fixed, `rm -rf test/data && .venv/bin/python -m demo_gx.cli --input data/sample_data.json --env test --run-timestamp 2026-09-14T00:00:00Z` writes `test/data/errors/bad_schema/20260914T000000000000Z_errors.json` with 5 lines: 4 `schema_mismatch` and 1 `type_coercion_failed`. Field order is `original_json / error_type / error_details / ingestion_timestamp`. The reproducible claim is the invariant: the envelope carries all four fields in that order and both `error_type` values.
- **回滚**: not applicable; documentation only.
- **关联**: `docs/changes/engineering.md` (same date, correction entry).
