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

Exit codes. These are the codes the entry point returns:

| Code | Meaning |
|---|---|
| `0` | Completed: Silver and Gold were written |
| `1` | Unhandled exception; the message is in the log and in metrics `errors` |
| `2` | Nothing matched `--event-date`; Bronze still archived the arriving batch |
| `3` | Nothing valid survived validation; Silver and Gold were not touched |

Codes `2` and `3` exist so a scheduler can tell "ran and processed nothing" apart from "ran fine".
A run that stops at either code still writes `metrics.json`.

The run timestamp is read exactly once at the entry boundary and then threaded down as a parameter. Modules never read the system clock for data stamping. That single read makes the injected value authoritative.

### 1.1 Inspection Commands

Two read-only commands inspect a run in place. `make check-data` judges the artefacts against
`docs/tables/*.md`; `make show-data` prints the rows. Neither writes under `data/`.
The tools behind them are `scripts/check_data.py` and `scripts/show_data.py`, which take the same
selectors as long options.

Both accept four selectors:

| Selector | Default | Choices | Meaning |
|---|---|---|---|
| `ENV` | `dev` | `dev`, `test`, `prod` | Environment root to inspect |
| `LAYER` | `all` | `all`, `bronze`, `silver`, `gold`, `errors` | Layer to inspect |
| `TABLE` | none | any table on disk | One table. Gold tables take the directory name. |
| `DATE` | none | `YYYY-MM-DD` | One partition |

**Case**: the uppercase spelling is the documented one. Its lowercase twin sets the same value, so
`DATE=2026-09-01` and `date=2026-09-01` are the same selector. Mixed case stays a typo, because make
compares variable names exactly.

**Origin**: a selector counts only when it is given on the command line. An exported `COLUMNS` or
`ENV` cannot turn into one, and a typed `TABLE=` stays empty.

`show-data` adds four:

| Selector | Default | Choices | Meaning |
|---|---|---|---|
| `LIMIT` | `10` | integer | Rows for Parquet layers, lines for JSON layers |
| `COLUMNS` | all | comma-separated names | Columns to read and show |
| `FORMAT` | `table` | `table`, `json`, `csv` | Output shape |
| `SCHEMA` | off | see below | Names and types only, no rows read |

`SCHEMA` is a switch, not a value. `1`, `yes`, `true` and `on` turn it on; `0`, `no`, `false` and
`off` turn it off. Any other value stops the build, because a mistyped switch is not an answer.

Exit codes. These are the codes the tools return:

| Command | `0` | `1` | `2` | `3` |
|---|---|---|---|---|
| `check-data` | every check passed | a check failed | no table with that name on disk | nothing was scanned |
| `show-data` | something was shown | not used | the request does not match the data | nothing to look at |

`check-data` counts a missing artefact as a failed check, so a `DATE` whose partition is absent
returns `1`, not `3`. `show-data` returns `2` when a named table is absent, and also when
`FORMAT=json` or `csv` covers more than one table, because a machine format needs a single table in
scope. It reports a partition that holds no file and still returns `0`, because it never fails on a
data defect.

**Through make**: a non-zero recipe exit becomes make's own `2`. Read the printed summary line for
the tool's code, or call the script directly.

**Streams**: with `FORMAT=json` or `csv` the rows go to stdout and the report moves to stderr, so a
pipe carries data only.

**What `check-data` checks**: file and partition counts, row counts, column and type parity against
the contract, the declared partition key, business primary key uniqueness, and whether every field
under `pii.masked_fields` is masked. The layer is a parameter because the layers are structural.
The table is discovered from disk, so a table added to the pipeline is checked without editing the
tool.

**What `show-data` never does**: fail on a data defect. A table that breaks its contract is exactly
the table you want to look at.

The layer layout itself is in `DATA-DESIGN.md`.

## 2. Input Format

The reader auto-detects format by file extension:

| Extension | Read method | Notes |
|---|---|---|
| `.json` | `pd.read_json(path, lines=True)` | JSON Lines: one event object per line |
| `.csv` | `pd.read_csv(path)` | Standard CSV |
| `.parquet` | `pd.read_parquet(path)` | Parquet columnar |

After reading, a `_raw_json` column is appended to every row containing the row's original JSON string. This enables audit and replay in the Bronze layer.

### Expected Input Fields

Defined in `config/contract/schema.yaml`. All 8 fields are required.

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
| dev | `./data/dev` | `config/env/dev.yaml` |
| test | `./data/test` | `config/env/test.yaml` |
| prod | `./data/prod` | `config/env/prod.yaml` |

Each environment root splits by direction. The example is dev; test and prod mirror it under `data/test/` and `data/prod/`:

```text
data/dev/
├── input/          # inbound drop location; where --input defaults to (sample_data.json)
└── output/         # everything the pipeline writes
```

Every path shape below is relative to `output/`, written `{output_root}`. In dev that resolves to `data/dev/output/`.

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
├── quarantine/event_date={YYYY-MM-DD|unknown}/data.parquet    # Parquet, partition-overwritten
└── duplicates/event_date={YYYY-MM-DD}/data.parquet             # Parquet, partition-overwritten
```

Both tables are partitioned by the record's own event date and overwritten per
partition, the same as Silver. A record whose `event_timestamp` does not parse
goes to `event_date=unknown` in the quarantine table.

There is no separate type-conversion quarantine directory. Every rejected row goes into the single `quarantine/` table, including rows whose type conversion failed: they are filed with `error_type=type_coercion_failed`.

### 3.6 Metrics and Logs

```text
{output_root}/metrics.json
{output_root}/logs/pipeline.log
```

## 4. Error Envelope Fields

Invalid records are written to `errors/quarantine/event_date={YYYY-MM-DD|unknown}/data.parquet` as a partitioned Parquet table. The partition key is the record's own event date.

| Field | Type | Description |
|---|---|---|
| `original_json` | string | JSON rebuild of the offending row. Pandas round-trip: keys missing from the raw line render as `null`. |
| `error_type` | string | `schema_mismatch` or `type_coercion_failed`. Derived from the validator's per-rule error reason. |
| `error_details` | string | Specific reason text from the validator (e.g. "field 'event_id' missing", "amount not numeric"). |
| `ingestion_timestamp` | string (ISO-8601) | The UTC time the pipeline processed this record. |
| `event_date` | string | Partition key: `YYYY-MM-DD` derived from `event_timestamp`, or `unknown` when it does not parse. |

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
