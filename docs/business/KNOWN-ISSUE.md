# Known Issues and Design Decisions

This document records known pitfalls, design decisions, and rejected alternatives. Each entry has five parts: symptom, root cause, impact, disposition, and related document. The disposition is either "accepted" (the project lives with it) or "migration item" (to be addressed when the production shape is available).
The deviation table in `AGENTS.md` §10 points to the anchors in this document. Items that have been migrated out of this list are listed under "Resolved Migration Items" at the end.
---

### #coverage-gate-off — No coverage gate enabled

**Symptom**: the project does not run a coverage tool. There is no `--cov` flag in the pytest configuration or CI pipeline.
**Root cause**: the upstream rule requires coverage of at least 80 percent for projects with CI. This project's CI skeleton defines test and data-quality stages but does not wire a coverage tool.
**Impact**: there is no automated check that new code is covered by tests. The baseline is "at least one assertion per requirement" plus manual review.
**Disposition**: accepted. The project has 88 tests covering contract edge cases. Adding a coverage gate is a future improvement, not a blocking issue for a reference implementation.
**Related**: AGENTS.md (deviation: coverage gate), tests/.
---

### #no-catalog — No catalog or session management

**Symptom**: the project has no `catalog.py` and no concept of a unified compute session. Bronze, Silver, and Gold are plain directory paths on the local file system.
**Root cause**: the skeleton provides a `catalog.py` entry point only for projects that have a catalog (Iceberg / Hive); this project has none. It runs on Pandas with local Parquet files. There is no Spark session, no Iceberg catalog, and no table registry.
**Impact**: table metadata (schema, partitions) is implicit in the directory structure, not registered in a catalog. Time travel and snapshot isolation are not available.
**Disposition**: accepted for the local demo. The production shape would use an Iceberg catalog. See DATA-DESIGN section 2.7 for the Iceberg DDL reference.
**Related**: DATA-DESIGN.md (section 2.7, production table format reference), KNOWN-ISSUE.md "Skeleton Deviations" (conditional skeleton item, not a deviation).
---

### #no-snapshot-lifecycle — No snapshot layer or retention policy

**Symptom**: partition directories are overwritten directly. There is no snapshot history, no retention policy, and no compaction task.
**Root cause**: the upstream rule requires each table to have a snapshot retention and compaction strategy. This project writes Parquet files directly to partition directories using overwrite mode. There is no metadata layer tracking snapshots.
**Impact**: re-running a partition destroys the previous version. There is no way to roll back to a prior state. Time travel queries are not possible.
**Disposition**: accepted for the local demo. Bronze retains the original JSON for replay. The production shape would use Iceberg snapshots with retention configuration.
**Related**: DATA-DESIGN.md (section 2.6, reprocessing semantics), AGENTS.md (deviation: snapshot lifecycle).
---

### #amount-float — Amount column uses float64 instead of DECIMAL

**Symptom**: the `amount` column in Silver and Gold is stored as pandas `float64`, not as a `DECIMAL` type.
**Root cause**: the upstream rule prohibits `float` for monetary values. Pandas does not have a native `DECIMAL` type; `float64` is the default numeric type. Converting to `decimal.Decimal` would break vectorized operations and significantly slow down the pipeline.
**Impact**: floating-point arithmetic can introduce rounding errors in `total_amount` and `avg_amount` aggregations. For a demo with small data this is not visible, but it would be a correctness issue in production.
**Disposition**: migration item. The production shape uses `DECIMAL(18,2)` in the Iceberg DDL (see DATA-DESIGN section 2.7, Silver and Gold table definitions).
**Related**: DATA-DESIGN.md (section 2.7, Iceberg DDL), AGENTS.md section 3 (red line: amount float), AGENTS.md (deviation: amount precision).
---

### #table-contract-approval — No approval chain for table contracts

**Symptom**: table contract files in `docs/tables/` do not carry a `status: approved` frontmatter field. There is no CI check that blocks migration of unapproved contracts.
**Root cause**: the upstream rule requires table contracts to record approval status and CI to enforce it. This project is a local reference implementation with no approval chain.
**Impact**: table contracts can be changed without review. There is no audit trail of who approved a schema change.
**Disposition**: accepted. The project has no production data and no multiple consumers. The contracts are maintained by the developer. A production system would add frontmatter and a CI gate.
**Related**: docs/tables/ (table contract files), AGENTS.md (deviation: table contract approval).
---

## Design Decisions and Rejected Alternatives

### Decision: Pandas single-machine instead of PySpark

**Chosen**: Pandas on a single machine.
**Rejected**: PySpark on a cluster.
**Reason**: no big-data cluster is available. Data volume assumption is under 10 GB per batch, which Pandas handles well. Module boundaries communicate through DataFrame contracts, so migrating to Spark is a re-implementation of each stage without re-architecting the pipeline.

