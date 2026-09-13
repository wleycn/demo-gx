# engineering changes (build / deps / config / docs / tooling / gate)

> Format and discipline: see `docs/rules/DEVELOP-FLOW.md` section 4. Append-only; never rewrite past entries.

## 20260914 · extract-error-envelope — Pipeline entry point change

- **动机**: part of the `#cli-holds-transform` migration. Full entry lives in `docs/changes/validation.md`.
- **范围**: `pipeline/cli.py` only — the inline error-envelope construction was replaced by a call to `validation.error_envelope.write_error_envelope`, plus one import. `cli.py` is the pipeline entry point and has no module directory of its own, so the pointer is recorded here.
- **行为与契约变化**: none.
- **验证**: see the full entry in `docs/changes/validation.md`.
- **回滚**: revert the commit.
- **关联**: `docs/changes/validation.md` (same date) / `KNOWN-ISSUE.md#cli-holds-transform`.
