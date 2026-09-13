# AGENTS.md — AI Coding Constraints (Data-processing project template)

> Rules come in two levels. 🔴 Red line: the AI must not generate code that violates it; review rejects it outright. 🟡 Recommendation: when deviating, state the reason in the report or in `CHANGELOG`.
> Every AI coding tool and agent runtime working in this repository is bound by this file.
> That includes Hermes Agent itself, along with the coder profiles, delegated subagents and cron jobs it dispatches.
> Claude Code, Codex, Cursor and other CLI / IDE assistants are equally subject to it.
> There is exactly one test: **having this repository as cwd means being bound**. A tool not named above is not exempt just because of that. The effective path on the Hermes side is in §8.

## 0. Rule Precedence

This file has the highest authority. Going down from there: the `docs/rules/` four-piece set, `docs/business/` business documents, existing code style, general industry practice. When layers conflict, the layer with the higher authority wins.

When you find existing code conflicting with a higher-level rule, **do not silently follow the existing code**. Point the conflict out in the change trail.

## 1. Tech Stack

- **Language and runtime**: Python 3.11 (minimum 3.10). The virtual environment lives inside the project at `.venv/`, is not committed, and commands always start with `.venv/bin/python`
- **Storage engine**: local filesystem, no database. The three data layers land in `data/`, the test environment in `test/data/`, isolated by the `storage.base_path` config item
- **Orchestration**: `src/demo_gx/cli.py`, invoked as `python -m demo_gx.cli`, no scheduler. The partition parameter is injected by `--event-date` and the run timestamp by `--run-timestamp`; the entry point reads the system clock once, and only when neither was injected
- **Table format**: Parquet partition directories `event_date=YYYY-MM-DD`, no Iceberg, no catalog
- **Dependencies and toolchain**: `pyproject.toml` (the single entry point for dependencies and toolchain), `Makefile`, `.gitlab-ci.yml`
- **Target shape**: designed for a Spark + Iceberg big-data shape, verified locally on single-machine Pandas. For the technology choices and the rejected alternatives see `docs/business/PROJECT.md`

## 2. Context Loading (mandatory before starting)

Read through in this order before starting:

1. Read the red line list in §3 of this file
2. Read the "directory duties" and "single entry point" sections of `docs/rules/PROJECT-STRUCTURE.md`
3. Read this type's red lines in `docs/rules/CODING-STANDARD.md`
4. A data change is involved → read the table contract in the corresponding `docs/tables/{table}.md`
5. **No more than 3 rule files in total** (to prevent context overload)

## 3. Red Line List

> The AI must not output code that violates the following; a violation blocks the change, and "merge first, fix later" is not accepted.

1. 🔴 **Writes must be idempotent** (MERGE or partition-level overwrite), **bare append is forbidden**
2. 🔴 **Queries must carry partition pruning**. Full table scans are forbidden, and pulling the full dataset to the driver is forbidden
3. 🔴 **Amounts must not use `float`**. Unit conversion is done once, at the ingestion boundary
4. 🔴 **PII must be masked at the detail layer**. Leaking plaintext into logs or into external tables is forbidden
5. 🔴 **Credentials, endpoints and paths must not be hardcoded**; they all go through the configuration single entry point
6. 🔴 **Computation and catalog access go through the single entry point file**. Scattered session instances are forbidden
7. 🔴 **Destructive operations require explicit human authorization**, including DROP, DELETE, snapshots expire
8. 🔴 **Schema evolution only goes through migrations**. Implicit column additions are forbidden
9. 🔴 **Every table must have a snapshot retention and compaction policy**. Unlimited retention is forbidden
10. 🔴 **Partition parameters are injected by the scheduler**. Code reading the system's current time is forbidden

## 4. Agent Conduct

- **No "incidental improvements"**: only change files within the authorized scope. Raise an adjacent problem separately; do not fix it on the side.
- **Failures must leave a trail**: exceptions must be logged. Catching and then doing nothing is forbidden.
- **Stop when unsure**: when the interface shape, the directory structure or the file a change belongs in is unclear, ask first.
- **Do not execute destructive operations on your own initiative**: DROP, DELETE, bulk overwrite, snapshot expiry — always ask first.
- 🔴 Must not push directly to `main`. A feature branch is mandatory, then submit an MR.

## 5. Output Requirements

