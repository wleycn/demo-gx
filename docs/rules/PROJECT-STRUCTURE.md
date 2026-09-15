# PROJECT-STRUCTURE — Project Structure Standard (Python)

## 1. Directory Structure (Example Shape, Adopt as Needed)

> What follows is the **example shape** of a Python project, not a checklist in which every line is mandatory. A line marked "only when ..." is created only when that condition holds; unmarked lines are general.
> **The authoritative source for the project's actual structure is the project map in the root `AGENTS.md` and the directory layout in `docs/business/PROJECT.md`.** This document only says, once a directory exists, where it goes and which single entry point owns it.
> When the project genuinely does not need a kind of directory, do not create one.

```text
{project}/
├── README.md                 # Human entry point (must stay at root)
├── AGENTS.md                 # AI coding constraints (unique name at project root)
├── pyproject.toml            # Sole entry point for dependencies and toolchain (ruff/mypy/pytest)
├── uv.lock                   # Dependency lock (only when using uv; without uv use requirements.txt for equivalent locking, see §5)
├── src/{pkg}/                # Product code (an installable package, not flat scripts)
│   ├── __init__.py
│   ├── <domain>/             # Split by business module
│   └── {shared}/             # Single entry point for cross-module shared capabilities: config.py / logger.py / mask.py, see §3
├── scripts/                  # Entry scripts and thin shells (only when there are entries invoked as commands by shell / cron; forward only, no business logic)
├── tests/                    # Tests, mirroring the src structure
│   └── fixtures/             # Small sample files (only when tests need sample data on disk)
└── docs/
    ├── rules/                # This four-file set
    ├── business/             # business documents: PROJECT / DATA-DESIGN / MODULE-DESIGN / INTERFACE-DESIGN / DOMAIN-LANGUAGE / CHANGELOG / KNOWN-ISSUE
    └── changes/              # Change trail (one per module, append-only)
```

## 2. Directory Responsibilities and Prohibitions

| Directory | Responsibility | Prohibited |
|---|---|---|
| `src/{pkg}/` | Product code | Hardcoded configuration; reading `os.environ` directly in scattered places |
| `scripts/` | Entries / thin shells (cron shells only forward via subprocess) | **Carrying business logic** (the real implementation must be unique) |
| `tests/` | Tests | Placing production code; locating the project root with `Path.cwd()` (use `Path(__file__).parent.parent` instead) |
| `notebooks/` | Exploration and analysis | Being referenced by production scheduling; committing outputs and plaintext credentials |
| `docs/` | Standards and business documents | Drifting from the code (changing code must be synced) |
| `docs/changes/` | Change trail (one per module, append-only) | Writing non-change content (explanations, attachments, temporary files) |

## 3. Single Entry Point Files (Single Entry Point Principle)

| Single entry point | File | Responsibility |
|---|---|---|
| Configuration and credentials | `{shared}/config.py` | env / secret loading, typed output (Pydantic Settings), with validation |
| Paths | `Path(__file__).resolve().parents[k]` | Projects always derive from `__file__` and **do not depend on an external shared library** |
| Logging | `{shared}/logger.py` | `get_logger(__name__)`, with run_id / target / row count / elapsed time |
| Retry | `{shared}/retry.py` | Unified retry and conflict handling; **unified gate**: all four categories -- non-zero exit / empty output / timeout / exception -- trigger |
| Data access | `{shared}/db.py` | Unified connection and query entry (for PG operations see skill `pg-query`) |
| Redaction | `{shared}/mask.py` | Phone numbers / ID documents / addresses / bank cards |

> 🔴 **The same capability must not be reimplemented outside the single entry point**

## 4. Naming Conventions

| Object | Rule | Example |
|---|---|---|
| Module / file | `snake_case` | `order_sync.py` |
| Class / Pydantic model | `PascalCase` | `OrderRecord` |
| Constant | `UPPER_SNAKE` | `MAX_RETRY` |
| Test file | `test_*.py`, same name as the source module | `test_order_sync.py` |
| Environment variable | `UPPER_SNAKE`, with a project prefix | `APP_DB_URL` |