### Decision: Strict mode rejects unknown fields

**Chosen**: strict mode that rejects rows carrying undeclared fields.
**Rejected**: lenient mode that passes unknown fields through to Silver.
**Reason**: strict mode maintains data contract integrity. Unknown fields indicate a schema drift that should be caught early, not silently propagated downstream.

### Decision: Fail-safe isolation over flag-and-pass

**Chosen**: type and format violations are quarantined at the validation stage. They never reach Silver.
**Rejected**: a "yellow path" that flags suspect rows with `_validation_status = "type_mismatch"` and passes them to Silver for downstream handling.
**Reason**: the single-machine demo chooses fail-safe isolation over carrying suspect rows downstream. The flag-and-pass path was never built, so no `_validation_status` column exists in the written Silver artefacts. The `type_mismatch` value is reserved for that path if it is ever built.

### Decision: Gold always reads from on-disk Silver snapshot

**Chosen**: the CLI reads all Silver Parquet files from disk and builds Gold from the full snapshot.
**Rejected**: building Gold from the in-memory batch that was just processed.
**Reason**: dimension tables and the wide table are full snapshots. A `--event-date` scoped backfill run must not rebuild dimensions from the scoped subset, or rows and `first_seen_date` values would be lost.

### Decision: Partition overwrite for idempotency

**Chosen**: Bronze, Silver, and Gold writes use partition-scoped overwrite.
**Rejected**: append mode.
**Reason**: re-running the same date must not produce duplicate data. A production Bronze would append new files instead of overwriting, but for the single-machine demo, overwrite is simpler and sufficient.

---

## Resolved Migration Items

Items that were registered as migration items and have since been migrated out. The full record lives in the module change log; the line here keeps the audit trail visible from this document.

| Anchor | Was | Resolved in |
|---|---|---|
| `#cli-holds-transform` | `cli.py` built the error envelope instead of delegating to a module | `docs/changes/validation.md` (20260914) — extracted to `validation/error_envelope.py` |
| `#now-timestamp` | Pipeline code read the system clock for processing timestamps | `docs/changes/engineering.md` (20260914) — `--run-timestamp` injected at the entry boundary and threaded down |
| `#layout-flat-pipeline` | Flat namespace packages instead of an installable src layout | `docs/changes/engineering.md` (20260914) — moved to `src/demo_gx/`, per-package `__init__.py`, `pyproject.toml` |

### #clock-reads-outside-data-stamping — Residual boundaries after the run-timestamp change

Two clock reads survive by design and are not defects:

- **Entry boundary**: `cli.py` reads the wall clock once when `--run-timestamp` is absent. The entry plays the scheduler role in a single-machine project; without that read `make run` would have no run instant. Injecting the flag removes the read entirely, and every data artefact then becomes byte-reproducible.
- **Telemetry**: `common/metrics.py` and `common/logger.py` stamp real wall-clock times. Metrics record how long a run actually took; injecting a synthetic value there would make the metric lie.

---

## Skeleton Deviations (upstream vs this project)

This section is the single home of the deviation record: the table, the applicability boundaries and the cost-and-rollback notes. `AGENTS.md` §10 keeps only the pointer here.

The standard practice is the default and a deviation is the exception, so a deviation must satisfy all four conditions at once:

1. It is registered item by item in the table below, in four columns: issue / upstream / this project / disposition.
2. Its disposition points to an anchor that actually exists; writing only "already explained" is forbidden.
3. It states why the standard practice is not adopted; empty reasons such as "this project is special" are forbidden.
4. Its cost and rollback cost are recorded in the cost-and-rollback summary at the end of this section.

Silently lowering the standard without registering it is forbidden, and "this is just a one-off case" is not a reason for exemption. Inside a table cell a vertical bar such as `a|b` is written `a\|b`, otherwise Markdown breaks that cell. Change entries under `docs/changes/` that cite `AGENTS.md` section 10 refer to this section; those entries are append-only and are not rewritten.

| Issue | Upstream | This project | Disposition |
|---|---|---|---|
| Environment setup | Commit a `uv.lock` lock file (`uv` is installed here, so the "no uv" escape does not apply) | `pyproject.toml` with `>=` floors only; venv + pip install; no lock file | See cost and rollback summary |
| Coverage gate | ≥80% coverage required for CI projects | No coverage tooling; floor is one assertion per requirement | `#coverage-gate-off` |
| Snapshot policy | Every table has retention and compaction | Partition directories overwritten in place; no snapshot layer | `#no-snapshot-lifecycle` |
| Amount precision | DECIMAL type required; no `float` for money | `amount` column is pandas `float64` | `#amount-float` |
| Table contract approval | `status: approved` frontmatter; CI blocks unreviewed | Local reference implementation; no approval chain | `#table-contract-approval` |
| Stage model | Ten stages including pre-release, deployment, observability | Stage 8 replaced by end-to-end smoke; stages 9–10 N/A | See skeleton boundaries below |
| Clock reads | Code reading system time forbidden | `common/metrics.py` and `common/logger.py` read clock for telemetry only | `#clock-reads-outside-data-stamping` |