- Give only code or an explicit diff, with no unrelated explanation mixed in
- Add a `[AI-GENERATED] model=<m> date=<d> reviewed_by=<human>` comment at the head of each changed file. The commit message contains `[AI]`.
- A single change must not exceed **40%** of the file total. If it exceeds that, split it into several changes and verify step by step.
- Comments and docstrings must be changed in the same commit as the code. Comments that contradict the implementation must not be left behind. A comment explains "**why**", it does not restate "what". For details see the comments section of `docs/rules/CODING-STANDARD.md`.
- Before writing documents, writing reports or writing delivery notes, load the `docs-writing-discipline` skill and read through once against its checklist before delivering
- Migration scripts must be reviewed line by line by a human, with a confirming comment in the PR

## 6. Change Trail

For a functional or contract change, **append** one entry to `docs/changes/{module}.md`. The entry slug has the same name as the branch; for the entry template see `docs/rules/DEVELOP-FLOW.md` §4. `{module}` takes the top-level module directory name under `src/demo_gx/`, namely `ingestion`, `validation`, `transformation`, `curation`, `common`; a non-functional change lands in `engineering.md`. That directory holds **entry files only** — no README, notes or attachments. For the module list see §9.1 project map.

- Append a deployment record after release.

## 7. Uncertainty

- When the rules do not cover a change but the change can be safely rolled back, follow the closest analogous rule in this repository and state in the change trail which rule the analogy was drawn from.
- The following four categories must be confirmed with a human and must not be decided autonomously: how an amount is computed, how deduplication is done, backfill scope, destructive operations.
- Do not introduce a new third-party dependency on your own initiative. To introduce one, write it into the dependency list and go through review.
- When the rules do not cover something or conflict with each other: **stop → ask → wait for confirmation**. Do not loosen a red line on your own, and do not "merge first, change later".

## 8. How This File Is Read (Effective Path)

- How it takes effect: the tool injects this file at **session start** along the **cwd → git root** directory chain. It is not "effective automatically once placed in the project".
- Sessions, delegations and test harnesses must all **start with the project root as cwd**. Starting from outside the project only lazy-loads it one step late, and actions taken before that are effectively unconstrained.
- **This file does not take effect in three cases**: a non-git project started from a subdirectory, a `delegate_task` subagent, and a cron job with no `workdir` set.
- **Guarantee on the Hermes side**: Hermes and its delegation chain always **start with the project root as cwd**. The delegation chain includes coder profiles, `delegate_task` subagents and cron jobs. A delegation brief must state `cwd=/home/hermes/workspace/demo-gx`. **Do not assume the executor has read this file**; when in doubt, **inline** the §3 red lines into the brief.
- Red lines must be **made executable**: if something can be written as a lint, a check script or a CI check, do not count on "the model will read it".

## 9. Maps (where to find what · which skill to use)

Neither map is optional. 9.1 answers "where is the thing", 9.2 answers "which skill to use at this stage".

### 9.1 Project Map (file index)

> Generation rule: fill the table below with files that **actually exist in the project**, and delete inapplicable rows. Paths in the table must be really reachable; `pre_commit_gate.py` checks them.

| Category | Location | Purpose |
|---|---|---|
| Human entry | `README.md` | What this is / how to get started (5-second test) |
| AI constraints | `AGENTS.md` (this file) | Red lines and conduct, highest precedence |
| Rules | `docs/rules/` | Four-piece set: structure / coding / flow / acceptance |
| Business documents | `docs/business/` | Project description / modules / data / interfaces / glossary / changes / known issues |
| Interface contract | `docs/business/INTERFACE-DESIGN.md` | CLI arguments, artefact paths, error envelope: the single source of truth |
| Data contract | `docs/business/DATA-DESIGN.md` | Layered data flow, table structures, partitioning and rerun semantics |
| Table contracts | `docs/tables/{table}.md` | One file per table: grain / primary key / dedup method / lifecycle |
| Field contract source | `config/schema.yaml` | Field types / required / enums / regular expressions |
| Environment config | `config/dev.yaml`, `config/test.yaml`, `config/prod.yaml` | Storage paths / logging / metrics / alerting |
| Product code | `src/demo_gx/` | Installable package; entry `cli.py`, modules `common` / `ingestion` / `validation` / `transformation` / `curation` |
| Dependencies and toolchain | `pyproject.toml` | The single entry point for dependency declarations, packaging and pytest config |
| Sample data generation | `scripts/generate_sample_data.py` | Generates `data/sample_data.json`, carries no business logic |
| Run artefacts | `data/`, `test/data/`, `data_prod/` | Bronze / Silver / Gold / errors; rebuildable, do not hand-edit |
| Change trail | `docs/changes/{module}.md` | One per module, append-only change entries |
| Gate | `scripts/hooks/pre-commit`, installed as `.git/hooks/pre-commit` | Calls `ng/tools/pre_commit_gate.py` |

