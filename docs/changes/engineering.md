# engineering changes (build / deps / config / docs / tooling / gate)

> Format and discipline: see `docs/rules/DEVELOP-FLOW.md` section 4. Append-only; never rewrite past entries.

## 20260914 · extract-error-envelope — Pipeline entry point change

- **Motivation**: part of the `#cli-holds-transform` migration. Full entry lives in `docs/changes/validation.md`.
- **Scope**: `pipeline/cli.py` only — the inline error-envelope construction was replaced by a call to `validation.error_envelope.write_error_envelope`, plus one import. `cli.py` is the pipeline entry point and has no module directory of its own, so the pointer is recorded here.
- **Behaviour and contract changes**: none.
- **Verification**: see the full entry in `docs/changes/validation.md`.
- **Rollback**: revert the commit.
- **Related**: `docs/changes/validation.md` (same date) / `KNOWN-ISSUE.md#cli-holds-transform`.

## 20260914 · inject-run-timestamp — Inject the run timestamp at the entry boundary

- **Motivation**: close the registered deviation "partition parameter injection" (`AGENTS.md` section 10). Four places stamped data from the system clock, so re-running the same batch was not reproducible and the validator's future-timestamp rule depended on when it ran. Two of those four were outside the originally reported site; the whole class was fixed rather than only the reported pair.
- **Scope**: `pipeline/cli.py` (new `--run-timestamp` flag, the run instant resolved once at the top of `main()` and threaded down); `pipeline/ingestion/reader.py` (`write_bronze(raw_df, bronze_base, run_ts)`); `pipeline/validation/schema_validator.py` (`SchemaValidator(schema_config, run_ts)`); `tests/test_validation.py` (fixed `RUN_TS` constant, `_ts(days_ago)` fixture helper, 16 constructor call sites, 8 timestamp literals); `docs/business/INTERFACE-DESIGN.md` section 1; `docs/business/MODULE-DESIGN.md` sections 1, 2.1, 2.2 and 2.9; `docs/business/KNOWN-ISSUE.md`; `docs/business/PROJECT.md`; `AGENTS.md` sections 1 and 10; `docs/changes/ingestion.md` and `docs/changes/validation.md` (pointer entries).
- **Behaviour and contract changes**: two module signatures changed and are now required parameters. `write_bronze` takes `run_ts`; `SchemaValidator.__init__` takes `run_ts`. The CLI gains an optional `--run-timestamp`. Omitting the flag preserves the previous behaviour, apart from the read happening once at the boundary instead of at each stamp site. No output column, partition scheme, or file naming changed.
- **Verification**: `.venv/bin/python -m pytest tests/ -q` → 27 passed. Behaviour equivalence against the previous revision: 100 artefact fingerprints identical after dropping run-timestamp columns. Reproducibility proved: two runs with `--run-timestamp 2026-09-14T00:00:00Z` produced byte-identical data artefacts (single aggregate hash `13d48407e55bdb13`); two runs without the flag differed, as expected. Injected value confirmed present in Silver `_processed_timestamp`, envelope `ingestion_timestamp`, and the envelope filename `20260914T000000000000Z_errors.json`.
- **Rollback**: revert the commit. The `--run-timestamp` flag disappears with it and callers go back to the wall clock. No data repair needed.
- **Related**: `CHANGELOG.md` entry for this date / `KNOWN-ISSUE.md#now-timestamp` / commit hash in `git log`.

## 20260914 · src-layout-package — Move to an installable src/demo_gx package

