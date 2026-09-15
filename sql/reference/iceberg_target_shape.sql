-- [AI-GENERATED] model=deepseek-flash date=2026-09-15 reviewed_by=pending
-- Production-shape DDL for the Bronze / Silver / Gold layers (Apache Iceberg).
--
-- Reference asset, not an executable migration. This repository runs on Pandas
-- with local Parquet files: there is no Spark, no Iceberg runtime and no catalog,
-- so nothing here is run by the pipeline, the Makefile or CI. Dialect: Spark SQL
-- plus Iceberg.
--
-- See docs/business/DATA-DESIGN.md section 2.7 for the mapping between the demo
-- layout and these tables, and docs/business/KNOWN-ISSUE.md for the decisions
-- that keep the demo on Pandas.

-- Bronze: raw archive, append-only and immutable ----------------------------
-- Catalog: HadoopCatalog pointed at a warehouse directory
CREATE DATABASE IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.events (
    event_id            STRING,
    source_system       STRING,
    customer_id         STRING,
    event_type          STRING,
    event_timestamp     TIMESTAMP,
    amount              DECIMAL(18,2),
    currency            STRING,
    ingestion_timestamp TIMESTAMP,
    _raw_json           STRING   -- full original record for replay/audit
)
USING iceberg
PARTITIONED BY (source_system, days(ingestion_timestamp))
TBLPROPERTIES (
    'format-version' = '2',
    'write.format.default' = 'parquet',
    'history.expire.max-snapshot-age-ms' = '2592000000'  -- 30-day Bronze retention
);

-- Append-only ingest (Bronze is immutable: never UPDATE/DELETE here)
INSERT INTO bronze.events
SELECT ... FROM source_staging_table;

-- Silver: cleaned detail, upsert by business key ----------------------------
CREATE DATABASE IF NOT EXISTS silver;

CREATE TABLE IF NOT EXISTS silver.events (
    event_id            STRING,
    source_system       STRING,
    customer_id         STRING,
    event_type          STRING,
    event_timestamp     TIMESTAMP,
    amount              DECIMAL(18,2),
    currency            STRING,
    ingestion_timestamp TIMESTAMP,
    event_date          DATE,
    _validation_status  STRING,  -- 'passed' (type_mismatch reserved, yellow path disabled)
    _raw_amount         STRING   -- original value kept on coercion failure
)
USING iceberg
PARTITIONED BY (days(event_timestamp))
TBLPROPERTIES ('format-version' = '2');

-- Deduplicated refresh of one date partition (retry-safe, ACID):
-- DELETE + INSERT inside one Iceberg transaction
DELETE FROM silver.events
WHERE event_date = '2026-09-09';

INSERT INTO silver.events
SELECT ... FROM bronze.events
WHERE days(ingestion_timestamp) = DATE '2026-09-09'
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY event_id ORDER BY ingestion_timestamp DESC
) = 1;

-- Alternative for incremental upsert (CDC-style): keep the newest record
MERGE INTO silver.events t
USING bronze.events_delta s
ON t.event_id = s.event_id
WHEN MATCHED AND s.ingestion_timestamp > t.ingestion_timestamp
    THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;

-- Gold: curated star schema, idempotent partition overwrite -----------------
CREATE DATABASE IF NOT EXISTS gold;

CREATE TABLE IF NOT EXISTS gold.fact_daily_events (
    event_date   DATE,
    customer_id  STRING,
    event_type   STRING,
    event_count  BIGINT,
    total_amount DECIMAL(18,2),
    avg_amount   DECIMAL(18,2)
)
USING iceberg
PARTITIONED BY (days(event_date));

-- Partition-overwrite write (equivalent of the demo's idempotent mode)
INSERT OVERWRITE gold.fact_daily_events
SELECT event_date, customer_id, event_type,
       COUNT(*)          AS event_count,
       SUM(amount)       AS total_amount,
       AVG(amount)       AS avg_amount
FROM silver.events
WHERE event_date = DATE '2026-09-09'
GROUP BY event_date, customer_id, event_type;

-- Dimension tables (dim_customer, dim_event_type) and the denormalized
-- wide table follow the same pattern; dims use full-snapshot refresh.

-- Analytics reads: snapshot isolation and time travel -----------------------
-- Snapshot as of a wall-clock time (consistent point-in-time read)
SELECT event_type, SUM(total_amount)
FROM gold.fact_daily_events
TIMESTAMP AS OF '2026-09-10 00:00:00'
GROUP BY event_type;

-- Explicit snapshot version
SELECT * FROM silver.events VERSION AS OF 12345678901234567;

-- Incremental consumption: only new snapshots since the last watermark
SELECT * FROM silver.events
WHERE _snapshot_id IN (
    SELECT snapshot_id FROM silver.events.snapshots
    WHERE committed_at > TIMESTAMP '2026-09-10 00:00:00'
);