### 9.2 Skill Map (stage → skill)

> For stage definitions see `docs/rules/DEVELOP-FLOW.md` §1 (ten stages) and §1.1 (stage 4 substeps). The table below links only skills that **actually exist in the skill library**; the names must be resolvable, `pre_commit_gate.py` checks them.
> Usage: before entering a stage, load that stage's skill (`skill_view`) and execute by its Phase or Step. Replacing a skill flow with "the usual approach" is forbidden.

| Stage | Skill | When to use |
|---|---|---|
| 1 Requirement analysis | `requirement-analysis`; for legacy rework start with `legacy-recon`; feasibility unknown → `feasibility-probe` | Vague request / taking over an unfamiliar repository / choosing between options A and B |
| 2 Solution design | `system-architecture` (architecture and ADR), `project-doc-system` (document system), `api-contract-design`, `data-layer-design`, `identity-access-design`, `secrets-management`, `threat-modeling`, `ui-foundation-design` | Setting up architecture / defining documents / changing a contract |
| 3 Task breakdown | No dedicated skill: break down by the `coding-flow` seven-step execution order; to delegate to a subagent use `coder-profile-delegation` | Down to a granularity that "can be verified independently" |
| 4 Coding implementation | `coding-flow` (flow), `minimal-diff` (which lines to change), `engineering-naming-discipline` (naming); MCP / tool services → `mcp-server-development` | Must be loaded before every code change |
| 4a–4d Coding substeps | Same as above; 4b interface implementation additionally loads `api-contract-design`; 4d wiring self-test additionally loads `http-e2e-testing` | Advance 4a→4b→4c→4d step by step; **no large parallel changes** |
| 5 Unit testing | `tdd-discipline` (RED-GREEN-REFACTOR); when stuck → `python-debugging` / `node-debugging` | A failing test comes before production code |
| 6 Code review | `pre-commit-gate` (commit gate), `independent-review` (third-party verdict), `ai-code-audit` (security of AI-generated code) | Before every commit / delivery |
| 7 Integration testing | `verify-data-layer` (independent verification of a data-layer handover), `performance-benchmarking` (data-volume baseline) | When changing a data pipeline or the partition layout |
| 8 Pre-release verification | This project has **no interface and no pre-release environment**, so interface walkthroughs and accessibility audits do not apply; end-to-end verification runs through `make run` plus the CI data-quality stage | When artefacts or the partition layout change |
| 9 Deployment and release | `ci-cd-delivery`; commit discipline `git-submit` | When there is a pipeline / multiple environments |
| 10 Live observability | `observability-sre` (SLO / alerting), `incident-postmortem` (incident postmortem), `performance-benchmarking` | When there is a production environment |
| Cross-cutting (any stage) | `doc-code-drift` (contract and code drift), `post-change-cleanup` (post-change cleanup), `module-retirement` (retiring an old module), `docs-writing-discipline` (before writing documents and reports); daily discipline `ops-basics-discipline` / `path-ssot-governance` / `secret-sprawl-audit` | Stage completion / before delivery / when drift is found |
| Any stage (specific to this type) | `data-layer-design` (schema and query plan); `verify-data-layer` (independent verification of a data-layer handover); `pg-query`; `performance-benchmarking` | When tables / partitions / a data pipeline are involved |

## 10. Rule Provenance and Deviations

- **Provenance**: this project's rules = this file + the `docs/rules/` four-piece set. The four-piece set is assembled verbatim by the assembly tool in three layers: **baseline → tech stack → project type** (`rules_assembly.py`). Assembly only lowers heading levels; it does not change the text of an upper layer, nor delete an upper-layer entry. **Not hand-edited per project**.
- **Deviation registration**: every place where this project disagrees with the upstream rules is listed item by item in this section, in four columns: issue / upstream wording / this project's practice / disposition. "Disposition" must point to a document anchor that actually exists; writing only "already explained" is forbidden.
- A deviation not yet resolved counts as a **known issue**: register it in `docs/business/KNOWN-ISSUE.md` and leave an index row here.

**Deviations registered for this project** (every place where this project disagrees with the upstream rules):

