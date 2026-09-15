# Domain Language

Project-specific terms used throughout the codebase and documentation. Terms are listed alphabetically.

| Term | English | Meaning | Where it appears |
|---|---|---|---|
| backfill | backfill | Reprocessing data for a specific date by passing `--event-date YYYY-MM-DD` to the CLI. The processing semantics live in DATA-DESIGN.md section 1. | INTERFACE-DESIGN, cli.py |
| Bronze | Bronze (raw layer) | The first layer of the lakehouse pipeline. Stores raw input as JSON Lines, immutable, no quality checks. Partitioned by `source_system` and ingestion date. | DATA-DESIGN, MODULE-DESIGN, reader.py |
| data layer mapping | data layer mapping | This project names its lakehouse layers Bronze / Silver / Gold. The upstream data-processing skeleton names the same stages `ods` / `dwd` / `dws` / `ads`. Correspondence: Bronze = ods (raw landing), Silver = dwd (cleaned detail), Gold = dws (subject aggregation). There is no separate ads layer; the wide table serves that role. | KNOWN-ISSUE.md, section "Skeleton Deviations" |
| dimension table | dimension table | A Gold-layer table that stores descriptive attributes for a business entity. This project has two: `dim_customer` and `dim_event_type`. Both are full snapshots (non-partitioned). | DATA-DESIGN, builder.py |
| event_date | event_date | The date portion of `event_timestamp`, used as the partition key for Silver, the Gold fact table, and the wide table. Typed as `date`. | DATA-DESIGN, cli.py, builder.py |
| fact table | fact table | A Gold-layer table that stores quantitative measures at a specific grain. This project has one: `fact_daily_events`, partitioned by `event_date`, with measures `event_count`, `total_amount`, `avg_amount`. | DATA-DESIGN, builder.py |
| Gold | Gold (curated layer) | The third layer of the lakehouse pipeline. Stores subject-oriented aggregations and dimensional models for BI and analytics. Written as Parquet. | DATA-DESIGN, MODULE-DESIGN, builder.py |
| quarantine | quarantine | The act of isolating invalid records into `errors/bad_schema/` instead of blocking the pipeline. Invalid records get an error envelope and the pipeline continues processing valid data. | DATA-DESIGN, INTERFACE-DESIGN, schema_validator.py |
| Silver | Silver (cleaned layer) | The second layer of the lakehouse pipeline. Stores validated, deduplicated, and standardized detail data as Parquet, partitioned by `event_date`. | DATA-DESIGN, MODULE-DESIGN, cli.py |
| source_system | source_system | A required field identifying the origin of an event. Enum values: `web`, `mobile`, `api`. Also used as a Bronze partition key (raw value, no enum check at Bronze). | schema.yaml, DATA-DESIGN, reader.py |
| strict mode | strict mode | Validation policy that rejects unknown fields not declared in `config/data/schema.yaml`. Row-level key presence is judged from the preserved `_raw_json` when available. | MODULE-DESIGN, schema_validator.py |
| wide table | wide table (denormalized view) | A Gold-layer table that left-joins the fact table with dimension tables into a single flat table for direct BI queries. This project has one: `wide_daily_user_events`, partitioned by `event_date`. | DATA-DESIGN, builder.py |
