# CODING-STANDARD — Coding Standard (Python)

> **Level**: 🔴 red line (violation blocks) | 🟡 strongly recommended. Examples `✅ Correct` / `❌ Wrong`.

## 1. Python Language Standards

- 🔴 All functions carry **type hints**, `tests/` included; CI runs `mypy` (at least strict on new modules)
- 🔴 **Bare generic containers are forbidden**: `-> tuple:` / `x: dict` must spell out their type arguments (`tuple[str, int]` / `dict[str, Any]`) -- a bare container switches type checking off; enforced by `mypy --disallow-any-generics`
- 🔴 **Do not write `from __future__ import annotations`**: with a runtime floor of 3.10 the `X | None` form and builtin generic annotations already work at runtime, and one more deferred-evaluation layer only trips `get_type_hints` and framework reflection
- 🟡 Unified `ruff` lint + format, configuration centralized in `pyproject.toml` (no scattered flake8/pylint configs); on top of the baseline set `E/W/F/I/UP/B/SIM/C4/DTZ/G/BLE/RUF` enable `N` (naming) and `D` (`convention="google"`); ignore `D203`, `D213`, `D401` and `D202`. The first two contradict the Google convention; `D401` demands the imperative mood while Google allows either; `D202` deletes the blank line after a docstring, which §13.1 of this file requires.
- 🟡 `tests/` turns `D1xx` off via `per-file-ignores`: a test function name is its own description, so a docstring is not required there
- 🟡 **Naming**: the whitelist is pandas' idiomatic short names (`df`), counters and iterators (`i`/`j`/`k`), the exception `e` and the file `f`; **invented abbreviations made by deleting letters are forbidden** (`evt_date` -> `event_date`, `dup_dir` -> `duplicates_dir`); a name colliding with a keyword takes a trailing underscore (`class_`). Basis: PEP 8 (which bans only `l`/`O`/`I`) and Google's "avoid abbreviation". **No lint rule can catch a letter-deleting abbreviation -- this one rests on review**
- 🔴 Production code **must not use `print`**; uniformly use `{shared}/logger.get_logger`
- 🔴 **No bare `except:`** and no `except Exception: pass` (silent failure = troubleshooting blind spot)
- 🔴 Dependencies must go into `pyproject.toml` with the lock file committed; ad-hoc `pip install` is forbidden
- 🟡 Prefer the standard library and existing single entry point files; do not pull in a heavy dependency for a single-purpose need
- 🔴 Comments and docstrings are maintained together with the code: explain "**why**", do not restate "what" (see §13)

## 2. Configuration and Credentials

- 🔴 Credentials / endpoints / paths are loaded via `config.py` from env or a secret manager; **plaintext must never appear in code, notebooks or scheduling parameters**
- 🔴 Paths must not use `Path.home()` / `expanduser` / a direct `import dotenv` -- a project derives its anchor from `__file__`
- 🟡 All configuration items have typed defaults and validation (Pydantic Settings), so configuration errors surface at startup

## 3. Error Handling and Retry

- 🔴 **Unified gate**: non-zero exit / empty output / timeout / exception -- **all four** categories must trigger a fallback or an alert; checking only the non-zero exit is not acceptable
- 🔴 A failure must **leave a trail** (log + state file/DB table); silently swallowing exceptions is forbidden
- 🔴 A retry goes through the shared retry module (`{shared}/retry.py`); **retry must presuppose idempotency** (otherwise retry = creating duplicate data)
- 🟡 External calls must have a timeout; a network call without a timeout counts as a defect

```python
# ✅ Correct: explicit classification + trail + idempotent
try:
    r = call_api(url, timeout=10)
    if r.status_code != 200:
        raise ApiError(f"http {r.status_code}")
except (ApiError, TimeoutError) as e:
    log.warning("call failed: %s", e)
    write_state("failed", reason=str(e))
    raise
```

```python
# ❌ Wrong: silent failure + no timeout
try:
    r = call_api(url)
except Exception:
    pass
```

## 4. Logging and Observability

- 🔴 Uniform `get_logger(__name__)`; no print and no self-built handlers
- 🟡 Key task runs emit metrics: `run_id` / target object / row count / elapsed time; failures go through the unified alert channel
- 🟡 Log fields are structured and searchable (eases troubleshooting by grepping session id / run_id)

## 5. External I/O and Batch Operations

- 🔴 **Probe the rate limit first** before batch-requesting an external API (see skill `probe-rate-limit-before-bulk`); never hit it flat out
- 🔴 **Read back and verify** after writing to an external system (a successful write does not mean it took effect); declared totals must be re-checked
- 🟡 Process large result sets in a streaming fashion; unconditional full `list(...)` loading is forbidden

## 6. Numbers and Amounts

