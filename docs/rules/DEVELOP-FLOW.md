# DEVELOP-FLOW — Development flow standard (baseline · independent of stack and project type)

> **Flow control**: shared between this project's `AGENTS.md` (AI coding constraints) and this standard; for coding patterns see `docs/rules/CODING-STANDARD.md`.

## 1. Ten-stage pipeline

1.Requirements → 2.Solution → 3.Breakdown → 4.Coding → 5.Unit test → 6.Review → 7.Integration → 8.Staging → 9.Deployment → 10.Observability

| Stage | Name | Quality Gate (exit condition) | Stage output (what is produced, where it goes) |
|---|---|---|---|
| 1 | Requirements analysis | Requirements unambiguous, ambiguities clarified, business value clear | Requirement list + impact analysis. **Human input is acceptable** (verbal / ticket / customer document are all fine, writing a document first is not mandatory); when a document is needed, write it into `docs/business/PROJECT.md` §Scope and requirements |
| 2 | Solution design | Solution reviewed, choices justified, 🔴 red line conflicts cleared to zero | **Standards**: the four-piece set under `docs/rules/` (structure / coding / flow / acceptance); **design documents**: `PROJECT` / `MODULE-DESIGN` / `DATA-DESIGN` / `INTERFACE-DESIGN` / `DOMAIN-LANGUAGE` under `docs/business/`; technical change list + change entries |
| 3 | Task breakdown | Task granularity ≤ 4h, dependencies clear | Task list + execution order (granularity criterion: **can be verified independently**) |
| 4 | Coding implementation | Coding standard followed, zero red line violations, compile/static checks 0 error | Runnable code + contract documents kept in sync + change entries (sub-steps in §1.1) |
| 5 | Unit test | Coverage ≥ 80% (**only for projects with CI**), core logic 100%, all tests green | Test code (mirroring the `src/` structure) + test report |
| 6 | Code review | No 🔴 issues in review, CI gates all green | Review record (issue list + conclusion + open items) |
| 7 | Integration test | Interface integration verified, data flow correct | Integration test report (including real request / response evidence) |
| 8 | Staging verification | Verification in the staging environment passed (including smoke test) | Verification record (smoke path + actual result) |
| 9 | Production deployment | Deployment script executed successfully, smoke test passed | Deployment record (date / environment / version / smoke result) |
| 10 | Production observability | Observation period anomaly-free, metrics within baseline | Observability report (metrics + anomalies + conclusion) |

> **Outputs fall into two categories, do not mix them**: ① **standards and design documents** (stage 2, long-lived living documents that must be kept in sync when code changes); ② **process records** (stages 4–10, written as change entries in `docs/changes/{module}.md`, with version-level summaries in `docs/business/CHANGELOG.md`). Process records **must not invent additional file types**.

### 1.1 Sub-steps of stage 4 "Coding implementation" (advance in order, verify step by step)

Stage 4 is not "write it all in one go". Advance in the order below; at the end of every sub-step the **code must still compile / still run**:

| Sub-step | What to do | Exit condition (verifiable) |
|---|---|---|
| 4a Framework setup | Directory skeleton, dependency declarations, configuration single entry point, logging and error handling single entry point, entry file (may be an empty implementation) | The project starts (service can start / command can run); static checks 0 error |
| 4b Interface implementation | The interface layer with **contract first**: routes / signatures / input validation / error shape (placeholders first, implementation later) | Interfaces reachable per the contract; error codes consistent with the contract |
| 4c Feature module implementation | Implement business logic module by module (one change entry per module) | Each module's behavior meets its corresponding acceptance criteria (AC) |
| 4d Wiring and self-test | Wire the modules into the interfaces, add boundary and exception handling at the wiring points, get the end-to-end main path working | The main path works end to end (the stage 5 tests are filled in here) |

🔴 **No large concurrent changes across sub-steps**: 4a must pass before entering 4b, and 4b must pass before entering 4c (the same discipline as "do not enter N+1 until stage N passes"). Committing several small steps within the same sub-step is allowed.

### Stage transition rules

- **Serial progression**: if stage N's Quality Gate is unmet, entering stage N+1 is **forbidden**
- **Small changes may be merged**: when few files are involved, stages 1–3 may be completed in one go, but **change entries cannot be skipped**; red line checks and smoke verification **cannot be skipped in any scenario**
- **Rollback**: if any stage fails, return to the corresponding stage per the rollback route table in §3 and start over

## 2. Branches and commits

