# Module Design

## 1. Module Overview

Each module is responsible for one thing only and communicates via standardized DataFrame contracts. All configuration (paths, validation thresholds) is managed centrally by `common/config`. Hardcoding is prohibited.

| Module directory | Script file | Core responsibility | Exposed interface |
|---|---|---|---|
| `ingestion/` | `reader.py` | Read raw data (JSON/CSV/Parquet) and append `_raw_json` audit column; archive arriving records to Bronze | `read_input(file_path)`, `write_bronze(raw_df, bronze_base)` |
| `validation/` | `schema_validator.py` | Strict data-contract validation (field existence, type, enum, pattern, minimum, future time) | `class SchemaValidator` with `validate(df) -> (valid_df, invalid_df)` |
| `transformation/` | `cleaner.py` | Timestamp UTC standardization, currency normalization, amount numeric check | `class DataCleaner` with `standardize_timestamps(df)`, `normalize_currency(df)`, `check_amount(df)` |
| `transformation/` | `deduplicator.py` | Deduplicate by business key (`event_id`), keep the newest record | `class Deduplicator` with `deduplicate(df)` |
| `curation/` | `builder.py` | Build Gold star schema (fact, dimensions, wide table) | `class GoldBuilder` with `build_fact_table(df)`, `build_dimensions(df)`, `build_wide_table(fact_df, dims)` |
| `common/` | `config.py` | Load YAML env configs and schema contract; env-var override | `load_config(env)`, `load_schema()` |
| `common/` | `logger.py` | Structured JSON logging | `setup_logging(level, log_file)`, `get_logger(name)` |
| `common/` | `metrics.py` | Run metrics collection and persistence | `class MetricsCollector` |
| `common/` | `time_utils.py` | Shared timestamp parsing policy | `parse_utc_mixed(series)` |
| `pipeline/` | `cli.py` | CLI entry point: parse arguments, orchestrate the full pipeline | `main()` |

## 2. Module Interface Contracts

### 2.1 ingestion/reader.py

**Description**: Auto-selects the read engine based on the file path suffix (`.json`, `.csv`, `.parquet`). After reading, each row retains its original JSON string in the `_raw_json` column for audit and replay.
**Input**: file path (string or Path object).
**Output**: Pandas DataFrame containing the raw data and a `_raw_json` column.
**Exception handling**: a missing file or an unsupported suffix raises immediately (fail fast, never a silent skip). The CLI logs the error and exits non-zero. Retry is the orchestration layer's responsibility, not the CLI's.
**`write_bronze`**: archives every raw record to Bronze, partitioned by `source_system` and ingestion date. The `_raw_json` column is excluded from the archive. Missing `source_system` falls back to `unknown`; missing `ingestion_timestamp` falls back to the run date. Returns the count of records written.

### 2.2 validation/schema_validator.py

**Description**: validates against the 8 required fields defined in `config/schema.yaml`. Uses strict mode:

- Rejects all extra fields not defined in the contract. Row-level key presence is judged from the preserved `_raw_json` when available, because a null extra value and a missing key are indistinguishable after `pandas.read_json`.
- Validates whether fields are missing, types are compatible, and formats are correct (UUID, ISO timestamp, enum, regex, minimum, max length, max decimals).

**Input**: raw DataFrame.
**Output**: tuple of two DataFrames `(valid_df, invalid_df)`. `invalid_df` includes an `error_reason` column describing each violation.
**Failure policy**: invalid records are written to `errors/bad_schema/` and do not block the processing of valid data.

### 2.3 transformation/cleaner.py

**Description**:

- **Timestamp standardization**: force-convert `event_timestamp` and `ingestion_timestamp` to UTC datetimes. The validator has already backed up the raw string into `_raw_<col>`; the cleaner only fills the backup if it is absent.
- **Currency normalization**: upper-case the `currency` field. Codes outside the demo whitelist `{USD, EUR, GBP, CNY, JPY}` are corrected to `USD` and flagged via the `_is_invalid_currency` boolean column.
- **Numeric check**: coerce `amount` to numeric and back up the pre-cleaner value to `_raw_amount`. Negative and non-numeric values are already quarantined by the validator before this stage.

**Input**: validated DataFrame.
**Output**: cleaned DataFrame with additional flag columns.

### 2.4 transformation/deduplicator.py

**Description**: deduplicates by `event_id`, keeping the record with the latest `ingestion_timestamp`. The tie-break rule is a data invariant; see DATA-DESIGN.md section 1.
**Input**: cleaned DataFrame.
**Output**: pair `(deduplicated_df, duplicates_df)`. The module performs no I/O. The CLI writes superseded duplicates to `errors/duplicates.log`.