- 🔴 Amounts must not be stored or computed as `float`; use `Decimal` (on the DB side `DECIMAL(18,2)`, in yuan)
- 🔴 Unit conversion **happens exactly once, at one boundary**, through a unified single entry point function; hand-written `/100` anywhere else in the chain is forbidden
- 🔴 Ratios are uniformly expressed as decimals (`0.1234` = 12.34%) and must not be mixed with percentages; the rounding mode (half-up / half-even) must be declared
- 🟡 Precision requirements for high-precision fields (unit price / mean / quantiles) are written into the contract document

## 7. Security and Redaction

- 🔴 PII (phone numbers / ID numbers / detailed addresses / bank cards) must be redacted or hashed in the outward-facing layer; plaintext is allowed only in the raw layer and with access control configured
- 🔴 Redaction implementations are centralized in `{shared}/mask.py`; hand-written regexes scattered around are forbidden
- 🔴 No leakage of sensitive context: code / logs / commits must not contain production data samples or credentials (see skill `secret-sprawl-audit`)

## 8. Testing

- 🔴 Amount conversion, deduplication/merging and boundary filtering logic **must have boundary cases** (empty set, duplicate keys, cross-boundary, over-limit)
- 🟡 `tests/` mirrors `src/`; small fixture samples go in `tests/fixtures/`
- 🟡 Tests isolate external services (DB / vector store) by injecting distinct resource names via env; a direct connection to production is forbidden

## 9. AI-Generated Code Audit Trail 🔴

```markdown
- Every file generated or modified by AI carries a header comment:
  # [AI-GENERATED] model=<model-name> date=<YYYY-MM-DD> reviewed_by=<human>
- The commit message contains the `[AI]` marker, easing audit tracing
- AI-generated migration/DDL scripts must be reviewed line by line by a human in the PR with a confirming comment
- AI-generated code must not be pushed directly to main; it must go through a feature branch + PR flow
```

## 10. Type-Specific Red Lines Are Not Repeated at the Stack Layer

**Project-type-specific** red lines such as data processing / agents all live in the type layer and are not restated at the stack layer (otherwise a `python x website` project would inherit data platform rules):

Type-specific red lines (data processing: write idempotency / partition pruning / table lifecycle / data quality; agents: output contract / tool boundaries / cost ceiling / evaluation) are assembled into this file along with the project type and are **not restated at the stack layer**.

## 11. Notebook Standards (`notebooks/`, if present)

> **What a notebook is**: a Jupyter interactive document (`.ipynb`). It interleaves code, execution output and prose, and is used for **exploration and analysis**. It is not part of the production chain: not source code, not imported, not invoked by scheduling.
> **Skip if not applicable**: a project without `notebooks/` (e.g. a pure service / site project) skips this section, and **there is no need to trim this file** (cross-shape content: if not applicable, skip it as a whole).

- 🔴 `notebooks/` is for exploration and analysis only; **referencing it from production code / scheduling / services is forbidden**
- 🔴 Plaintext credentials and plaintext PII output (including already-executed output cells) are forbidden inside notebooks
- 🟡 Clean outputs before committing; name them `EXP-{YYYYMMDD}-{topic}.ipynb`

## 12. Service Layer Standards (`serving/`, if present)

> **Skip if not applicable**: a project without a service layer (`serving/`) skips this section (cross-shape content: if not applicable to this project, skip it as a whole).

- 🟡 One unified API framework (under Python that is FastAPI); a unified response body `{code, message, data, timestamp}`; pagination `page` starts at 1 and `size` defaults to 20, returning `PageResult`(items/total/page/size)
- 🔴 Server-side queries must go through the single entry point and carry **filter / limit constraints**; **unbounded queries are forbidden** (full table scans, lists without a limit)
- 🔴 Authentication and role checks reuse the unified middleware; hand-written checks inside endpoints are forbidden

## 13. Comments, Docstrings and Layout (Python)

> **Criterion**: comments answer "**why**" -- intent, constraints, non-obvious trade-offs, pitfalls already hit; the code itself answers "what". Restating the implementation = noise.
> **Timing**: write them **as you go** while coding, not as a "fill it in later" task; when reworking existing code, change the comments **in the same diff**.