> For finer naming discipline (real / sufficient / memorable: faithfulness, expressiveness, elegance) see skill `engineering-naming-discipline`.

## 5. Dependencies and Environment

- 🔴 **An independent venv per project** (under a `PEP 668` environment, installing packages into the system python always fails; see skill `python-project-env-setup`)
- 🔴 Dependencies go only into `pyproject.toml`, with the lock file committed to the repo; **ad-hoc `pip install` is forbidden** (the root cause of environment drift)
- 🟡 Installing packages on a domestic network goes through a mirror source (see skill `china-pip-mirrors`)
- 🔴 At runtime only read env; do not hardcode absolute paths in the code

## 6. Type-Specific Structure Is Not Repeated at the Stack Layer

> This layer covers only the structure that follows from the language and toolchain. The directory skeleton specific to a project type is given by the project-type section at the end of this file, marked with a layer label such as `[Layer: <type>]`. Restating it here would let the two copies drift apart.

## 7. Test and Service Layer Structure

> **Skip if not applicable**: a project without a service layer (`serving/`) skips the service layer part of this section (cross-shape content: if not applicable to this project, skip it as a whole).

- `tests/` and `src/` **mirror** each other; small fixture samples go in `tests/fixtures/`
- Tests isolate external services (DB / Qdrant etc.) by **injecting distinct resource names via env** and do not connect to production
- If a service layer (`serving/`) is present: API and business logic are separated, with a unified response body + pagination conventions, and authentication reuses the unified middleware (hand-written checks inside endpoints are forbidden)

## [Layer: data-processing]PROJECT-STRUCTURE — Project Structure (Data-Processing Projects)

### 1. Structure Skeleton (additions on top of `python/PROJECT-STRUCTURE.md`, adopt as needed)

> A data-processing project has exactly **three built-in parts**: the table contract (`docs/tables/`, see §3), the layering dependency direction (see §2) and the configuration directory layout (see below). Everything listed below appears **only with a given technology choice**; a line marked "only when ..." is created only when that condition holds.
> A local Pandas pipeline, for example, has no scheduler (so no `dags/`), no catalog (so no `catalog.py`) and no SQL (so no `sql/`). Not creating these directories is not a deviation.
> The project's actual structure is in the project map of the root `AGENTS.md` and in `docs/business/PROJECT.md`.

```text
{project}/
├── config/                      # configuration, split by purpose
│   ├── env/{env}.yaml           # one file per environment: storage paths / logging / metrics / alerting 🔴 configuration is read from here only
│   └── data/schema.yaml         # data contract source: field types / required / enums / patterns / ranges
├── dags/                        # orchestration: dependency assembly only, no transform logic 🔴 (only when a scheduler exists, e.g. Airflow / Dagster)
├── src/{pkg}/pipelines/{domain}/ # read/write transform logic (only when a domain needs a further pipeline split; the domain directory itself comes from the stack layer)
├── src/{pkg}/models/            # schema / contract models, aligned with the table contract 🔴 (only when the contract becomes code models)
├── src/{pkg}/catalog.py         # 🔴 single entry point: session, catalog, table loading, maintenance ops (only when there is a catalog, e.g. Iceberg / Hive)
├── sql/migrations/              # V{N}__{desc}.sql incremental DDL (only when the table structure is managed by SQL migrations)
├── sql/transforms/              # SQL transform scripts, by business domain (only when transforms are written in SQL)
├── docs/tables/{table}.md       # table contract: one md per table
└── tests/{fixtures,pipelines}/  # only when tests need sample data on disk / per-pipeline subdirectories
```

> The configuration directory splits by **purpose**: `env/` holds the runtime parameters that vary per environment (one file per environment), `data/` holds the data contract, which does not vary by environment. Both are **built-in**: they do not appear or disappear with a technology choice. `config/data/schema.yaml` is the **single source** of the field contract; the table contract refers to it instead of restating it.