### 2.5 curation/builder.py

**Description**: aggregates Silver-layer detail data into analysis-oriented data products.

- **Fact table**: groups by `event_date`, `customer_id`, `event_type` and computes `event_count`, `total_amount`, `avg_amount`.
- **Dimension tables**: extracts `dim_customer` (unique customer IDs with `first_seen_date`) and `dim_event_type` (unique event types) from the Silver layer.
- **Wide table**: left-joins the fact table with dimension tables to produce a single denormalized wide table for direct BI queries.

**Input**: Silver-layer DataFrame. The CLI passes the full on-disk Silver snapshot (see DATA-DESIGN.md section 2.4), never the in-memory batch.
**Output**: three independent DataFrames (`fact_df`, `dims_dict`, `wide_df`).

### 2.6 common/config.py

**Description**: reads `config/{env}.yaml` and parses the YAML content into a Python dict. Supports overriding the storage base path via the `STORAGE_BASE_PATH` environment variable. Anchors relative paths for metrics and log files under the environment's storage base path.
**Input**: environment identifier (`dev`, `test`, `prod`).
**Output**: configuration dict containing storage paths, logging settings, metrics output location, and alert endpoints.

### 2.7 common/time_utils.py

**Description**: shared timestamp parsing policy. Uses `pd.to_datetime` with `format="mixed"` and `utc=True` to parse each element in its own format (mixed timezones and precisions). Unparseable values become NaT. This function never raises.
This policy lives in one place so the validator, cleaner, CLI, and Bronze writer cannot drift apart.

### 2.8 common/metrics.py

**Description**: lightweight collector that tracks input row counts, validation pass and fail counts, deduplication stats, Gold-layer row counts, and a list of error messages. Results are saved as a JSON file for monitoring.

### 2.9 Pipeline Entry cli.py

**Description**: parses CLI arguments (`--env`, `--input`, optional `--event-date`), calls each module in sequence.
**Execution order**:

1. Load configuration and set up logging.
2. Call `ingestion.read_input` to read the batch.
3. Call `ingestion.write_bronze` to archive the full arriving batch.
4. If `--event-date` is given, scope processing to rows whose `event_timestamp` falls on that date.
5. Call `SchemaValidator.validate` to split valid and invalid data. Invalid records are written to `errors/bad_schema/` with an error envelope.
6. Call `DataCleaner` and `Deduplicator` to process valid data. Superseded duplicates are written to `errors/duplicates.log`.
7. Write to Silver layer (partitioned by `event_date`, Parquet format). Add `_processed_timestamp` at write time.
8. Call `GoldBuilder` to generate Gold-layer data from the full on-disk Silver snapshot (see DATA-DESIGN.md section 2.4).
9. Save `metrics.json`.

**Idempotency**: Bronze, Silver, and Gold writes use partition-scoped overwrite mode. Re-running the same date does not produce duplicate data.

## 3. Configuration Management

### 3.1 Configuration Files

- `config/dev.yaml`, `config/test.yaml`, `config/prod.yaml`.
- Core config items:
  - `storage.base_path`: data storage root directory. INTERFACE-DESIGN.md section 3.1 lists the root for each environment.
  - `storage.bronze_subpath` / `silver_subpath` / `gold_subpath` / `errors_subpath`: subdirectory names under the base path.
  - `logging.level`: log level (INFO/DEBUG).
  - `logging.file`: log file path, anchored under the storage base path.
  - `metrics.output_file`: metrics JSON path, anchored under the storage base path.
  - `alert.slack_webhook`: alert callback URL. Reserved but not wired. All environments ship it empty.

### 3.2 Data Contract

- `config/schema.yaml` explicitly defines fields, types, required flags, enum value whitelists, regex patterns, minimum values, max length, and max decimals.
- Modifying this YAML takes effect without changing core Python logic.

## 4. Cross-Module Communication

- **Data carrier**: all modules pass data via Pandas DataFrame.
- **Metadata passing**: DataFrame `attrs` is a documented option for lightweight metadata such as the processing timestamp or the source filename. The current implementation does not rely on it: that metadata travels in explicit columns, for example `_processed_timestamp`.
- **Error passing**: validation and cleaning modules do not raise exceptions to interrupt the flow. They pass problem data downstream or to the quarantine area via the returned `invalid_df` or flag columns.
- **No global state**: modules do not share global variables. All configuration flows through `common/config`.

## 5. Test Extension Points

- All module interfaces use DataFrame as input and output, not depending on specific file paths. This makes unit testing straightforward.
- `tests/` covers contract edge cases: happy path, missing required field, future timestamp, non-numeric amount, extra field, non-v4 UUID, deduplication tie, currency normalization, backfill regression.