- **Motivation**: close the registered deviation "source directory layout" (`AGENTS.md` section 10). `pipeline/` used flat namespace packages with no `__init__.py`, so the code could not be installed and imports depended on the working directory being the project root. The same pass recorded the remaining deltas between this project and the data-processing structural skeleton.
- **Scope**: `pipeline/` to `src/demo_gx/` via `git mv` (history preserved) plus `__init__.py` in the package and each subpackage; 17 intra-package imports rewritten to `demo_gx.*`; `common/config.py` root anchor `parents[2]` to `parents[3]`; `common/logger.py` logger name `pipeline` to `demo_gx` behind a `LOGGER_NAME` constant; new `pyproject.toml`; removed `requirements.txt` and `pytest.ini`, both consolidated into `pyproject.toml`; `Makefile`; `.gitlab-ci.yml`; `.gitignore`; `README.md`; `AGENTS.md` sections 1, 6, 9.1 and 10; `docs/business/PROJECT.md`, `MODULE-DESIGN.md`, `INTERFACE-DESIGN.md`, `DOMAIN-LANGUAGE.md`, `KNOWN-ISSUE.md`; the six `docs/changes/*.md` file headers.
- **Behaviour and contract changes**: the entry point is now `python -m demo_gx.cli` instead of `python pipeline/cli.py`. Dependencies moved from `requirements.txt` to `pyproject.toml`; the install step is `pip install -e ".[dev]"`. Log lines carry `"logger": "demo_gx"` instead of `"pipeline"`. No data output, partition scheme, or CLI flag changed.
- **Verification**: `.venv/bin/python -m pytest tests/ -q` → 27 passed, run both from the project root and from `/tmp`. `python -m demo_gx.cli --input data/sample_data.json --env test` → exit 0. Import from `/tmp` resolves the package and yields `PROJECT_ROOT = /home/hermes/workspace/demo-gx`. Behaviour equivalence against the previous revision: 100 artefact fingerprints identical after dropping run-timestamp columns. Reproducibility unchanged: two injected-timestamp runs share the aggregate hash `13d48407e55bdb13`.
- **Rollback**: revert the commit. `git mv` reverses cleanly and `requirements.txt` / `pytest.ini` return. No data repair needed.
- **Related**: `CHANGELOG.md` entry for this date / `KNOWN-ISSUE.md#layout-flat-pipeline` / commit hash in `git log`.

> Historical entries in this directory and in `validation.md` / `ingestion.md` name files under `pipeline/`. That was this package's path before 20260914. Entry bodies are append-only and are not rewritten.

## 20260914 · verification-correction — Correct the verification claims in the three entries above

- **Motivation**: an independent read-only audit of the three entries above found verification claims a reader cannot reproduce as written. Entry bodies stay untouched because this directory is append-only; the corrections are recorded here instead.
- **Scope**: documentation only, plus one comment in `scripts/generate_sample_data.py`. No pipeline code, config, or output shape changed.
- **Behaviour and contract changes**: none. The audited re-runs confirmed every underlying behaviour; what was wrong was the wording of the evidence.
- **Verification**: four corrections. Each was re-run before being written here.
  1. **The aggregate hash `13d48407e55bdb13` is not reproducible and is withdrawn.** It was measured against a `data/sample_data.json` that no longer exists: `make run` depends on the `data` target, which regenerates that file, and `scripts/generate_sample_data.py` varies `event_id` (uuid4) and every timestamp per run. The reproducible statement is the invariant, with the fixture held fixed: two runs of `rm -rf test/data && .venv/bin/python -m demo_gx.cli --input data/sample_data.json --env test --run-timestamp 2026-09-14T00:00:00Z` give identical `sha256sum` manifests over `find test/data -type f ! -path "*/logs/*" ! -name metrics.json` — 101 files, empty `diff`.
  2. **The artefact count in the equivalence check is fixture-dependent, not a fixed 100.** The count in the first entry was measured on the fixture present then. The method is the reproducible part: `git stash` the change, run both revisions against the same fixed fixture, compare fingerprints after dropping run-timestamp columns. Every fingerprint matched.
  3. **"27 passed from `/tmp`" needs the absolute path**: `cd /tmp && /home/hermes/workspace/demo-gx/.venv/bin/python -m pytest /home/hermes/workspace/demo-gx/tests -q` gives 27 passed. A bare `pytest tests/` from `/tmp` collects nothing.
  4. **The end-to-end command is `python -m demo_gx.cli`** after the package move. `pipeline/cli.py` no longer exists, so the command quoted in the first two entries no longer runs as written.