| Directory | Responsibility | Forbidden |
|---|---|---|
| `dags/` | Task orchestration and dependency assembly | Writing transform logic, reading/writing tables directly |
| `pipelines/` | Read/write transforms by business domain | Orchestrating dependencies, hardcoded config |
| `models/` | schema and type definitions | Business logic |
| `{shared}/` | Single entry point for cross-module shared capabilities | Referencing concrete business modules |
| `sql/migrations/` | schema evolution incremental scripts | Modifying an already-committed number, manual execution in production |
| `notebooks/` | Exploratory analysis | Referenced by production scheduling, committing outputs and credentials |

### 2. Layering and Dependency Direction 🔴

- Business domains align with source systems (OLTP domains), e.g. `trade / product / user / marketing / fulfillment`
- Data layering: `ods` (ingest) → `dwd` (cleaned detail) → `dws` (subject aggregates) → `ads` (application)
- 🟡 The layer names above are **example naming** and follow the project (for example Bronze / Silver / Gold); the constraint is a **single dependency direction**, not a single set of names
- 🔴 The dependency direction is **only** `ods→dwd→dws→ads`; reverse dependencies and cross-layer references (e.g. ads reading ods directly) are forbidden
- 🟡 Same-layer cross-domain references go through dws shared subjects; reading each other's dwd detail is forbidden

### 3. Table Contract (one file per table) 🔴

Each table gets one `docs/tables/{table}.md`. It must record: layer / subject / grain / business key / **deduplication method** / partition spec (with rationale and estimated per-partition data volume) / monetary unit convention. It must also record: PII fields and masking method / lifecycle (snapshot retention, compaction strategy, retention period) / freshness SLA and owner / upstream and downstream dependencies / **quality rule list**.

The top of the contract records the approval state via frontmatter:

```yaml
---
status: draft | approved
approved_by: [@owner1, @finance-owner]
approved_at: 2026-09-11
version: 3
---
```
- CI check: when `status != approved` the corresponding migration is blocked from merging into `main`
- **When the contract changes, status is automatically reset to `draft`** and re-approval is required

### 4. Naming Conventions (additions on top of the stack standard)

> The table name and field rows are general to data-processing projects; the DAG and migration rows apply **only when the project has a scheduler / SQL migrations**.

| Object | Rule | Example |
|---|---|---|
| Table name | `{layer}_{domain}_{entity}_{cycle}` | `dwd_trade_order_di` (`_di` daily incremental / `_df` daily full) |
| Field | snake_case | `pay_amount` / `created_at` |
| Model class | PascalCase, aligned with the table contract | `DwdTradeOrderDi` |
| DAG | `dag_{layer}_{domain}_{entity}_{cycle}` | `dag_dwd_trade_order_di` |
| Migration | `V{N}__{desc}.sql` | `V12__create_dwd_trade_order_di.sql` |

### 5. Single Entry Points (single-entry principle)

> **The path follows the project structure layer**: `{shared}/` is the cross-module capability directory, for example `utils/` or `common/`. The module name follows the structure layer as well. The constraint is **one implementation per capability**, not one particular file name. A capability the project genuinely does not need does not require a module. Once it is needed, it goes through the entry point in this table.

| Single entry point | File | Responsibility |
|---|---|---|
| Compute and catalog | `catalog.py` | Session / catalog / table loading / snapshot expiry / compaction trigger (only when there is a catalog) |
| Config and credentials | `{shared}/config.py` | env / secret loading, typed output |
| Money | `{shared}/money.py` | cents↔yuan conversion, rounding mode (only when money amounts are converted) |
| Masking | `{shared}/mask.py` | phone number / ID document / address masking (only when PII fields exist) |
| Quality | `{shared}/quality.py` | `check_table(df, rules)` (only when there are quality rules) |
| Logging and metrics | `{shared}/logger.py` | logger + run metrics (row count / partitions / elapsed) |

🔴 Outside the single entry points you must not reimplement equivalent capabilities on your own (including session parameter tuning, masking regexes, retry logic).
