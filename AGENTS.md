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
- **Storage engine**: local filesystem, no database. Every environment writes under one root, `data/{env}/`, split by direction: `input/` holds what is fed in, `output/` holds Bronze / Silver / Gold / errors / logs. The root is the `storage.base_path` config item
- **Orchestration**: `src/demo_gx/cli.py`, invoked as `python -m demo_gx.cli`, no scheduler. The partition parameter is injected by `--event-date` and the run timestamp by `--run-timestamp`; the entry point reads the system clock once, and only when `--run-timestamp` was not injected
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
- Add a `[AI-GENERATED] model=<m> date=<d> reviewed_by=<human>` comment at the head of each changed **code** file. Two kinds of file are exempt: what an assembly tool generates, and documents. Their provenance is the commit marker below plus the change trail.
- `reviewed_by=pending` means no human has reviewed the file yet; the reviewer replaces it with their own name.
- An agent-authored commit message must contain `[AI]`; a human commit carries no marker. The machine gate blocks an agent-session commit whose message lacks `[AI]`, and warns about a changed code file without the header. The rule therefore does not rest on anyone remembering it.
- A single change must not exceed **40%** of the file total. If it exceeds that, split it into several changes and verify step by step.
- Comments and docstrings must be changed in the same commit as the code. Comments that contradict the implementation must not be left behind. A comment explains "**why**", it does not restate "what". For details see the comments section of `docs/rules/CODING-STANDARD.md`.
- Before writing documents, writing reports or writing delivery notes, load the `docs-writing-discipline` skill and read through once against its checklist before delivering
- Migration scripts must be reviewed line by line by a human, with a confirming comment in the PR

## 6. Change Trail

For a functional or contract change, **append** one entry to `docs/changes/{module}.md`. The entry slug has the same name as the branch; for the entry template see `docs/rules/DEVELOP-FLOW.md` §4. `{module}` takes the top-level module directory name under `src/demo_gx/`, namely `ingestion`, `validation`, `transformation`, `curation`, `common`; a non-functional change lands in `engineering.md`. That directory holds **entry files only** — no README, notes or attachments. For the module list see the §9 project map.

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


## 9. Project Map (file index)

> answers "where is the thing"
> Generation rule: fill the table below with files that **actually exist in the project**, and delete inapplicable rows. Paths in the table must be really reachable. The machine gate checks the referenced files under `docs/`, `src/`, `scripts/`, `tests/` and `data/` plus the root files it names. A directory path or a `config/*.yaml` entry has to be verified by the reviewer.

| Category | Location | Purpose |
|---|---|---|
| Human entry | `README.md` | What this is / how to get started (5-second test) |
| AI constraints | `AGENTS.md` (this file) | Red lines and conduct, highest precedence |
| Rules | `docs/rules/` | Four-piece set: structure / coding / flow / acceptance |
| Business documents | `docs/business/` | Project description / modules / data / interfaces / glossary / changes / known issues |
| Deviation register | `docs/business/KNOWN-ISSUE.md` | Known pitfalls / design decisions / every disagreement with the upstream rules, registered item by item (lowering the standard without registering it is forbidden) |
| Interface contract | `docs/business/INTERFACE-DESIGN.md` | CLI arguments, artefact paths, error envelope: the single source of truth |
| Data contract | `docs/business/DATA-DESIGN.md` | Layered data flow, table structures, partitioning and rerun semantics |
| Table contracts | `docs/tables/{table}.md` | One file per table: grain / primary key / dedup method / lifecycle |
| Production-shape DDL | `sql/reference/iceberg_target_shape.sql` | Target Iceberg DDL (Spark SQL) for Bronze / Silver / Gold; a reference asset that nothing executes |
| Field contract source | `config/contract/schema.yaml` | Field types / required / enums / regular expressions |
| Environment config | `config/env/dev.yaml`, `config/env/test.yaml`, `config/env/prod.yaml` | Storage paths / logging / metrics / alerting |
| Product code | `src/demo_gx/` | Installable package; entry `cli.py`, modules `common` / `ingestion` / `validation` / `transformation` / `curation` |
| Dependencies and toolchain | `pyproject.toml` | The single entry point for dependency declarations, packaging and pytest config |
| Sample data generation | `scripts/generate_sample_data.py` | Generates `data/{env}/input/sample_data.json` from a fixed seed, carries no business logic |
| Artefact verification | `scripts/check_data.py` | Read-only verifier for a run's output, behind `make check-data`; pairs each layer with `docs/tables/{table}.md` |
| Artefact inspection | `scripts/show_data.py` | Read-only viewer for a run's output, behind `make show-data`; shows columns, partitions and rows |
| Run artefacts | `data/{env}/output/` | Bronze / Silver / Gold / errors / logs; rebuildable, do not hand-edit. The layer skeleton is committed, the data is not |
| Change trail | `docs/changes/{module}.md` | One per module, append-only change entries |
| Gate | `scripts/hooks/pre-commit` and `scripts/hooks/commit-msg`, installed as `.git/hooks/pre-commit` / `.git/hooks/commit-msg` | Calls `ng/tools/pre_commit_gate.py` |

## 10. Skill Map (stage → skill)

> answers "which skill to use at this stage".
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

