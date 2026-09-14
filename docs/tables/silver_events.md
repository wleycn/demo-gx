# Table Contract: silver_events

## Layer

Silver (cleaned detail)

## Subject

Events. One row per deduplicated event, unified across every source system.

## Grain

One row per unique event (after deduplication by `event_id`).

## Business Primary Key

`event_id` (UUID v4)

## Deduplication

By `event_id`, keeping the record with the latest `ingestion_timestamp`. On an exact
tie (identical `ingestion_timestamp`), the last-occurring row in the input file wins
(keep-last; stable sort). Superseded duplicates are written to `errors/duplicates.log`
for post-hoc review.

## Partition

`event_date` (date, derived from `event_timestamp`). Partition directory format:
`event_date={YYYY-MM-DD}/data.parquet`.

- **Rationale**: every downstream read filters or groups by date. A date partition lets one run rewrite a single day without touching the others.
- **Estimated volume**: 1 to 7 rows per partition in the demo sample. The sample holds 101 rows across 30 partitions, about 11 KB per partition.

## Field List

| Field | Type | Description | Constraint |
|---|---|---|---|
| `event_id` | string | Unique event ID | Non-null, UUID v4 format |
| `source_system` | string | Source system | Enum: `web`, `mobile`, `api` |
| `customer_id` | string | Customer ID | Non-null; may be hash-masked by policy in production |
| `event_type` | string | Event type | Non-null, length at most 64 |
| `event_timestamp` | timestamp (us, UTC) | Event occurrence time | Microsecond precision, UTC timezone |
| `amount` | double | Amount | At least 0, original value preserved; `NaN` if conversion fails |
| `currency` | string | Currency code | ISO 4217 three-letter code; invalid values corrected to `USD` |
| `ingestion_timestamp` | timestamp (us, UTC) | Ingestion time from source system | Must be at most current time |
| `_raw_json` | string | Full original record as JSON | Added by `reader.read_input`; for row-level replay |
| `_raw_event_timestamp` | string | Original raw `event_timestamp` string | Backed up by the validator before parse; never overwritten |
| `_raw_ingestion_timestamp` | string | Original raw `ingestion_timestamp` string | Backed up by the validator before parse; never overwritten |
| `_is_invalid_currency` | boolean | Whether currency was corrected | `true` means original value was invalid, changed to `USD` |
| `_raw_amount` | double | Backup of amount after validator's numeric coercion | Written by the cleaner on every row |
| `event_date` | date | Partition column | Derived from `event_timestamp` |
| `_processed_timestamp` | timestamp (us, UTC) | Pipeline processing time | Added at write time |

## Monetary Convention

- **Unit**: `amount` holds a decimal in the currency's major unit, not its minor unit. `12.34` with `currency=USD` means 12.34 US dollars.
- **Precision**: two decimal places at most. The validator quarantines finer values.
- **Accepted codes**: five. `USD`, `EUR`, `GBP`, `CNY`, and `JPY`. Any other value is replaced with `USD` and flagged in `_is_invalid_currency`.
- **No conversion**: amounts are never converted between currencies. The pipeline has no exchange rate.
- **Aggregation caveat**: `amount` carries no currency dimension, so a sum across rows mixes currencies. The Gold aggregates inherit this caveat.

## PII and Masking

- **Direct identifiers**: `customer_id` is the only one. `event_id` is a surrogate key and carries no personal data.
- **Masking today**: `customer_id` is replaced by a keyed digest at the ingestion boundary. The masked form is `h_` plus 16 hex characters.
- **Raw copy**: `_raw_json` holds the masked value, because the mask runs before that column is built. Bronze, Silver, Gold and the quarantine envelopes all carry the masked form.
- **Why a digest and not a redaction**: Gold groups events by `customer_id` and `dim_customer` holds one row per distinct value. A redaction such as `cust_***` would collapse every customer into a single bucket and change the Gold row counts.
- **Production note**: the demo config leaves `pii.pepper` empty, so the digest is reproducible from the input alone. A real deployment injects the key from the secret store.

## Lifecycle

- **Write mode**: partition-scoped overwrite (idempotent). Each partition's `data.parquet`
  is rewritten per run.
- **Empty partitions**: not pruned. A full clean re-run (`make clean`) removes all artifacts.
- **Retention**: no retention policy. All partitions persist until manually cleaned.
- **Reprocessing**: `--event-date` reprocesses one date. Late data writes to the
  corresponding historical partition.
- **Compaction and snapshot retention**: not implemented. See KNOWN-ISSUE.md `#no-snapshot-lifecycle`.

## Freshness SLA and Owner

- **Freshness SLA**: none. The demo runs on demand, with no schedule and no alert wired.
- **Owner**: the repository maintainers.
- **Production rule**: SLA and alerting belong in the orchestration layer. See DATA-DESIGN.md section 3.

## Dependencies

- **Upstream**: the environment's inbound file, read by `ingestion.read_input`. It accepts `.json` lines, `.csv`, and `.parquet`.
- **Downstream**: `fact_daily_events`, `dim_customer`, `dim_event_type`, and `wide_daily_user_events`. Each reads the full on-disk Silver snapshot.

## Quality Rules

1. All eight declared fields must be present and non-null. A missing or null field quarantines the row.
2. A record carrying an undeclared key is quarantined. Strict mode judges this from `_raw_json`, so a null extra value still counts as present.
3. `event_id` must match the UUID v4 pattern.
4. `source_system` must be one of `web`, `mobile`, or `api`.
5. `event_type` must be at most 64 characters.
6. `amount` must be numeric, at least 0, finite, and at most two decimal places.
7. `currency` must match three upper-case letters.
8. Both timestamps must parse and must not be later than the run instant.
9. `event_id` is unique after deduplication.
10. A quarantined row never reaches this table. Validation failure sends it to `errors/bad_schema/`.
