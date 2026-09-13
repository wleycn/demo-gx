# ACCEPTANCE-CHECKLIST — Acceptance checklist (baseline)

> **This file contains no type markers**: assembly = baseline + stack + type **concatenated directly**, with no manual trimming needed. If a marker such as `[data-type]` appears in a project, the assembly is wrong (machine review will report it), and **it must not be deleted by hand in the project**.

## I. CR Checklist (before the merge request)

- [ ] No 🔴 red line violations (the red lines for this stack / this project are in `CODING-STANDARD.md`)
- [ ] Contract / interface documents updated in sync (API contract + the corresponding documents under `docs/business/`; for data types see also the table contract)
- [ ] Unit tests cover the new logic, **including boundaries** (numeric precision, dedup keys, null values, over-limit)
- [ ] Migration script numbering is correct and the `dry-run` passes
- [ ] Logging and runtime metrics are complete (key object identifiers, processed counts, elapsed time)
- [ ] **AI-generated code is marked** (file header + commit message)
- [ ] No prompt injection risk: the generated code does not execute external data as instructions
- [ ] No sensitive context leakage: no production data samples, log fragments or credentials in the code
- [ ] Destructive operations (DROP / DELETE / bulk overwrite) have a recorded explicit human authorization
- [ ] Agent behavior compliant: **no "incidental improvements" to adjacent code** (one task touches only the authorized scope)
- [ ] Line-ending and blank-line hygiene: line endings match the repository declaration, with no extra blank lines (such as a double-CR `\r\r\n`)

## II. Production Readiness Checklist (before going live)

### Reliability
- [ ] Failure notification is configured (email / webhook / event hook)
- [ ] Retry policy is defined, **and assumes idempotent writes**

### Observability
- [ ] Every run outputs: run identifier / target object / processed count / elapsed time
- [ ] Key metrics are wired into monitoring
- [ ] Log fields are structured and indexable by the logging system

### Deployment and rollback
- [ ] Migration `dry-run` passes
- [ ] Rollback script has been verified (it is not "written, therefore done")
- [ ] Shadow run / canary acceptance passed
- [ ] Change record written to `docs/changes/{module}.md` (entry includes verification and rollback)

### Security
- [ ] No hardcoded credentials / endpoints / paths
- [ ] PII fields masked per the contract
- [ ] AI-generated code is marked

## [Layer: data-processing]ACCEPTANCE-CHECKLIST — Acceptance Checklist (data-processing specific)

### 1. CR Checklist Additions (before the merge request)

- [ ] Quality rules are wired in and configured for **failure blocking** (not just alerting)

### 2. Production Readiness Additions (before go-live)

#### Data Quality
- [ ] Every output dataset has at least 1 **fail-fast** quality rule
- [ ] warn / drop / fail thresholds are graded by business impact, not set uniformly
- [ ] Thresholds are written into the table contract document; changes go through a PR

#### Reliability and Scheduling
- [ ] Scheduling has **catchup disabled** (unless a backfill is explicitly declared)
- [ ] For stateful flows the **checkpoint recovery procedure is documented and tested**
- [ ] Table contract state machine: when `status != approved` the corresponding migration is blocked from merging into `main`

#### Observability (narrows the baseline requirement)

- [ ] Every run's output includes the **partition list** and rows read/written (the baseline only requires the processed count)