| Issue | Upstream wording | This project | Disposition |
|---|---|---|---|
| Environment setup | Commit a `uv.lock` lock file | Dependencies declared in `pyproject.toml`; venv plus pip install; no lock file | See "Deviation rationale and cost" below |
| Orchestration directory | `dags/` holds task orchestration and dependency assembly | No scheduler; orchestration doubles as the in-package entry point `src/demo_gx/cli.py` | See "Data-processing skeleton applicability boundaries" below |
| Transformation module split | `src/{pkg}/pipelines/{domain}/`, by business domain | Split by pipeline stage: `ingestion` / `validation` / `transformation` / `curation` | See "Data-processing skeleton applicability boundaries" below |
| Contract model layer | `src/{pkg}/models/` holds schema and type definitions | Field contract in `config/schema.yaml`, table contracts in `docs/tables/`; no Python model layer | See "Data-processing skeleton applicability boundaries" below |
| SQL assets | `sql/migrations/` incremental DDL and `sql/transforms/` | No `sql/` assets and no SQL engine; Parquet is written straight to disk. Iceberg DDL exists as an archived reference only and is not on the execution path | See "Data-processing skeleton applicability boundaries" below |
| Test directory | `tests/` mirrors `src/` | Flat `tests/test_{module}.py` | See "Data-processing skeleton applicability boundaries" below |
| Data layer naming | `ods` to `dwd` to `dws` to `ads` | Bronze to Silver to Gold | See the `data layer mapping` term in `docs/business/DOMAIN-LANGUAGE.md` |
| Coverage gate | Projects with CI require unit-test coverage of 80% or more | No coverage tooling enabled; the floor is "at least one assertion per requirement" | See `docs/business/KNOWN-ISSUE.md#coverage-gate-off` |
| Computation and catalog entry point | `catalog.py` unifies session and table loading | No catalog: local Parquet, the session concept does not exist | See `docs/business/KNOWN-ISSUE.md#no-catalog` |
| Snapshot and compaction policy | Every table configures a retention period and a compaction job | Partition directories are overwritten in place, no snapshot layer | See `docs/business/KNOWN-ISSUE.md#no-snapshot-lifecycle` |
| Amount precision | Amounts must not use `float`; use DECIMAL with a single conversion | The `amount` column is pandas `float64` | See `docs/business/KNOWN-ISSUE.md#amount-float` |
| Table contract approval | Contract frontmatter carries `status: approved` and CI blocks unreviewed migrations | Local reference implementation, no approval chain | See `docs/business/KNOWN-ISSUE.md#table-contract-approval` |
| Stage model | The baseline ten stages, including pre-release, deployment and observability | Stage 8 is replaced by an end-to-end smoke run; stages 9 and 10 do not apply | See "Stage model applicability boundaries" below |
| Clock reads outside data stamping | Red line 10 forbids code reading the system's current time | `common/metrics.py` and `common/logger.py` still read the clock, for telemetry only; no data-stamping site reads it | See `docs/business/KNOWN-ISSUE.md#clock-reads-outside-data-stamping` |

**Stage model applicability boundaries**: this project is a local reference implementation. It has no pre-release environment, no production deployment, and no release chain beyond CI. Of the baseline ten stages, stages 1-7 apply in full; stage 8 is replaced by an end-to-end smoke run, and its interface checks do not apply; stages 9 and 10 do not apply. The CI gate and commit discipline still apply.

**Data-processing skeleton applicability boundaries**: the data-processing structure skeleton assumes a technology stack of Spark plus Iceberg plus a scheduler. This project is a single-machine Pandas reference implementation (for the choices and the rejected alternatives see `docs/business/PROJECT.md`), so the skeleton entries that depend on that stack are registered here as inapplicable:

