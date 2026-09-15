# Changelog

Version-level changes, reverse chronological order. Source: `git log --date=short --pretty=format:'%ad %h %s'`.
A commit that only updates this file cannot list itself, so the newest hash here always trails `git log` by one entry.

## 2026-09-15

- `2f5f2eb` refactor(sql): move the target-shape DDL into sql/reference/ [AI]
- `b542cd6` docs: drop the archive and fold the Iceberg DDL into DATA-DESIGN [AI]
- `cf13763` refactor(config): rename the data contract half of config/ to contract/ [AI]
- `fc87eff` docs: show the configuration split in the layout trees [AI]
- `6f9cca6` docs(interface): publish the inspection CLI contract and close two rule drifts [AI]
- `11e1a1f` fix(config): carry the config layout through the code, the tests and the documents [AI]
- `a748aae` [AI] fix send_email path references across SSQ and fin-risk scripts
- `0de1385` docs: record the selector hardening and the rename in the changelog [AI]
- `ca9605d` refactor(show-data): finish the show rename inside the viewer [AI]
- `80ec9f2` fix(make): read selectors only from the command line and treat SCHEMA as a switch [AI]
- `5a97c8d` docs: record the selector case fix in the changelog [AI]
- `490a662` fix(make): accept the inspection selectors in either case [AI]

## 2026-09-14

- `c4ab4fb` docs: give the two inspection commands their own subsections [AI]
- `7000dd3` docs: list the show-data viewer in the README, PROJECT and AGENTS [AI]
- `2cf5b89` feat(show-data): add a read-only viewer for the run output [AI]
- `f6d03db` feat(check-data): add a read-only verifier for the run output [AI]
- `5519396` docs: list make lint in the quick start and the verification commands [AI]
- `0edbf50` docs: tidy the storage tree comment alignment [AI]
- `4515435` docs: align the project documents with the repository [AI]
- `53b3324` docs(rules): name the shared logging entry point logger.py [AI]
- `a06f010` docs(rules): stop the project layers from mandating system-side files [AI]
- `99fd54e` docs(rules): make the skeleton conditional instead of mandatory [AI]
- `572100c` docs(rules): decouple the shared rules material from a project layout [AI]
- `9ed1aa4` feat(pii): mask direct identifiers at the ingestion boundary [AI]
- `69e3d3c` chore(lint): make the ruff and mypy claims in CODING-STANDARD true [AI]
- `1da42c6` chore(provenance): retrofit the AI-generation header on all 22 code files [AI]
- `88c3d41` feat(gate): enforce the AI provenance marker on agent commits [AI]
- `9c7f463` docs: move the deviation record out of AGENTS.md into KNOWN-ISSUE.md [AI]
- `24945f3` docs: split clause-chained sentences into one statement each [AI]
- `011c432` docs: make the table contract the single source for the dedup rule
- `667bd59` docs: align the table contracts with the artefacts and retire two phantom fields
- `0ee0860` docs: complete the table contracts and retract the duplicated table detail
- `431c9d2` docs: credit the project authors in the README
- `1f91b73` docs: sync the documentation to the new storage layout
- `3b7711f` chore: commit the demo data skeleton and make the sample reproducible
- `f28f68e` feat: let --input default to the environment's inbound drop location
- `13a6654` refactor: restructure the environment storage layout into data/{env}/{input,output}

- `2018807` docs: record the blocking line-ending check in the change trail
- `99a7001` docs: fix the double-CR line endings in AGENTS.md and normalise the index
- `e6f78e4` docs: record the line-ending fix and re-assemble the rules set
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
