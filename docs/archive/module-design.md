# Functional Module Design (Interface Contracts and Responsibility Definitions)

> **Design principle**: Strict Separation of Concerns. Each module is responsible for one thing only and communicates via standardized DataFrame contracts. All configuration (paths, validation thresholds) is managed centrally by the configuration center (`common/config`); hardcoding is strictly prohibited.

## 1. Module Overview

| Module directory   | Script file        | Core responsibility                                                      | Exposed interface (function/class)                        |
| :---               | :---               | :---                                                                     | :---                                                      |
| `ingestion/`       | `reader.py`        | Read raw data (JSON/CSV/Parquet) + append `_raw_json` audit column; archive arriving records to Bronze | `read_input(file_path)`, `write_bronze(raw_df, bronze_base)` |
| `validation/`      | `schema_validator.py` | Strict data-contract validation (field existence, type, enum, pattern, min, future time) | class `SchemaValidator` → `validate(df) -> (valid_df, invalid_df)` |
| `transformation/`  | `cleaner.py`       | Cleaning: timestamp UTC standardization, currency normalization, amount numeric check | class `DataCleaner` → `standardize_timestamps(df)`, `normalize_currency(df)`, `check_amount(df)` |
| `transformation/`  | `deduplicator.py`  | Deduplicate by business key (`event_id`), keep the newest record        | class `Deduplicator` → `deduplicate(df)`                    |
| `curation/`        | `builder.py`       | Build Gold star schema (fact, dimensions, wide table)                   | class `GoldBuilder` → `build_fact_table(df)`, `build_dimensions(df)`, `build_wide_table(fact_df, dims)` |
| `common/`          | `config.py`        | Load YAML env configs / schema contract; env-var override               | `load_config(env)`, `load_schema()`                         |
| `common/`          | `logger.py`        | Structured JSON logging                                                  | `setup_logging(level, log_file)`, `get_logger(name)`        |
| `common/`          | `metrics.py`       | Run metrics collection and persistence                                   | class `MetricsCollector` → `increment/set/add_error/save`   |
| `pipeline/`        | `cli.py`           | CLI entry point, parse arguments, orchestrate the full pipeline flow    | `main()`                                                  |

---

## 2. Module Interface Contracts (Input/Output Definitions)

### 2.1 `ingestion/reader.py`
- **Description**: Auto-selects the read engine based on the file path suffix (`.json`, `.csv`, `.parquet`). After reading, each row must retain its original JSON string (stored in the `_raw_json` column) to enable fully auditable replay in the Bronze layer.
- **Input**: File path (string or Path object).
- **Output**: Pandas DataFrame containing the raw data and a `_raw_json` column.
- **Exception handling**: If the file suffix is unsupported or the file does not exist, a clear exception is raised, caught and logged by the CLI layer.

### 2.2 `validation/schema_validator.py`
- **Description**: Validates against the 8 required fields defined in `config/schema.yaml`. Uses **Strict Mode**:
  - Rejects all extra fields not defined in the contract (directly dropped).
  - Validates whether fields are missing, types are compatible (e.g. string, numeric), and formats are correct (e.g. UUID, ISO timestamp).
- **Input**: Raw DataFrame.
- **Output**: Returns a tuple of two DataFrames `(valid_df, invalid_df)`. `invalid_df` includes an `error_reason` column describing the specific violation.
- **Failure policy**: Invalid records are written to `errors/bad_schema/` and **do not block** the processing of valid data.

### 2.3 `transformation/cleaner.py`
- **Description**:
  - **Timestamp standardization**: Force-convert `event_timestamp` and `ingestion_timestamp` to UTC datetimes. The validator has already backed up the raw string into `_raw_<col>`; the cleaner only fills the backup if it is absent.
  - **Currency normalization**: Upper-case the `currency` field; codes outside the demo whitelist `{USD, EUR, GBP, CNY, JPY}` are corrected to `USD` and flagged via the `_is_invalid_currency` boolean column (the whitelist is a demo subset of ISO-4217).
  - **Numeric check**: Coerce `amount` to numeric. Negative and non-numeric values are already quarantined by the validator (`minimum` / `not numeric` rules) before this stage.
- **Input**: Validated DataFrame.
- **Output**: Cleaned DataFrame with additional flag columns (e.g. `_is_invalid_currency`).