| Item | Convention | Example |
|---|------|---------|
| Feature branch | `feature/{slug}`, with the **same name** as the change entry slug | `feature/coupon-feature` |
| Fix branch | `fix/{issue-or-bug-desc}` | `fix/cart-total-rounding` |
| Main branch | `main` (protected branch, only accepts merged MRs) | — |
| Commit | `type(scope): message`; type ∈ feat/fix/refactor/test/docs/chore | `feat(coupon): support coupon claiming` |
| Merge | An MR may only be raised after stage 6 review passes + CI is all green | — |

## 3. Rollback route table

| Stage | Rollback strategy | Trigger condition |
|---|---|---|
| Coding implementation | Discard changes with `git checkout --` | Compile failure |
| Unit test | Fix the tests or revert the code | Test failure rate > 20% |
| Code review | Revise per the review comments | 🔴 issues unresolved |
| Integration test | Revert to the last stable version | Interfaces not working |
| Staging verification | Revert to the production version | Feature anomalies |
| Production deployment | Roll back to the previous version's image/package | Smoke test failure |
| Production observability | Emergency rollback + degradation | Error rate > 1% |

> **Database change rollback is out of scope for this table**: rollback scripts and migration scripts go **in pairs** under `sql/migrations/` (`{V}__{desc}.sql` + `{V}__{desc}.down.sql`), and **code rollback precedes data repair**.

## 4. Change management

```text
docs/changes/
├── {module}.md          # one per module, appended in ascending order (module = top-level module directory name under `src/`)
└── engineering.md       # fallback for non-functional changes (build / dependencies / rules / documents / CI)
```

- 🔴 This directory holds **entry files only** (`{module}.md`): no README / notes / lists / attachments — **the directory itself is the list** (module name = source top-level module directory name). The mapping of "which change goes in which file" and the fallback rules are written into the project's `AGENTS.md` §9 and `docs/business/PROJECT.md`
- Division of labor with `CHANGELOG.md`: this directory = **per-module change details** (one entry per change, including scope / verification / rollback); `CHANGELOG.md` = **timeline summary view** (one line per entry)

- 🔴 Append an entry to the end of the corresponding module file **when the change is complete**; for cross-module changes write the full text in the primary module and a one-line pointer back in the other modules
- 🔴 Module files are **append-only**; do not rewrite historical entries (if you got something wrong, append a correction entry to keep it traceable)
- Changes containing DDL: migration and rollback scripts go **in pairs** under `sql/migrations/` (`{V}__{desc}.sql` + `{V}__{desc}.down.sql`), and the entry gives the paths
- Projects without CI: write entries as usual; in the "Verification" field write the commands actually executed and their results
- 🔴 The "Verification" field must contain **commands and results that were actually run** ("should be fine" is forbidden); historical entries are not backfilled, use `git log` for traceability

### Change entry template (six required + one conditional)

````markdown
## {YYYYMMDD} · {slug} — {one-line title}
- **Motivation**: what is being done and why (corresponding requirement ID / issue)
- **Scope**: file-level list (code / configuration / DDL / contract documents)
- **Behavior and contract changes**: external impact of interfaces, schema, data meaning, configuration items; write "none" if there is no change
- **Verification**: commands actually executed + results ("should be fine" is forbidden)
- **Rollback**: write the code revert method and the data repair method separately
- **Related**: `CHANGELOG.md` entry / `KNOWN-ISSUE.md#anchor` / commit hash
- **Deployment record** (conditional: append only when the project has a production deployment; otherwise omit the whole bullet): date / environment / version / smoke result
````

> Complex changes (spanning multiple modules / with external dependencies) may add a "Task breakdown" sub-section under the entry (granularity ≤ 4h).

## 5. AI coding constraints (paired with the project root `AGENTS.md`)

### 5.0 Preconditions for effect (confirm first, then talk about constraints)

`AGENTS.md` is injected at **session startup** along the "cwd → git root" chain: a non-git project started from a subdirectory **does not load it**; `delegate_task` sub-agents and cron jobs without a `workdir` set **do not read it** either. Delegation, testing and acceptance must always be started **with the project root as cwd**. Otherwise the constraints arrive one step late, and the actions in the meantime are effectively unconstrained. This applies equally to Hermes and its delegation chain: coder profile, sub-agents and cron. When unsure, **inline** the red lines from the project's `AGENTS.md` §3 into the task brief.

### 5.1 The 40% threshold
- A single AI-generated **code change must not exceed 40% of the file's total volume**; above that it must be split into multiple operations
- After each operation, verify the compile/run status (per stack: `mvn compile` / `vue-tsc --noEmit` / `python -m compileall` + static checks)

