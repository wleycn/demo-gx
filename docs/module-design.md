# Functional Module Design (Interface Contracts and Responsibility Definitions)

> **Design principle**: Strict Separation of Concerns. Each module is responsible for one thing only and communicates via standardized DataFrame contracts. All configuration (paths, validation thresholds) is managed centrally by the configuration center (`common/config`); hardcoding is strictly prohibited.

## 1. Module Overview

| Module directory   | Script file        | Core responsibility                                                      | Exposed interface (function/class)                        |
| :---               | :---               | :---                                                                     | :---                                                      |
| `ingestion/`       | `reader.py`        | Adapt to different file formats (JSON/CSV/Parquet), read raw data and append lineage columns | `read_input(file_path)`                                   |
| `validation/`      | `schema_validator.py` | Execute strict data contract validation (field existence, type, enum, format) | `validate_schema(df)`                                     |
| `transformation/`  | `cleaner.py`       | Data cleaning (timestamp standardization, currency normalization, anomaly flagging) | `standardize_timestamps(df)`, `normalize_currency(df)`    |
| `transformation/`  | `deduplicator.py`  | Deduplicate by business key (`event_id`), keep the newest record        | `deduplicate(df)`                                         |
| `curation/`        | `builder.py`       | Build Gold-layer star schema (fact table, dimension tables, wide table) | `build_fact_table(df)`, `build_dimensions(df)`, `build_wide_table(df)` |
| `common/`          | `config.py`        | Load YAML config files, inject environment variables                    | `load_config(env)`                                        |
| `common/`          | `logger.py`        | Provide structured logging (JSON format) and audit metric collection    | `get_logger()`, `collect_metrics()`                       |
| `cli/`             | `cli.py`           | CLI entry point, parse arguments, orchestrate the full pipeline flow    | `main()`                                                  |

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
  - **Timestamp standardization**: Force-convert `event_timestamp` and `ingestion_timestamp` to UTC timestamps (on parse failure, set to null and flag).
  - **Currency normalization**: Convert the `currency` field to uppercase; non-standard ISO codes (e.g. not USD, EUR) are auto-corrected to `USD` and an `_is_invalid_currency` boolean flag column is added.
  - **Numeric check**: Check whether `amount` is ≥ 0; if negative, flag as anomalous (but do not block the write).
- **Input**: Validated DataFrame.
- **Output**: Cleaned DataFrame with additional flag columns (e.g. `_is_invalid_currency`).
- **Special handling**: If a type conversion fails (e.g. letters mixed into the amount field), a `_raw_<field>` column is automatically generated to retain the original string, and `_validation_status` is set to `type_mismatch`.

### 2.4 `transformation/deduplicator.py`
- **Description**: Deduplicates by `event_id`. When duplicate IDs appear, the record with the **latest** `ingestion_timestamp` is retained.
- **Input**: Cleaned DataFrame.
- **Output**: Deduplicated DataFrame.
- **Side effect**: Superseded duplicate records are written to `logs/duplicates.log` (including duplicate ID and timestamp) for post-hoc audit.

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
- **Description**: Parses CLI arguments (`--env` and `--input` file path), calls each module in sequence, forming the complete ETL.
- **Execution order (DAG)**:
  1. Load configuration.
  2. Call `ingestion` to read data.
  3. Call `validation` to split valid/invalid data.
  4. Call `cleaner` and `deduplicator` to process valid data.
  5. Write to Silver layer (partitioned by `event_date`, Parquet format).
  6. Call `builder` to generate Gold-layer data and write to the corresponding directory.
  7. Collect and output `metrics.json` (total rows, passed, failed, duration).
- **Idempotency guarantee**: Both Silver and Gold writes use "overwrite specific partition" mode, ensuring that re-running the same date does not produce duplicate data.

---

## 3. Configuration and Contract Management (Non-code)

### 3.1 Configuration File Structure (YAML Template)
- `config/dev.yaml`, `config/test.yaml`, `config/prod.yaml`.
- **Core config items**:
  - `storage.base_path`: Data storage root directory (local or S3).
  - `validation.schema_path`: Path to `schema.yaml`.
  - `logging.level`: Log level (INFO/DEBUG).
  - `alert.slack_webhook`: Alert callback URL (only configured in production).

### 3.2 Data Contract (Schema Registry)
- `config/schema.yaml` explicitly defines fields, types, required flags, enum value whitelists, and regex patterns.
- For future extensions, modifying this YAML takes effect without changing core Python logic.

---

## 4. Cross-module Communication Specification
- **Data carrier**: All modules pass data via **Pandas DataFrame**.
- **Metadata passing**: Modules can pass lightweight metadata (e.g. processing timestamp, source filename) via the DataFrame's `attrs` attribute, avoiding reliance on global variables.
- **Error passing**: Validation or cleaning modules do not raise exceptions to interrupt the flow; instead, they pass problem data downstream or to the quarantine area via the returned `invalid_df` or flag columns (e.g. `_validation_status`).

## 5. Test Extension Point Design
- All module interfaces use DataFrame as input/output, not depending on specific file paths, making unit testing (`pytest`) straightforward.
- A `test_helpers.py` is provided in `common/` for generating standardized mock data (fixtures), ensuring a reproducible test environment.