- **No `dags/`**: there is no scheduler, so orchestration doubles as the in-package entry point and `python -m demo_gx.cli` is the invocation. The skeleton's "merging is allowed" boundary requires all three conditions; this project **satisfies only the first**: there is one entry, but it hardcodes the three `--env` values and their default, so condition two fails, and `tests/` imports four pipeline components as libraries (`GoldBuilder`, `DataCleaner`, `Deduplicator`, `SchemaValidator`), so condition three fails as well. The project still merges, because there is only this one entry and no second caller; the cost is that the entry carries command-line side effects, and a future split would have to separate argument parsing from library code.
- **Transformation modules split by pipeline stage**: the project has a single business domain, events, so splitting by domain would produce single-element directories; the stage boundaries are the real reusable boundaries. `common/` is the cross-stage shared layer: it is not in the skeleton's list, but it matches the intent of `utils/`.
- **No `src/demo_gx/models/`**: the single source of truth for the field contract is `config/schema.yaml`, and table contracts live in `docs/tables/`. A separate Python model layer would create a second definition.
- **No `sql/`**: there is no SQL engine, so schema changes are kept in step through `schema.yaml` and the table contracts. Iceberg DDL does exist in the repository, but only under `docs/archive/` as a production-shape reference, and it is not on the execution path.
- **Tests are flat rather than mirroring `src/`**: one file per module; mirroring would add a directory level for each of the four test files. Names do not mirror their module exactly: `test_validation.py` covers `validation/schema_validator.py`.
- **Layering keeps Bronze / Silver / Gold**: the mapping to the upstream `ods` / `dwd` / `dws` / `ads` is recorded under the `data layer mapping` term in `docs/business/DOMAIN-LANGUAGE.md`.

**Modules with no direct unit test**: `ingestion/reader.py`, `validation/error_envelope.py`, `common/*` and `cli.py` currently have end-to-end smoke coverage only, with no direct unit tests. This is the concrete form of `#coverage-gate-off`.

**Deviation rationale and cost**

Cost and rollback for the six skeleton rows above: moving to Spark plus Iceberg means the first four items need their directories rebuilt and the logic re-placed inside them; the last two are naming and organisation differences with zero rollback cost.

Cost and rollback for the remaining rows:

- **Environment setup**: uv is not installed in this environment and the upstream fallback is an equivalent lock kept in a plain requirements file, whereas this project folds the dependency declaration into `pyproject.toml` and commits no lock file. Cost: dependency resolution is not pinned, so a fresh environment can resolve different versions. Rollback cost: low, add `uv lock`, or pin the environment with `pip freeze` into a requirements file.
- **Coverage gate**: no coverage tooling is enabled. Cost: a regression that no test asserts can pass CI unnoticed. Rollback cost: low, add pytest-cov and a threshold.
- **Computation and catalog entry point**: there is no catalog and no session concept to unify. Cost: introducing Iceberg later means adding a `catalog.py` and re-pointing every read and write. Rollback cost: medium.
- **Snapshot and compaction policy**: partitions are overwritten in place. Cost: no point-in-time recovery and no small-file compaction. Rollback cost: medium, re-registering the data as an Iceberg table.
- **Amount precision**: the `amount` column is `float64`, which cannot represent decimal amounts exactly, so equality comparisons and sums are approximate. Cost: monetary rounding has to be handled by explicit rounding at the boundary. Rollback cost: medium, switch the column to `decimal.Decimal` and re-lock the affected tests and the table contract.
- **Table contract approval**: no approval chain exists. Cost: nothing blocks an unreviewed contract change. Rollback cost: low, add a CI check on the frontmatter.
- **Stage model**: stages 9 and 10 have no practice here. Cost: release and observability discipline is not exercised. Rollback cost: both stages must be reinstated once this becomes a deployed service.
- **Clock reads outside data stamping**: `common/metrics.py` and `common/logger.py` still read the clock, for telemetry only; no data-stamping site reads it. Cost: telemetry timestamps are not reproducible across runs. Rollback cost: low, inject the run instant into the telemetry path too.

- **Deviation discipline**: the standard practice is the **default** and a deviation is the exception. A deviation is allowed, but it must satisfy all three conditions at once:
  - ① Register it item by item in this section, with the "disposition" column pointing to an anchor that actually exists.
  - ② State **why the standard practice is not adopted**; empty reasons such as "this project is special" are forbidden.
  - ③ Note the cost and the rollback cost.
- **Silently lowering the standard without registering it is forbidden**. "This is just a one-off case" is not a reason for exemption from registration.
- **Vertical bars inside table cells must be escaped**: when writing content that contains a vertical bar such as `a|b` in a cell, write it as `a\|b`, otherwise Markdown breaks that cell.
- **The structure of this file is fixed**: eleven sections in total, §0–§10, and **no new section may be added**. Project-level additions go into the corresponding section. Red lines go into §3, conduct into §4, output requirements into §5. Maps go into §9.1 / §9.2, and any disagreement with upstream goes into this section's deviation table. A self-added section would drift apart from the existing ones, and the machine gate warns about it. In particular, do not add another "anti-pattern" comparison table that duplicates §3.
