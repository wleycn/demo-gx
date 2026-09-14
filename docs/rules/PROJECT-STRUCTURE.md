# PROJECT-STRUCTURE — Project Structure Standard (Python)

## 1. Directory Structure (General Skeleton)

```text
{project}/
├── README.md                 # Human entry point (must stay at root)
├── AGENTS.md                 # AI coding constraints (unique name at project root)
├── pyproject.toml            # Sole entry point for dependencies and toolchain (ruff/mypy/pytest)
├── uv.lock                   # Dependency lock, committed with the repo 🔴 (without uv use requirements.txt for equivalent locking, see §3)
├── src/{pkg}/                # Product code (an installable package, not flat scripts)
│   ├── __init__.py
│   ├── config.py             # 🔴 single entry point: env / secret loading, typed config
│   ├── <domain>/             # Split by business module
│   └── {shared}/             # Single entry point for cross-module shared capabilities
├── scripts/                  # Entry scripts and thin shells (forward only, no business logic)
├── tests/                    # Tests, mirroring the src structure
│   └── fixtures/
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

> **Why `src/` and `scripts/` are not merged**: the two are invoked in different ways. `src/` is library code that is `import`ed: possibly installed, packaged and reused in many places. `scripts/` are entries invoked **as commands** by shell / cron / a scheduler, containing `if __name__ == "__main__"` and argument parsing. The benefits of separating them: ① library code does not carry command-line side effects because of an entry; ② changing scheduling shell arguments does not affect the library; ③ permission and path assumptions differ (a shell may depend on env / argv, a library must not).
> **Boundary where merging is allowed** (keep only `src/` only when all three hold): ① there are only 1-2 entries; ② the entries contain no scheduler-specific assumptions (hardcoded absolute paths, fixed env names); ③ there is no library code that would be reused outside the shell. If any one fails -> keep them separate. After merging, use `python -m {pkg}.cli` as the entry and still write no script files.
| `tests/` | Tests | Placing production code; locating the project root with `Path.cwd()` (use `Path(__file__).parent.parent` instead) |
| `notebooks/` | Exploration and analysis | Being referenced by production scheduling; committing outputs and plaintext credentials |
| `docs/` | Standards and business documents | Drifting from the code (changing code must be synced) |
| `docs/changes/` | Change trail (one per module, append-only) | Writing non-change content (explanations, attachments, temporary files) |

## 3. Single Entry Point Files (Single Entry Point Principle)

> **The path follows the project structure layer**: `{shared}/` is the cross-module capability directory, for example `utils/` or `common/`. The module name follows the structure layer as well. The constraint is **one implementation per capability**, not one particular file name. A capability the project genuinely does not need does not require a module. Once it is needed, it goes through the entry point in this table.

| Single entry point | File | Responsibility |
|---|---|---|
| Configuration and credentials | `config.py` | env / secret loading, typed output (Pydantic Settings), with validation |
| Paths | `path_anchor.py` / `path_resolve.py` | **No** `Path.home()` / `expanduser` / direct `import dotenv`; unified `load_shared_env()` |
| Paths (project root) | `Path(__file__).resolve().parents[k]` | Projects always derive from `__file__` and **do not depend on an external shared library** (a shared `path_anchor` applies only to system scripts hosted under a unified infrastructure directory) |
| Logging | `{shared}/log.py` | `get_logger(__name__)`, with run_id / target / row count / elapsed time |
| Retry | `{shared}/retry.py` | Unified retry and conflict handling; **unified gate**: all four categories -- non-zero exit / empty output / timeout / exception -- trigger |
| Data access | `{shared}/db.py` | Unified connection and query entry (for PG operations see skill `pg-query`) |
| Redaction | `{shared}/mask.py` | Phone numbers / ID documents / addresses / bank cards |

> 🔴 **The same capability must not be reimplemented outside the single entry point** (including retry, redaction regexes, connection parameter tuning, logging handlers). New scripts must pass `path_governance_audit.py` with zero violations.

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

## 7. Test and Service Layer Structure

> **Skip if not applicable**: a project without a service layer (`serving/`) skips the service layer part of this section (cross-shape content: if not applicable to this project, skip it as a whole).

- `tests/` and `src/` **mirror** each other; small fixture samples go in `tests/fixtures/`
- Tests isolate external services (DB / Qdrant etc.) by **injecting distinct resource names via env** and do not connect to production
- If a service layer (`serving/`) is present: API and business logic are separated, with a unified response body + pagination conventions, and authentication reuses the unified middleware (hand-written checks inside endpoints are forbidden)

## [Layer: data-processing]PROJECT-STRUCTURE — Project Structure (Data-Processing Projects)

### 1. Structure Skeleton (additions on top of `python/PROJECT-STRUCTURE.md`)

```text
{project}/
├── dags/                        # orchestration: dependency assembly only, no transform logic 🔴
├── src/{pkg}/pipelines/{domain}/ # read/write transform logic (by business domain)
├── src/{pkg}/models/            # schema / contract models, aligned with the table contract 🔴
├── src/{pkg}/catalog.py         # 🔴 single entry point: session, catalog, table loading, maintenance ops
├── sql/migrations/              # V{N}__{desc}.sql incremental DDL
├── sql/transforms/              # SQL transform scripts (by business domain)
├── docs/tables/{table}.md       # table contract: one md per table
└── tests/{fixtures,pipelines}/
```

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
| Compute and catalog | `catalog.py` | Session / catalog / table loading / snapshot expiry / compaction trigger |
| Config and credentials | `config.py` | env / secret loading, typed output |
| Money | `{shared}/money.py` | cents↔yuan conversion, rounding mode |
| Masking | `{shared}/mask.py` | phone number / ID document / address masking |
| Quality | `{shared}/quality.py` | `check_table(df, rules)` |
| Logging and metrics | `{shared}/log.py` | logger + run metrics (row count / partitions / elapsed) |

🔴 Outside the single entry points you must not reimplement equivalent capabilities on your own (including session parameter tuning, masking regexes, retry logic).