- 🔴 **Public interfaces must carry a docstring**: a module / class / public function includes ① a one-sentence responsibility ② non-obvious parameters and return values ③ exception semantics ④ idempotency and side effects. Private functions follow the "only write it when non-obvious" rule.
- 🔴 **Comments change together with the code**: in one change, comments and implementation change together; **a comment inconsistent with the implementation must not be left behind**. A stale comment is more dangerous than no comment -- it actively misleads the next person and the next agent.
- 🔴 **Comments must not contain things that expire**: change history ("changed to ..."), dates, version numbers, "temporary solution" promises -> these belong in `docs/changes/` / `CHANGELOG` / `KNOWN-ISSUE`; keep only **currently true** facts in the code.
- 🔴 **Commented-out code must not be committed**: just delete it (tracing relies on git); to explain "why it was deleted", write it into the change entry.
- 🔴 **No bare `TODO` / `FIXME`**: they must carry a traceable anchor or condition (`# TODO(#issue-123): ...` / `# FIXME: waiting for upstream 2.x fix`) -- an unanchored todo equals forgetting.
- 🟡 **Must write**: ① why it is written this way (workaround / platform differences / precision and rounding mode); ② non-obvious boundaries and the source of magic values; ③ agreements with external systems (protocol quirks, field units); ④ security assumptions (which inputs are sanitized and which are not).
- 🟡 **Do not write**: restating the code (`# i plus 1`), decorative banners / separator lines, informational modification records (`# modified on xx`).
- 🟡 **AI-generated code**: comments must not claim unverified facts ("tested", "thread-safe", "performance optimized") unless evidence is attached in the same change.

### 13.1 Blank Lines and Layout (written for the human reader)

> **Basis**: PEP 8 allows blank lines to mark logical sections inside a function. The Google style guide §3.5 is more explicit: **use single blank lines as you judge appropriate within functions or methods**. A single blank line between logical stages is **encouraged**, not noise.

- 🔴 **Two lines between functions**: two blank lines between top-level functions and top-level classes. `ruff format` adds whatever is missing and collapses anything beyond two down to two.
- 🔴 **One line between methods**: one blank line between methods inside a class. This is the formatter's **enforced** value, and writing two collapses back to one, so the rule follows the tool.
- 🔴 **No blank line after a `def` line**; one blank line between a class docstring and its first member.
- 🔴 **One line before a comment**: a comment on its own line gets one blank line above it, which separates it from the code above.
- 🔴 **One line after a docstring**: a docstring is followed by one blank line, for a single-line docstring as well as a multi-line one. The rule does not apply when the docstring is the only statement in its block.
- 🔴 **At most one blank line inside a function**: two or more consecutive blank lines collapse to one. No blank lines inside parentheses or literals, and no trailing spaces on a blank line (`W293`).
- 🟡 **Stages inside a function**: separate logical stages (validate / transform / write) with a **single** blank line, and do not insert blank lines inside one stage.
- 🟡 **Counter-check**: a stretch of code that needs two or more blank lines to stay readable is usually a signal to **split the function**. A blank line separates stages; it is not a way to hide a long function.
- **Exemptions**, all of them hard constraints rather than leniency: a comment that is the **first line of a block** gets no blank line above it, because the formatter deletes one right under `if:` / `for:` / `def:`; the same holds for a comment inside parentheses; also the first line of a file, and tool directives such as `#!`, an encoding line, the `[AI-GENERATED]` header, `# type:` and `# noqa`, which stay glued to what they annotate.
- **Who enforces what**: blank lines between functions and methods, consecutive blank lines, blank lines inside parentheses and trailing whitespace are handled mechanically by `ruff format` and `ruff check`, so review does not repeat them. The blank line **before a comment** and the one **after a docstring** are out of the formatter's reach. The pre-commit gate covers them, judging added lines only, so an old repository is never re-litigated.

## [Layer: data-processing]CODING-STANDARD — Coding Standard (Data-Processing Projects)

> **General discipline** (type annotations / no print / unified gate / no float for money / masking single entry point / AI generation markers) is in `../../python/CODING-STANDARD.md`; this document lists only the red lines **specific to this type**.

### 1. Writes and Idempotency 🔴 (the #1 red line for this type)

- Incremental dedup tables must use `MERGE INTO` or **partition-level overwrite**; 🔴 **bare append is forbidden** (a rerun duplicates)
- **Single writer** per table / per partition; concurrent production must be serialized through orchestration
- Partition overwrite mode (dynamic overwrite) is **set uniformly at the session single entry point**; ad-hoc toggling in scripts is forbidden
- Commit conflicts (optimistic concurrency conflicts) are caught and retried via `{shared}/retry.py`; 🔴 silently skipping is forbidden
- 🔴 Destructive operations (`DROP` / `DELETE` / snapshot expiry / orphan cleanup) must have an explicit human authorization record

```sql
-- ✅ Correct: incremental merge by business key
MERGE INTO dwd_trade_order_di AS t
USING staging.trade_order_inc AS s
  ON t.order_id = s.order_id AND t.ds = s.ds
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;
```
```python
# ✅ Correct: partition-level idempotent rewrite          # ❌ Wrong: append; a rerun duplicates
df.writeTo("dwd.trade.order_di").overwritePartitions()
```

### 2. Partitions and Queries 🔴