### 5.2 Context loading constraints
- Before coding, load the two categories of documents as needed: **standards** in `docs/rules/` (boundaries and prohibitions) + **business documents** in `docs/business/` (this project's contracts, data structures, module design); **no more than 3 files** in total (to prevent context overload)
- **Locate before reading**: read only the sections relevant to this change; never read the whole thing as a catch-all
- For concrete coding patterns, prefer **existing code** and skill files; rule files only define boundaries, they do not expand on them

### 5.3 Quality checkpoints

| Checkpoint | What is checked | Pass criteria |
|---|---|---|
| Compile check | Code compiles | 0 error |
| Standard check | Complies with `CODING-STANDARD.md` | 0 🔴 violation |
| Comment check | Comments / docstrings match the implementation; no commented-out code, no bare `TODO` | 0 mismatches |
| Test check | Unit tests pass | Coverage ≥ 80% |
| Review check | Code review passes | 0 🔴 issue |
| Gate check | CI pipeline | Compile/test/coverage/red line scan all green |

### 5.4 Handling red line conflicts
If a violation of the red lines in `AGENTS.md` is found at any stage: **stop advancing immediately → fix → re-verify from the affected stage**. "Merge first, fix afterwards" is forbidden.

## 6. Entropy management cycle table

| Frequency | Activity | Content |
|---|---|---|
| Daily | Code scan | Dead code, unused imports, TODO backlog |
| Weekly | Dependency audit | Outdated dependencies, security vulnerabilities |
| Biweekly | Architecture review | Module boundaries, circular dependencies |
| Monthly | Technical debt cleanup | Prioritize and pay down |
| Quarterly | Code refactoring | For high-churn modules |

## 7. Correspondence with the stage axis

The ten stages of this standard map onto the seven stages of the `develop/` skill tree: 1–3 → `01-analyze`, 4 → `03-build`, 5/7 → `04-test`, 6 → `05-accept`, 8–10 → `06-release`, production issues → `07-maintain`.

## 8. Applicable boundaries (relationship to the `coding-flow` seven steps)

- This pipeline targets delivery **with CI / MR / staging / production multi-environment** setups; single-machine scripts without CI and delegated agent tasks use the **seven-step execution sequence** of the `coding-flow` skill.
- Mapping: seven steps 0–2 ≈ ten stages 1–3; seven steps 3–4 ≈ 4–5; seven step 6 ≈ 7–8; seven step 7 ≈ 10.
- Red lines shared by both: contract before coding, tests must not be written next to the source code, changes must leave a trail (without CI, use `docs/business/CHANGELOG.md` instead of `summary.md`).

## [Layer: python]DEVELOP-FLOW — Development Flow Standard (Python)

### 1. Python Stack Stage Execution

| Stage | Python stack action | Command / gate |
|---|---|---|
| 2 Solution design | Define the **data contract** (if there is data): fields / types / precision / primary key / idempotency approach | The contract document goes into `docs/business/DATA-DESIGN.md` |
| 4 Coding implementation | Independent venv + dependencies in `pyproject.toml` | `ruff check` + `mypy` 0 error |
| 5 Unit testing | pytest; cover core logic and boundaries | `pytest -q` all green, coverage ≥ 80% |
| 6 Code review | Red line scan (this standard §1-§9) | 0 🔴 violation |
| 8 Pre-release verification | Run through with shadow resource names (independent DB/schema) | See §4 shadow acceptance |
| 9 Release deployment | Migration → code → scheduling (**the order is not interchangeable**) 🔴 | The deploy script includes a smoke test |
| 10 Production observation | Metrics + searchable log fields | No anomalies during the observation period |

### 2. Contract Before Coding 🔴

For projects with data landing in a database: one contract per table / per external structure, and **define the contract before writing code**. The contract must include:

- Granularity / business primary key / **deduplication method** (MERGE or row_number)
- Fields and types, **precision** (amounts / ratios / exchange rates), PII fields and their redaction method
- Lifecycle (retention period / cleanup policy), freshness SLA and owner, upstream and downstream dependencies
- **Quality rule list** (uniqueness / non-null / row count fluctuation threshold / enum values)

**Review**: at least 1 owner approves; tables containing amounts or PII require **dual sign-off**.
**Contract state machine**: `draft → approved`; **when the contract changes the state is automatically reset to `draft` and re-approval is required**; CI checks that the migration corresponding to a contract that is not approved must not enter main.

### 3. Dependency and Migration Management 🔴

- Migration scripts `V{N}__{desc}.sql` are **numbered incrementally**; modifying or reusing an already-committed number is forbidden
- Scope: `CREATE TABLE`, schema evolution (ADD/DROP/RENAME COLUMN), indexes, table properties
- **Dry-run locally and in CI against the dev environment**; production execution goes only through the release pipeline, and **manually changing the schema in the production database is forbidden**
- Every `V{N}__{desc}.sql` **must be paired with a rollback script**: covering DROP TABLE (only tables created in this change), DROP COLUMN (only columns added in this change) and restoring table properties; the rollback must be dry-run as well
- 🔴 Data repair is **not allowed** inside a rollback script; data rollback follows the priority flow in §5
- **For tables with a serial primary key, INSERT does not list the id column** (otherwise it bypasses the sequence, see skill `pg-query`)

### 4. Shadow Run and Acceptance Criteria

New tasks / major changes first run on shadow resources (a dev database or shadow tables), and may cut over to production only when **all** of the following hold:

1. Successfully running for ≥ 2 consecutive scheduling cycles
2. Primary key uniqueness 100%
3. Amount field totals reconcile with upstream (precision to the cent)
4. PII fields are redacted per the contract
5. Quality checks pass with no alerts
6. Task elapsed time is within the SLA budget

### 5. Rerun / Backfill

- Must be declared in the PR and in the `docs/changes/{module}.md` entry: scope, **idempotency approach**, downstream impact
- When the rerun window conflicts with the scheduling window, **pause the corresponding schedule first**
- Large-scale reruns are **executed in batches**, verifying the quality rules after each batch

### 6. Release and Scheduling

- 🔴 Release order: **migration → code → scheduling** (reversing the order leaves the code unable to find the schema)
- 🟡 Scheduled tasks forward through a thin shell (the shell only calls the real implementation, see skill `cron-creation-discipline`); the logic is stored in one place only

### 7. Interface with the Acceptance Checklist

Before CR, pass the **CR Checklist** of `ACCEPTANCE-CHECKLIST.md` (a file at the same level); before release, pass the **Production Readiness Checklist** (data quality / reliability / observability / deployment rollback / security).

## [Layer: data-processing]DEVELOP-FLOW — Development Flow (Data-Processing Projects)

### 1. Flow Overview (this type's version)

```text
Requirements → Table contract design → Design review → Migration scripts → Pipeline development → Local testing
     → Quality wiring → CR → Merge → Release (migration→code→scheduling) → Rerun verification → Change record
```

Difference from the ten-stage baseline (this file §1): **"table contract design" precedes coding**, and in this type "staging verification" is completed through a **shadow table run**.

### 2. Stage-Specific Focus Points

| Stage | Action specific to this type |
|---|---|
| Requirements analysis | Clarify the grain (daily/hourly), the deduplication and filtering method, SLA, owner |
| Solution design | **Table contract first** (see structure standard §3); tables containing monetary amounts or PII require a **two-person sign-off** |
| Coding implementation | Pipeline function signature `run(ds: str)`; the partition parameter is injected by the scheduler |
| Unit testing | Money conversion, deduplication/merge, partition filtering **must have boundary cases** (empty table, duplicate keys, cross-partition) |
| Integration testing | Run migration dry-run against the dev environment + run a shadow table for one cycle |
| Staging verification | Shadow table acceptance (see §3) |
| Go-live deployment | **Migration → Code → Scheduling** (the order cannot be changed) 🔴 |
| Production observability | Row count / freshness / quality alerts |

### 3. Shadow Run Acceptance Criteria (all must be satisfied to go to production)

1. Successfully run for ≥ 2 consecutive scheduling cycles
2. Row count deviation between the shadow table and the upstream source table < 1%
3. Primary key uniqueness 100%
4. Monetary field totals reconcile with upstream (precision to the cent)
5. PII fields are masked per the contract
6. Quality checks pass with no alerts
7. Task elapsed time is within the SLA budget

### 4. Backfill

- Must be declared in the PR and the change entry: **partition range, idempotency method** (partition overwrite / MERGE), impact on downstream
- When the backfill window conflicts with the scheduling window, **pause the corresponding DAG first**
- Large-range backfills are **executed in batches**, with the quality rules validated after each batch

### 5. Scheduling and Release 🔴

- Release order: **Migration → Code → DAG** (the order cannot be changed)
- New DAGs have **catchup disabled** by default (`catchup=False`); if historical backfill is needed it must be explicitly declared and go through §4
- 🔴 The task partition parameter is uniformly injected by the scheduler (`ds`); **reading the system's current time inside the code is forbidden**
- 🟡 A new task first runs for one cycle in the dev catalog / shadow table; only after verifying the row count and primary key uniqueness does it switch to the production table

### 6. Rollback and Incidents

- Data rollback priority: **partition-level overwrite rerun > snapshot time-travel restore > upstream recompute**
- 🔴 Before executing snapshot expiry / orphan file cleanup, you must confirm there are **no in-flight backfills or time-travel reads** within the retention window
- Incident postmortems are recorded in `docs/changes/{module}.md`