### 2.4 `transformation/deduplicator.py`
- **Description**: Deduplicates by `event_id`. When duplicate IDs appear, the record with the **latest** `ingestion_timestamp` is retained. On an exact tie (identical `ingestion_timestamp`) the **last-occurring row** in the input file wins (keep-last; the sort is stable); no extra tiebreaker is defined.
- **Input**: Cleaned DataFrame.
- **Output**: A pair `(deduplicated_df, duplicates_df)` — the deduplicated rows
  and the superseded duplicates for audit logging. The module itself performs
  no I/O; cli.py (see §2.7) writes the duplicates to
  `data/errors/duplicates.log`.

### 2.5 `curation/builder.py` (Gold Layer Construction)
- **Description**: Aggregates Silver-layer detail data into analysis-oriented data products.
  - **Fact table**: Groups by `event_date`, `customer_id`, `event_type` and computes `event_count`, `total_amount`, `avg_amount`.
  - **Dimension tables**: Extracts `dim_customer` (only `customer_id`, extensible in the future) and `dim_event_type` (only `event_type`) from the Silver layer.
  - **Wide table**: Left-joins the fact table with dimension tables to produce a single denormalized wide table for direct BI queries.
- **Input**: Silver-layer DataFrame.
- **Output**: Three independent DataFrames (`fact_df`, `dims_dict`, `wide_df`).

### 2.6 `common/config.py`
- **Description**: Reads `config/{env}.yaml` and parses the YAML content into a Python dict. Supports overriding sensitive configuration (e.g. storage path prefix) via environment variables.
- **Input**: Environment identifier (`dev`, `test`, `prod`).
- **Output**: Configuration dict (containing input/output paths, validation thresholds, alert webhook URL, etc.).

### 2.7 Pipeline Entry `cli.py`
- **Description**: Parses CLI arguments (`--env`, `--input`, optional `--event-date`), calls each module in sequence, forming the complete ETL.
- **Execution order (DAG)**:
  1. Load configuration.
  2. Call `ingestion.read_input` to read the batch.
  2b. Call `ingestion.write_bronze` to archive the full arriving batch (Bronze landing zone).
  2c. If `--event-date` is given, scope processing to rows whose `event_timestamp` falls on that date (safe backfill).
  3. Call `SchemaValidator.validate` to split valid/invalid data (invalid → `errors/bad_schema/`).
  4. Call `DataCleaner` and `Deduplicator` to process valid data; cli.py
     writes the deduplicator's superseded rows to `data/errors/duplicates.log`.
  5. Write to Silver layer (partitioned by `event_date`, Parquet format; `_processed_timestamp` added at write time).
  6. Call `GoldBuilder` to generate Gold-layer data and write to the corresponding directory.
  7. Save `metrics.json` (row counts; path = `metrics.output_file` config,
     resolved under the env's `storage.base_path`).
- **Idempotency guarantee**: Bronze/Silver/Gold writes use "overwrite specific partition" mode, ensuring that re-running the same date does not produce duplicate data (a production Bronze would append instead).

---

## 3. Configuration and Contract Management (Non-code)

### 3.1 Configuration File Structure (YAML Template)
- `config/dev.yaml`, `config/test.yaml`, `config/prod.yaml`.
- **Core config items**:
  - `storage.base_path`: Data storage root directory (local or S3).
  - `validation.schema_path`: Path to `schema.yaml`.
  - `logging.level`: Log level (INFO/DEBUG).
  - `alert.slack_webhook`: Alert callback URL — **reserved, not yet wired to any alert consumer** (all envs ship it empty).

### 3.2 Data Contract (Schema Registry)
- `config/schema.yaml` explicitly defines fields, types, required flags, enum value whitelists, and regex patterns.
- For future extensions, modifying this YAML takes effect without changing core Python logic.

---

## 4. Cross-module Communication Specification
- **Data carrier**: All modules pass data via **Pandas DataFrame**.
- **Metadata passing**: DataFrame `attrs` is a documented option for lightweight metadata (processing timestamp, source filename); the current implementation does not rely on it.
- **Error passing**: Validation or cleaning modules do not raise exceptions to interrupt the flow; instead, they pass problem data downstream or to the quarantine area via the returned `invalid_df` or flag columns (e.g. `_validation_status`).

## 5. Test Extension Point Design
- All module interfaces use DataFrame as input/output, not depending on specific file paths, making unit testing (`pytest`) straightforward.
- `tests/test_validation.py` covers the contract edge cases (happy path, missing required field, future timestamp, non-numeric amount, extra field, non-v4 UUID).
