# validation changes (`pipeline/validation/`)

> Format and discipline: see `docs/rules/DEVELOP-FLOW.md` section 4. Append-only; never rewrite past entries.

## 20260914 · extract-error-envelope — Move the quarantine error envelope out of the CLI

- **动机**: close the registered deviation "orchestration and transformation separation" (`AGENTS.md` section 10). `cli.py` was building the error envelope in place, so the entry point carried transformation logic.
- **范围**: new `pipeline/validation/error_envelope.py`; `pipeline/cli.py` (the 24-line inline construction replaced by one call plus one import); `docs/business/MODULE-DESIGN.md` (section 1 module table, section 2.9 step 5, new section 2.10); `docs/business/INTERFACE-DESIGN.md` (section 4 classification owner); `docs/business/KNOWN-ISSUE.md` (entry `#cli-holds-transform` closed); `docs/business/PROJECT.md` and `AGENTS.md` section 10 (index rows removed).
- **行为与契约变化**: none. Envelope field names, field order, the two-value classification rule, the filename stamp format, and the on-disk location are all unchanged. The log line still reports the directory rather than the file. `write_error_envelope` is a new module-level interface.
- **验证**: `.venv/bin/python -m pytest tests/ -q` → 27 passed. End-to-end run `.venv/bin/python pipeline/cli.py --input data/sample_data.json --env test` → exit 0, envelope written with 4 rows and both `error_type` values present. Behaviour equivalence proved against the pre-change revision: 100 artefact fingerprints identical after dropping run-timestamp columns (`git stash` A/B run).
- **回滚**: revert the commit. No data repair needed, because no output shape changed.
- **关联**: `CHANGELOG.md` entry for this date / `KNOWN-ISSUE.md#cli-holds-transform` / commit hash in `git log`.
