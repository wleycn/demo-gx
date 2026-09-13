# Changelog

Version-level changes, reverse chronological order. Source: `git log --date=short --pretty=format:'%ad %h %s'`.

## 2026-09-14

- `14ab112` docs: record the type-marker gate fix in the change trail
- `c114261` docs: move the repository to English via an upstream language layer
- `67d05e7` docs: apply the independent audit findings
- `4ce4aad` refactor: move pipeline/ to an installable src/demo_gx package
- `65f7b4b` refactor: inject the run timestamp at the entry boundary
- `67ff35f` refactor(validation): extract the error envelope out of the CLI
- `c3c9c21` docs: wrap over-long English lines in PROJECT.md and the table contracts
- `5c5ec2d` docs: restore missing content and converge duplicated statements
- `c10c173` docs: turn the gate description into a list in PROJECT.md
- `f306ec2` docs: split an over-long sentence in PROJECT.md
- `ecd08a4` docs(governance): keep the pre-commit gate hook in the repository
- `e92748c` docs: migrate to the nine-document system, archive superseded docs
- `9761eb8` docs(governance): add AGENTS.md and docs/rules four-piece set

## 2026-09-11

- `0a8eb3a` docs: add change-logs / known-issues placeholder docs
- `75e3b60` docs: README venv-activate step + git-repo heading; architecture Flink option

## 2026-09-09

- `d600c1f` refactor: move run artifacts under env storage dirs to clean the repo root
- `202b9e8` fix: dev peer-review findings including epoch timestamp corruption, parser consolidation, dead code, test coverage
- `8563ac2` fix: round-2 writer QC including dedup stable tie, event-date mixed-format scope, env isolation, doc contract alignment
- `b78709c` fix: round-2 QC findings (test role) including backfill Gold regression, mixed-format ts, precision, bronze null handling
- `9300cdc` docs: align with implementation after QC audit (test and writer roles)
- `d599c93` fix: quarantine non-numeric amount, reject extra fields, wire `--event-date`; add CI skeleton
- `1364969` chore: add Makefile entry points and README Quick Start
- `456254f` fix: end-to-end run plus Bronze layer and future-timestamp quarantine
- `5ea5bf9` docs: declare big-data runtime constraint and add Iceberg SQL assets
- `2d50b0d` fix(docs): wrap ASCII trees and diagrams in code fences
- `0a7a45e` chore: declare line-ending policy via `.gitattributes`
- `9e07022` i18n: globalize project to English-only with Google-style docstrings
- `6f3e0a4` chore: initial commit (P5 take-home pipeline reference implementation)
