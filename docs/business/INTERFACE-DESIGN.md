# Interface Design

This document is the single source of truth for the CLI interface, input formats, output path shapes, error envelope fields, and metrics fields.

## 1. CLI Parameter Contract

Entry point: `demo_gx.cli`, run as `python -m demo_gx.cli`

| Parameter | Required | Default | Choices | Description |
|---|---|---|---|---|
| `--input` | No | `<env root>/input/sample_data.json` | file path | Path to the input file (JSON, CSV, or Parquet). When omitted it resolves to `storage.input_root` joined with `storage.input_file` |
| `--env` | No | `dev` | `dev`, `test`, `prod` | Environment configuration to load |
| `--event-date` | No | none | `YYYY-MM-DD` | Scope processing to one event date (safe backfill) |
| `--run-timestamp` | No | wall clock at the entry boundary | ISO-8601 | Run instant injected by the orchestrator. Stamps `_processed_timestamp` and the error envelope. Passing it makes a run byte-reproducible. |

Example:

```bash
python -m demo_gx.cli --env dev
python -m demo_gx.cli --env test --event-date 2026-09-09
python -m demo_gx.cli --env test --run-timestamp 2026-09-14T01:00:00Z
python -m demo_gx.cli --env dev --input /tmp/other.json
```

The CLI anchors all relative paths (storage, logs, metrics, input) to the project root, so it behaves identically regardless of the caller's working directory.

The run timestamp is read exactly once, at this entry boundary, and then threaded down as a parameter. Modules never read the system clock for data stamping, which is what makes the injected value authoritative.

## 2. Input Format

The reader auto-detects format by file extension:

| Extension | Read method | Notes |
|---|---|---|
| `.json` | `pd.read_json(path, lines=True)` | JSON Lines: one event object per line |
| `.csv` | `pd.read_csv(path)` | Standard CSV |
| `.parquet` | `pd.read_parquet(path)` | Parquet columnar |

After reading, a `_raw_json` column is appended to every row containing the row's original JSON string. This enables audit and replay in the Bronze layer.

### Expected Input Fields

Defined in `config/schema.yaml`. All 8 fields are required.

| Field | Type | Validation |
|---|---|---|
| `event_id` | string | UUID v4 regex pattern |
| `source_system` | string | Enum: `web`, `mobile`, `api` |
| `customer_id` | string | Non-null |
| `event_type` | string | Non-null, max length 64 |
| `event_timestamp` | timestamp | Parseable as UTC, not in the future |
| `amount` | number | Minimum 0, max 2 decimal places |
| `currency` | string | Three-letter code regex `^[A-Z]{3}$` |
| `ingestion_timestamp` | timestamp | Parseable as UTC, not in the future |

Strict mode rejects unknown fields not in this list.

## 3. Output Path Shapes

### 3.1 Environment Storage Roots

| Environment | `storage.base_path` | Config file |
|---|---|---|
| dev | `./data/dev` | `config/dev.yaml` |
| test | `./data/test` | `config/test.yaml` |
| prod | `./data/prod` | `config/prod.yaml` |

Each environment root splits by direction:

```text
{storage.base_path}/
├── input/          # inbound drop location; where --input defaults to
└── output/         # everything the pipeline writes
```

Every path shape below is relative to `output/`, written `{output_root}`.

### 3.2 Bronze

```text
{output_root}/bronze/{source_system}/dt={YYYY-MM-DD}/events.json
```

JSON Lines format. One file per `source_system` plus `dt` partition combination. Partition-scoped overwrite (idempotent).

### 3.3 Silver

```text
{output_root}/silver/event_date={YYYY-MM-DD}/data.parquet
```

Parquet format. One file per `event_date` partition. Partition-scoped overwrite (idempotent).

### 3.4 Gold

```text
{output_root}/gold/
├── fact_daily_events/event_date={YYYY-MM-DD}/data.parquet
├── dim_customer/data.parquet
├── dim_event_type/data.parquet
└── wide_daily_user_events/event_date={YYYY-MM-DD}/data.parquet
```

Fact and wide tables are partitioned by `event_date`. Dimension tables are full snapshots (non-partitioned). All Gold outputs are Parquet.

### 3.5 Errors

```text
{output_root}/errors/
├── bad_schema/{timestamp}_errors.json    # JSON Lines
└── duplicates.log                        # Plain text, appended
```

There is no separate type-conversion quarantine directory. Every rejected row goes into the single `bad_schema/` envelope, including rows whose type conversion failed: they are filed with `error_type=type_coercion_failed`.

### 3.6 Metrics and Logs

```text
{output_root}/metrics.json
{output_root}/logs/pipeline.log
```

## 4. Error Envelope Fields

Invalid records are written to `errors/bad_schema/{timestamp}_errors.json` in JSON Lines format. Each line is one error object.

| Field | Type | Description |
|---|---|---|
| `original_json` | string | JSON rebuild of the offending row. Pandas round-trip: keys missing from the raw line render as `null`. |
| `error_type` | string | `schema_mismatch` or `type_coercion_failed`. Derived from the validator's per-rule error reason. |
| `error_details` | string | Specific reason text from the validator (e.g. "field 'event_id' missing", "amount not numeric"). |
| `ingestion_timestamp` | string (ISO-8601) | The UTC time the pipeline processed this record. |

### Error Type Classification

`validation/error_envelope.py` classifies each error reason into one of two types:

- `type_coercion_failed`: the reason text contains "not numeric", "not string", or "parse failed".
- `schema_mismatch`: all other reasons (missing field, pattern mismatch, enum violation, extra fields, future timestamp, below minimum, exceeds max length, exceeds max decimals, not finite).

## 5. Metrics Fields

Written to `{output_root}/metrics.json` at the end of each run. Metrics are always persisted, even on failure.

| Field | Type | Description |
|---|---|---|
| `start_time` | string (ISO-8601) | UTC timestamp when the run started |
| `end_time` | string (ISO-8601) | UTC timestamp when metrics were saved |
| `input_rows` | integer | Total rows read from the input file |
| `bronze_rows` | integer | Rows archived to Bronze |
| `valid_rows` | integer | Rows that passed schema validation |
| `invalid_rows` | integer | Rows that failed schema validation |
| `duplicates_removed` | integer | Superseded duplicate rows removed by the deduplicator |
| `silver_rows` | integer | Rows written to Silver (after deduplication) |
| `gold_rows` | integer | Rows in the Gold fact table |
| `errors` | array of strings | Error messages from unhandled exceptions (empty on success) |

Per-stage durations are not yet collected.
