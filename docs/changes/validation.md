# validation changes (`src/demo_gx/validation/`)

> Format and discipline: see `docs/rules/DEVELOP-FLOW.md` section 4. Append-only; never rewrite past entries.

## 20260914 · extract-error-envelope — Move the quarantine error envelope out of the CLI

- **Motivation**: close the registered deviation "orchestration and transformation separation" (`AGENTS.md` section 10). `cli.py` was building the error envelope in place, so the entry point carried transformation logic.
- **Scope**: new `pipeline/validation/error_envelope.py`; `pipeline/cli.py` (the 24-line inline construction replaced by one call plus one import); `docs/business/MODULE-DESIGN.md` (section 1 module table, section 2.9 step 5, new section 2.10); `docs/business/INTERFACE-DESIGN.md` (section 4 classification owner); `docs/business/KNOWN-ISSUE.md` (entry `#cli-holds-transform` closed); `docs/business/PROJECT.md` and `AGENTS.md` section 10 (index rows removed).
- **Behaviour and contract changes**: none. Envelope field names, field order, the two-value classification rule, the filename stamp format, and the on-disk location are all unchanged. The log line still reports the directory rather than the file. `write_error_envelope` is a new module-level interface.
- **Verification**: `.venv/bin/python -m pytest tests/ -q` → 27 passed. End-to-end run `.venv/bin/python pipeline/cli.py --input data/sample_data.json --env test` → exit 0, envelope written with 4 rows and both `error_type` values present. Behaviour equivalence proved against the pre-change revision: 100 artefact fingerprints identical after dropping run-timestamp columns (`git stash` A/B run).
- **Rollback**: revert the commit. No data repair needed, because no output shape changed.
- **Related**: `CHANGELOG.md` entry for this date / `KNOWN-ISSUE.md#cli-holds-transform` / commit hash in `git log`.

## 20260914 · inject-run-timestamp — Future-timestamp rule uses the injected run instant

- **Motivation**: part of the `#now-timestamp` migration. Full entry lives in `docs/changes/engineering.md`.
- **Scope**: `pipeline/validation/schema_validator.py` only — `SchemaValidator.__init__` takes `run_ts`; the `<= current time` rule compares against it.
- **Behaviour and contract changes**: the constructor gains a required second parameter. The rule and its quarantine behaviour are unchanged; only its reference instant moved from the wall clock to the injected value.
- **Verification**: see the full entry in `docs/changes/engineering.md`.
- **Rollback**: revert the commit.
- **Related**: `docs/changes/engineering.md` (same date) / `KNOWN-ISSUE.md#now-timestamp`.

## 20260914 · verification-correction — Correct the first entry's envelope row count

- **Motivation**: the first entry above states the envelope held "4 rows". An independent audit re-ran it and measured 5. Neither number is a reproducible quantity: `scripts/generate_sample_data.py` varies `event_id` and every timestamp per run, so the row count tracks the fixture, not the code. Entry bodies stay untouched because this directory is append-only.
- **Scope**: documentation only. No code changed.
- **Behaviour and contract changes**: none.
- **Verification**: with the fixture held fixed, `rm -rf test/data && .venv/bin/python -m demo_gx.cli --input data/sample_data.json --env test --run-timestamp 2026-09-14T00:00:00Z` writes `test/data/errors/bad_schema/20260914T000000000000Z_errors.json` with 5 lines: 4 `schema_mismatch` and 1 `type_coercion_failed`. Field order is `original_json / error_type / error_details / ingestion_timestamp`. The reproducible claim is the invariant: the envelope carries all four fields in that order and both `error_type` values.
- **Rollback**: not applicable; documentation only.
- **Related**: `docs/changes/engineering.md` (same date, correction entry).

## 20260914 · verification-correction-2 — Correct the first entry's line count

- **Motivation**: the first entry above describes "the 24-line inline construction" that was moved out of the CLI. The change's own diff for `pipeline/cli.py` is 22 deletions and 5 insertions, a net of minus 17 lines, which is what the commit message states. The entry body stays untouched because this directory is append-only.
- **Scope**: documentation only. No code changed.
- **Behaviour and contract changes**: none.
- **Verification**: `git show --numstat 67ff35f -- pipeline/cli.py` prints `5  22  pipeline/cli.py`. The load-bearing claim of that entry is that the envelope construction moved out of the CLI and behaviour stayed identical; the exact line count is descriptive only.
- **Rollback**: not applicable; documentation only.
- **Related**: `docs/changes/engineering.md` (same date, `english-doc-assets`).
