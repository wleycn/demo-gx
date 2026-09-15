#!/usr/bin/env python
# [AI-GENERATED] model=qianfan-code-latest date=2026-09-15 reviewed_by=pending
"""Command-line entry point for the data pipeline.

The CLI orchestrates the full ETL flow:
read -> validate -> clean -> deduplicate -> Silver -> Gold.

Environment configuration and schema contracts are loaded centrally
via ``common.config`` (from ``config/`` at the project root).
"""

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

from demo_gx.common.config import PROJECT_ROOT, load_config, load_schema
from demo_gx.common.logger import setup_logging
from demo_gx.common.metrics import MetricsCollector
from demo_gx.common.time_utils import parse_utc_mixed
from demo_gx.curation.builder import GoldBuilder
from demo_gx.ingestion.reader import read_input, write_bronze
from demo_gx.transformation.cleaner import DataCleaner
from demo_gx.transformation.deduplicator import Deduplicator
from demo_gx.validation.error_envelope import write_error_envelope
from demo_gx.validation.schema_validator import SchemaValidator


def main() -> None:
    """Run the pipeline end-to-end from the command line.

    Parses ``--env`` and the optional ``--input`` / ``--event-date`` arguments,
    then executes the six-stage ETL flow (read, validate, clean, deduplicate,
    write Silver, build and write Gold).  Metrics are always persisted, even
    on failure.

    Exit codes, as published in INTERFACE-DESIGN.md section 1: ``0`` a completed
    run, ``1`` an unhandled exception, ``2`` nothing matched the date scope,
    ``3`` nothing valid survived validation.
    """
    # Anchor relative paths (storage/logs/metrics/input) to the project root
    # so the pipeline behaves identically regardless of the caller's CWD
    # (e.g. cron without cd) — dev-review: CWD-relative drift.
    os.chdir(PROJECT_ROOT)
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default="dev", choices=["dev", "test", "prod"])
    parser.add_argument(
        "--input",
        help="Path to the input file; defaults to the environment's "
        "inbound drop location (<env root>/input/sample_data.json)",
    )
    parser.add_argument("--event-date", help="Override event date for processing (YYYY-MM-DD)")
    parser.add_argument(
        "--run-timestamp",
        help="ISO-8601 run timestamp injected by the orchestrator; "
        "defaults to the wall clock read once at this entry boundary",
    )
    args = parser.parse_args()

    # The run timestamp enters the pipeline exactly here and is then threaded
    # down as a parameter. The CLI is the outermost boundary (the stand-in for
    # a scheduler), so this single read is the only place the pipeline touches
    # the system clock for data stamping — AGENTS.md section 3 red line 10.
    # Passing --run-timestamp makes a run byte-reproducible.
    run_ts = pd.Timestamp(args.run_timestamp) if args.run_timestamp else pd.Timestamp.now(tz="UTC")
    if run_ts.tzinfo is None:
        run_ts = run_ts.tz_localize("UTC")

    # Load environment configuration
    config = load_config(args.env)
    # The input path defaults to the environment's inbound drop location, so a
    # bare `python -m demo_gx.cli --env test` runs with no path argument. Both
    # the directory and the file name come from config, never from a literal
    # here (AGENTS.md section 3 red line 5).
    input_path = args.input or str(Path(config["storage"]["input_root"]) / config["storage"]["input_file"])
    logger = setup_logging(level=config["logging"]["level"], log_file=config["logging"].get("file"))
    logger.info("Starting pipeline with env=%s, input=%s", args.env, input_path)
    metrics = MetricsCollector()

    try:
        # 1. Read input. Direct identifiers are masked here, at the ingestion
        #    boundary, so nothing downstream holds a clear-text value.
        logger.info("Reading input...")
        pii = config.get("pii", {})
        masked_fields = pii.get("masked_fields", [])
        raw_df = read_input(input_path, masked_fields=masked_fields, pepper=pii.get("pepper", ""))
        if masked_fields:
            logger.info("Masked %s field(s) at the ingestion boundary", len(masked_fields))
        metrics.increment("input_rows", len(raw_df))
        logger.info("Read %s rows", len(raw_df))

        # 1b. Archive every raw record to Bronze (before any quality gate,
        #     so rows later quarantined are still preserved for replay/audit)
        logger.info("Writing Bronze archive...")
        bronze_base = Path(config["storage"]["output_root"]) / config["storage"]["bronze_subpath"]
        bronze_written = write_bronze(raw_df, bronze_base, run_ts)
        metrics.increment("bronze_rows", bronze_written)

        # 1c. Optional event-date backfill scope: when --event-date is given,
        #     process only rows whose event_timestamp falls on that date
        #     (safe backfill per DATA-DESIGN.md section 2.6). Bronze above always keeps
        #     the full arriving batch for replay.
        if args.event_date:
            target_date = pd.to_datetime(args.event_date).date()
            # Shared parsing policy so scoping matches validator behaviour
            evt_date = parse_utc_mixed(raw_df["event_timestamp"]).dt.date
            # Rows whose timestamp does not parse have no event date: keep
            # them so the validator quarantines them instead of dropping them
            # silently outside the scope (round-2 writer QC #10)
            raw_df = raw_df[(evt_date == target_date) | evt_date.isna()]
            logger.info("--event-date %s: processing %s scoped rows", args.event_date, len(raw_df))
            if raw_df.empty:
                logger.warning("No rows with event_date=%s, stopping.", args.event_date)
                metrics.save(config["metrics"]["output_file"])
                # 2 = nothing in scope. A scheduler has to tell this apart from
                # a plain success; see INTERFACE-DESIGN.md section 1.
                sys.exit(2)

        # 2. Validate schema
        logger.info("Validating schema...")
        schema_cfg = load_schema()
        validator = SchemaValidator(schema_cfg, run_ts)
        valid_df, invalid_df = validator.validate(raw_df)
        metrics.increment("valid_rows", len(valid_df))
        metrics.increment("invalid_rows", len(invalid_df))
        logger.info("Valid: %s, Invalid: %s", len(valid_df), len(invalid_df))
        # Write invalid records to the error quarantine area
        if not invalid_df.empty:
            errors_path = Path(config["storage"]["output_root"]) / config["storage"]["errors_subpath"] / "quarantine"
            # Envelope fields and reason classification belong to the validation
            # layer (INTERFACE-DESIGN.md section 4); the orchestrator only
            # supplies the destination and the run timestamp.
            write_error_envelope(invalid_df, errors_path, run_ts)
            logger.warning("Invalid records written to %s", errors_path)

        if valid_df.empty:
            logger.warning("No valid records, stopping.")
            metrics.save(config["metrics"]["output_file"])
            # 3 = nothing valid survived validation. No Silver and no Gold were
            # written, so this is not a plain success either.
            sys.exit(3)

        # 3. Clean data
        logger.info("Cleaning data...")
        cleaner = DataCleaner()
        cleaned_df = cleaner.standardize_timestamps(valid_df)
        cleaned_df = cleaner.normalize_currency(cleaned_df)
        cleaned_df = cleaner.check_amount(cleaned_df)
        # Add event_date partition column
        cleaned_df["event_date"] = pd.to_datetime(cleaned_df["event_timestamp"]).dt.date

        # 4. Deduplicate
        logger.info("Deduplicating...")
        deduper = Deduplicator()
        deduped_df, duplicates_df = deduper.deduplicate(cleaned_df)
        metrics.increment("duplicates_removed", len(duplicates_df))
        if not duplicates_df.empty:
            dup_dir = Path(config["storage"]["output_root"]) / config["storage"]["errors_subpath"] / "duplicates"
            # Partition-scoped overwrite by event_date, same as quarantine and
            # Silver (AGENTS.md red line 1: bare append is forbidden).
            for date_val, group in duplicates_df.groupby("event_date"):
                date_str = str(date_val)
                part_path = dup_dir / f"event_date={date_str}"
                part_path.mkdir(parents=True, exist_ok=True)
                tmp_file = part_path / "data.parquet.tmp"
                group.to_parquet(tmp_file, index=False)
                tmp_file.replace(part_path / "data.parquet")
            logger.info("Duplicates written to %s", dup_dir)
        metrics.increment("silver_rows", len(deduped_df))
        # DATA-DESIGN.md section 2.3: _processed_timestamp is added automatically at
        # write time (pipeline processing timestamp, UTC), injected by the
        # entry boundary rather than read here (AGENTS.md section 3 red line 10)
        deduped_df["_processed_timestamp"] = run_ts

        # 5. Write Silver layer
        silver_path = Path(config["storage"]["output_root"]) / config["storage"]["silver_subpath"]
        # Partition by event_date
        for date, group in deduped_df.groupby("event_date"):
            date_str = date.strftime("%Y-%m-%d")
            part_path = silver_path / f"event_date={date_str}"
            part_path.mkdir(parents=True, exist_ok=True)
            group.to_parquet(part_path / "data.parquet", index=False)
            logger.info("Silver data written to %s", part_path)

        # 6. Build Gold layer — ALWAYS from the on-disk Silver snapshot, never
        #    from the in-memory batch: dims and wide are full snapshots, so a
        #    --event-date scoped (backfill) run must not rebuild them from the
        #    scoped subset or rows/first_seen_date would be lost (round-2 QC #7).
        logger.info("Building Gold layer...")
        silver_base = Path(config["storage"]["output_root"]) / config["storage"]["silver_subpath"]
        silver_files = sorted(silver_base.glob("event_date=*/data.parquet"))
        if silver_files:
            gold_input = pd.concat([pd.read_parquet(f) for f in silver_files], ignore_index=True)
        else:
            gold_input = deduped_df.iloc[0:0]
        builder = GoldBuilder()
        fact_df = builder.build_fact_table(gold_input)
        dims = builder.build_dimensions(gold_input)
        wide_df = builder.build_wide_table(fact_df, dims)

        # Write Gold outputs
        gold_base = Path(config["storage"]["output_root"]) / config["storage"]["gold_subpath"]
        # Fact table (partitioned)
        for date, group in fact_df.groupby("event_date"):
            date_str = date.strftime("%Y-%m-%d")
            fact_path = gold_base / "fact_daily_events" / f"event_date={date_str}"
            fact_path.mkdir(parents=True, exist_ok=True)
            group.to_parquet(fact_path / "data.parquet", index=False)
        # Dimension tables (full snapshot, non-partitioned)
        for dim_name, dim_df in dims.items():
            dim_path = gold_base / dim_name
            dim_path.mkdir(parents=True, exist_ok=True)
            dim_df.to_parquet(dim_path / "data.parquet", index=False)
        # Wide table (partitioned)
        if not wide_df.empty:
            for date, group in wide_df.groupby("event_date"):
                date_str = date.strftime("%Y-%m-%d")
                wide_path = gold_base / "wide_daily_user_events" / f"event_date={date_str}"
                wide_path.mkdir(parents=True, exist_ok=True)
                group.to_parquet(wide_path / "data.parquet", index=False)

        metrics.increment("gold_rows", len(fact_df))

        # Save metrics
        logger.info("Saving metrics...")
        metrics.save(config["metrics"]["output_file"])
        logger.info("Pipeline completed successfully.")

    except Exception as e:
        logger.exception("Pipeline failed: %s", e)
        metrics.add_error(str(e))
        metrics.save(config["metrics"]["output_file"])
        sys.exit(1)


if __name__ == "__main__":
    main()