- 🔴 Large tables must be partitioned (hidden partitioning: `days(ts)`, `bucket(n, id)`); target per-partition data volume 1–50 GB; **exposing raw columns directly as partition fields is forbidden**
- 🔴 Queries on partitioned tables **must carry partition pruning** conditions; full table scans are forbidden
- 🔴 `collect()` / `toPandas()` / `toArrow()` pulling a large table in full to the driver is forbidden; sampling must carry a `limit` and a comment on its purpose
- 🟡 Production pipelines must not use `SELECT *`; external output must have an explicit column list
- 🟡 Join strategy (dimension-table broadcast threshold) is unified at the session single entry point; manually adding broadcast hints for large tables is forbidden
- 🟡 Prefer built-in functions; use Python UDFs only when necessary and comment the performance impact (pandas UDFs recommended)

### 3. Table Design and Lifecycle 🔴

- 🔴 There are no native unique constraints: the business key and the **deduplication method** (MERGE / row_number) must be written into the table contract and implemented in code
- 🔴 Every table must have a **snapshot retention period and compaction strategy** configured (wired into maintenance tasks); unlimited retention is forbidden
- 🟡 Table properties (target file size, etc.) are set uniformly in migrations; ad-hoc modification in scripts is forbidden
- 🟡 Soft delete and audit: the source layer keeps `is_deleted`; the detail layer provides a way to filter valid data; historical audit goes through snapshot time travel

### 4. Data Quality 🔴

- 🔴 After `dwd` / `dws` tables are written, quality validation must be wired in: **primary key uniqueness, non-null rate of key fields, period-over-period row count drift, partition freshness**
- Unified entry point `{shared}/quality.check_table(df, rules)`; 🔴 a failed check **blocks downstream tasks**
- 🟡 Thresholds and the rule list are written into the **table contract** (not hardcoded in code); changes go through a PR

```yaml
# Declared in the table contract, not hardcoded in code
quality_rules:
  primary_key_unique: [order_id, ds]
  not_null: [pay_amount, user_id]
  row_count: { drift_warn: 0.30, drift_fail: 0.50, min_rows: 1000 }
  freshness: { max_lag_minutes: 120 }
  enum_check: { status: [paid, shipped, delivered, cancelled] }
```

### 5. Monetary Amounts and Numerics (narrows the requirements of this type) 🔴

- 🔴 Money must not use `float`/`double`; on the DB side `DECIMAL(18,2)` (yuan), high-precision fields `DECIMAL(24,6)` and must be declared in the contract
- 🔴 The cents→yuan conversion is done **only once, at the boundary of the ingest layer** (via `{shared}/money.cents_to_yuan`); a hand-written `/100` anywhere else in the pipeline is forbidden
- 🔴 Aggregations operate directly on DECIMAL; converting to float mid-way is forbidden; ratios are uniformly expressed as decimals (`0.1234` = 12.34%) and must not be mixed with percentages
- 🔴 All DECIMAL fields must be **explicitly cast**; relying on automatic inference is forbidden; the rounding mode (half-up / half-even) is declared in the contract

### 6. Schema and Types 🔴

- 🔴 Read/write schemas are centralized in `models/`, with names aligned with the table contract
- 🔴 schema evolution **goes through migrations only**; implicitly changing the schema at write time (auto add column / merge schema) is forbidden
- 🟡 Time fields uniformly use `timestamp` (UTC) or a date partition `ds` string, declared in the contract
- 🟡 One value list (enum / status code / currency / unit) has **exactly one home**: the schema under `config/contract`, with code reading it from configuration. A second copy inside code drifts (observed in practice: the schema carried a regex while the code carried a set, and one was updated without the other)

### 7. Data Security 🔴

- 🔴 PII (phone number, ID document number, detailed address, bank card) must be **masked or hashed at the detail layer**; plaintext is allowed only in the ingest layer and with access control configured
- 🔴 Masking implementations are centralized in `{shared}/mask.py`; hand-written regexes scattered around are forbidden
- 🔴 External tables and data-service responses must not contain plaintext PII
- 🟡 Column-level permissions are declared uniformly in the catalog / permission system

### 8. Orchestration 🔴

- 🔴 Orchestration files only orchestrate (import pipeline functions, assemble dependencies and scheduling parameters); **writing transform logic is forbidden**
- 🔴 Task function signatures are uniformly `run(ds: str, ...)`; partitions are injected by the scheduler; **implicitly using the system's current time is forbidden** (otherwise reruns are not reproducible)
- 🟡 Task-level retries are configured in the orchestration layer; business-level retries go through `{shared}/retry.py`; retries presuppose idempotent writes
- 🟡 Every run outputs metrics via `{shared}/log`: `run_id`, table, partition list, rows read/written, elapsed time
