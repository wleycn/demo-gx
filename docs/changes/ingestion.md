# ingestion changes (`src/demo_gx/ingestion/`)

> Format and discipline: see `docs/rules/DEVELOP-FLOW.md` section 4. Append-only; never rewrite past entries.

(no entries yet: this directory records changes from its establishment onward; for prior history see `git log`)

## 20260914 · inject-run-timestamp — Bronze partition fallback no longer reads the clock

- **Motivation**: part of the `#now-timestamp` migration. Full entry lives in `docs/changes/engineering.md`.
- **Scope**: `pipeline/ingestion/reader.py` only — `write_bronze` takes `run_ts` and uses it as the partition-date fallback for rows with no parseable `ingestion_timestamp`.
- **Behaviour and contract changes**: `write_bronze` gains a required third parameter. Partition layout and the fallback value are unchanged; only its source moved from the wall clock to the injected run instant.
- **Verification**: see the full entry in `docs/changes/engineering.md`.
- **Rollback**: revert the commit.
- **Related**: `docs/changes/engineering.md` (same date) / `KNOWN-ISSUE.md#now-timestamp`.

## 20260914 · english-doc-assets — Pointer

- The change-entry field labels in this file were translated to English as part of the repository-wide language migration. The full entry lives in `docs/changes/engineering.md`.

## 20260914 · pii-masking-at-ingestion — Mask direct identifiers as records enter the pipeline

- **Motivation**: red line 4 of `AGENTS.md` requires PII to be masked at the detail layer, and both table contracts stated the rule as "mask at the Bronze entry boundary". Nothing implemented it: `customer_id` was stored in clear text in Bronze, in Silver, in `_raw_json`, in the quarantine envelopes and in the logs. `docs/business/PROJECT.md` compounded the problem by claiming the mask ran at the Silver layer, which the table contracts contradict.
- **Scope**: new `src/demo_gx/common/mask.py`; `src/demo_gx/ingestion/reader.py`, which now masks before the audit copy is built; `src/demo_gx/cli.py`, which reads the policy from config and passes it in; `config/dev.yaml`, `config/test.yaml` and `config/prod.yaml`, which gain a `pii` block; new `tests/test_mask.py`; and the PII statements in `docs/tables/silver_events.md`, `docs/tables/dim_customer.md`, `docs/business/PROJECT.md`, `docs/business/DATA-DESIGN.md` and `docs/business/MODULE-DESIGN.md`.
- **The mask**: `h_` plus 16 hex characters of HMAC-SHA256 over the value, keyed by `pii.pepper`. The digest is deterministic and injective on purpose. Gold groups events by `customer_id` and `dim_customer` holds one row per distinct value, so a redaction such as `cust_***` would collapse every customer into a single bucket and change the Gold row counts.
- **Where it runs**: at the ingestion boundary, before `_raw_json` is built. Every artefact below ingestion therefore holds the masked form. That is why the table contracts asked for the boundary and not the Silver gate: masking at Silver would leave the clear value inside `_raw_json`, which is the copy kept for replay.
- **Configuration**: `pii.masked_fields` lists the columns and `pii.pepper` keys the digest. All three environments mask, and all three leave the pepper empty. The shape matches the existing `alert.slack_webhook` placeholder, so no secret value is committed and a real deployment injects the key from the secret store.
- **Behaviour and contract changes**: `read_input` gains two keyword parameters, and the masked value replaces the clear value in every artefact. The Gold shape is unchanged. The parquet file count, the per-partition row counts and the metrics totals are identical to the pre-mask run, and `dim_customer` still holds 44 distinct customers.
- **Verification**: `pytest` reports 35 passed, up from 27. `ruff check`, `ruff format --check` and `mypy` are clean. The pipeline was run end to end, and a search for the clear-text prefix over the whole output tree returns no file. A row-by-row comparison against the pre-mask run shows every Silver and Gold partition identical in size, and `metrics.json` identical once the volatile run fields are dropped.
- **Known limits**: the configured column names are not checked against `config/schema.yaml`, so a typo would leave that column unmasked. `dim_customer` still lists the masked identifiers, so the table stays sensitive. A digest is pseudonymisation and not anonymisation.
- **Rollback**: revert the commit. The masked artefacts are rebuildable from the input batch.
- **Related**: `CHANGELOG.md` entry for this date / `docs/tables/silver_events.md` section "PII and Masking" / red line 4 of `AGENTS.md`.