Items that the skeleton presents as **conditional** are not deviations. Upstream `PROJECT-STRUCTURE.md` §1 marks `dags/`, `src/{pkg}/pipelines/{domain}/`, `src/{pkg}/models/`, `sql/`, `catalog.py`, `tests/{fixtures,pipelines}/` and the `ods`→`dwd`→`dws`→`ads` layer naming as "created only when that condition holds", and states that not creating them is not a deviation. This project adopts none of them, so they are absent from the table above. Only those rows are departures from an unconditional rule.

**Skeleton applicability boundaries**: the conditional skeleton items appear only with a given technology choice (a scheduler, a catalog, a SQL engine). This project is a single-machine Pandas reference implementation (`docs/business/PROJECT.md`) and adopts none of them. What it does instead:

- **No `dags/`**: no scheduler; `python -m demo_gx.cli` is the only entry point.
- **Entry point inside the package, not in `scripts/`**: the skeleton's merge boundary requires three conditions at once and this project satisfies only the first (single entry). Conditions two and three fail because the entry hardcodes `--env` values and `tests/` imports four pipeline components as libraries. Merge accepted because there is no second caller; cost is command-line side effects in library code.
- **Transformation by stage not domain**: single business domain (events) means domain-split would produce singleton directories. Stage boundaries are the real reusable boundaries. `common/` fills the cross-stage shared layer role.
- **No `src/demo_gx/models/`**: `config/schema.yaml` and `docs/tables/` are the single sources of truth. A Python model layer would create a second definition.
- **No `sql/`**: no SQL engine; schema changes tracked through `schema.yaml` and table contracts. Iceberg DDL exists in `docs/archive/` as production-shape reference only.
- **Flat tests**: one file per module; mirroring would add a directory level per test file. `test_validation.py` covers `validation/schema_validator.py`.
- **Bronze/Silver/Gold naming**: maps to upstream `ods/dwd/dws/ads` via `DOMAIN-LANGUAGE.md` term `data layer mapping`.

**Stage model applicability boundaries**: this project is a local reference implementation. It has no pre-release environment, no production deployment, and no release chain beyond CI. Of the baseline ten stages, stages 1-7 apply in full; stage 8 is replaced by an end-to-end smoke run, and its interface checks do not apply; stages 9 and 10 do not apply. The CI gate and the commit discipline still apply.

**Uncovered modules**: `ingestion/reader.py`, `validation/error_envelope.py`, `common/*`, and `cli.py` have only end-to-end smoke coverage, no direct unit tests. This is the concrete form of `#coverage-gate-off`.

**Cost and rollback summary** (one line per deviation row; the conditional skeleton items are grouped in the first line):
- Adopting the conditional skeleton items (`dags/`, `src/{pkg}/pipelines/{domain}/`, `src/{pkg}/models/`, `sql/`) means creating those directories and rewiring the entry point; the layer-name difference (Bronze/Silver/Gold) has zero rollback cost. These are shape choices, not deviations.
- **Environment setup** — cost: dependency resolution is not pinned, so a fresh environment can resolve different versions; rollback: low, add `uv lock` or pin with `pip freeze`.
- **Coverage gate** (`#coverage-gate-off`) — cost: a regression that no test asserts can pass CI unnoticed; rollback: low, add pytest-cov and a threshold.
- **Catalog entry point** (`#no-catalog`) — cost: introducing Iceberg later means adding `catalog.py` and re-pointing every read and write; rollback: medium.
- **Snapshot policy** (`#no-snapshot-lifecycle`) — cost: no point-in-time recovery and no small-file compaction; rollback: medium, re-register the data as an Iceberg table.
- **Amount precision** (`#amount-float`) — cost: monetary rounding has to be handled by explicit rounding at the boundary; rollback: medium, switch the column to `decimal.Decimal` and re-lock the affected tests and the table contract.
- **Table contract approval** (`#table-contract-approval`) — cost: nothing blocks an unreviewed contract change; rollback: low, add a CI check on the frontmatter.
- **Stage model** — cost: release and observability discipline is not exercised; rollback: both stages must be reinstated once this becomes a deployed service.
- **Clock reads** (`#clock-reads-outside-data-stamping`) — cost: telemetry timestamps are not reproducible across runs; rollback: low, inject the run instant into the telemetry path too.