- **Rollback**: not applicable; documentation only.
- **Related**: `docs/changes/validation.md` (same date, correction entry) / commit hash in `git log`.

## 20260914 · english-doc-assets — Move the whole repository to English

- **Motivation**: the repository is delivered to English-speaking readers, but eight tracked files still carried Chinese. Four of them (`AGENTS.md` and the `docs/rules/` set) are assembled verbatim from the upstream material library, so editing them in place would have forked the single source and broken the assembly-consistency check. The upstream library therefore gained a language layer, and this repository was re-assembled from it.
- **Scope**: upstream material library — new `references/rules/en/` and `references/AGENTS/en/` mirror layers (11 files); `rules_assembly.py` (`--lang`, sparse-mirror resolution, fail-closed preflight, cross-language skeleton parity); `agents_assembly.py` (`--lang`, per-language section list, cross-language section-number parity); `verify_rules_layering.py` (`--lang`, per-language type keywords and skip markers); `pre_commit_gate.py` (the `AGENTS.md` section check is now by section number and therefore language-neutral). This repository — `AGENTS.md` regenerated, the four `docs/rules/` files re-assembled, the change-entry field labels in `docs/changes/` translated, `README.md` gate description corrected, `docs/business/INTERFACE-DESIGN.md`, `docs/business/PROJECT.md`, `docs/business/KNOWN-ISSUE.md`, `docs/changes/engineering.md`.
- **Behaviour and contract changes**: none in the pipeline; documentation and tooling only. Two contract-level points. First, the change-entry field labels are now English: Motivation / Scope / Behaviour and contract changes / Verification / Rollback / Related. Second, `AGENTS.md` section 10 gained a deviation row for the remaining telemetry clock reads, plus cost-and-rollback notes for every row.
- **Verification**: `.venv/bin/python -m pytest tests/ -q` to 27 passed. `pre_commit_gate.py --repo . --agents-strict` to exit 0 with zero warnings. `rules_assembly.py --stack python --type data-processing --lang en --check .` to all four files identical to the upstream assembly. `verify_rules_layering.py --lang en --project . --stack python --type data-processing` to B1/B2/C1/D1/E1 all zero. `agents_assembly.py --type data-processing --lang en --check` to pass, including the cross-language section-number parity check. Chinese-character scan over all 63 tracked files to zero. Line endings: every `.md` CRLF, every code and config file LF.
- **Rollback**: revert the commit. The pipeline code is untouched, so no data repair is needed. Reverting restores the Chinese assets as well, because the English layer lives in the upstream material library rather than in this repository.
- **Related**: `CHANGELOG.md` entry for this date / `docs/changes/validation.md` and `docs/changes/ingestion.md` (pointer entries, same date) / commit hash in `git log`.

## 20260914 · layer-label-drift — Fix the layer label drift in the assembly tool

- **Motivation**: `rules_assembly.py` emitted enriched layer labels such as `python 栈` and `项目类型：website`, while every assembled file in both live projects uses the bare layer directory name and the tool's own docstring documents the bare name. The `--check` mode therefore failed on both projects before this change. The projects, the docstring and the full assembly history agree with each other, so the tool was the outlier and was corrected.
- **Scope**: `ng/tools/rules_assembly.py` (`layer_label` and its call site, plus the docstring). No file in this repository changed for this fix.
- **Behaviour and contract changes**: none. Assembled layer headings read `【层：python】` and `【层：data-processing】` again, matching every artefact ever produced.
- **Verification**: `rules_assembly.py --stack python --type website --check <memo-ledger>` to PASS and `--stack python --type data-processing --check .` to PASS. Both reported four mismatched files before the fix.
- **Rollback**: revert. Recorded here because this tool produces this repository's `docs/rules/` set, even though it lives outside the repository.
- **Related**: commit hash in `git log`.
