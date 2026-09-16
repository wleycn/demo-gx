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
from demo_gx.common.storage import write_table
from demo_gx.common.time_utils import parse_utc_mixed
from demo_gx.curation.builder import GoldBuilder
from demo_gx.ingestion.reader import read_input, write_bronze
from demo_gx.transformation.cleaner import DataCleaner
from demo_gx.transformation.deduplicator import Deduplicator
from demo_gx.validation.error_envelope import write_error_envelope
from demo_gx.validation.schema_validator import SchemaValidator


def _covered_dates(frame: pd.DataFrame) -> list[str]:
    """Return the event dates a run covers, as partition values.

    Every parsed event day, plus the literal ``unknown`` when the frame holds a
    timestamp that does not parse — that is the quarantine's own key for those
    rows. The error tables clear the covered days they produced nothing for, so
    this names the days the run *covered*, not the days it *wrote*.

    Args:
        frame (pandas.DataFrame): The frame as it enters validation.

    Returns:
        list[str]: Sorted partition values.
    """
    if "event_timestamp" not in frame.columns:
        return ["unknown"]
    dates = parse_utc_mixed(frame["event_timestamp"]).dt.date
    covered = {str(day.strftime("%Y-%m-%d")) for day in dates.dropna().unique()}
    if dates.isna().any():
        covered.add("unknown")
    return sorted(covered)


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

        # The dates this run covers, as partition values. The error tables clear
        # the covered days that produced nothing, so "nothing went wrong here"
        # is visible in the artefacts instead of an earlier run's rows
        # surviving (code audit, 2026-09-15).
        covered_dates = _covered_dates(raw_df)

        # 2. Validate schema
        logger.info("Validating schema...")
        schema_cfg = load_schema()
        validator = SchemaValidator(schema_cfg, run_ts)
        valid_df, invalid_df = validator.validate(raw_df)
        metrics.increment("valid_rows", len(valid_df))
        metrics.increment("invalid_rows", len(invalid_df))
        logger.info("Valid: %s, Invalid: %s", len(valid_df), len(invalid_df))
        # Write the error quarantine. This runs even when nothing was rejected,
        # because it also clears the covered days that no longer have rejects:
        # a rerun after a fix must not leave the earlier rows behind.
        errors_base = Path(config["storage"]["output_root"]) / config["storage"]["errors_subpath"]
        quarantine_path = errors_base / "quarantine"
        # Envelope fields and reason classification belong to the validation
        # layer (INTERFACE-DESIGN.md section 4); the orchestrator only
        # supplies the destination and the run timestamp.
        quarantined = write_error_envelope(invalid_df, quarantine_path, run_ts, scope=covered_dates)
        if quarantined:
            logger.warning("Invalid records written to %s", quarantine_path)
        else:
            logger.info("No invalid records for %s: no quarantine partition kept", covered_dates)

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
        # Add event_date partition column. Parsed through the shared policy so
        # the scoping above, the validator, Silver and Gold cannot disagree.
        cleaned_df["event_date"] = parse_utc_mixed(cleaned_df["event_timestamp"]).dt.date

        # 4. Deduplicate
        logger.info("Deduplicating...")
        deduper = Deduplicator()
        deduped_df, duplicates_df = deduper.deduplicate(cleaned_df)
        metrics.increment("duplicates_removed", len(duplicates_df))
        # Partition-scoped overwrite by event_date, same as the quarantine and
        # Silver (AGENTS.md red line 1: bare append is forbidden). Written even
        # when the frame is empty, so a covered day that no longer has
        # duplicates loses its partition.
        dup_dir = errors_base / "duplicates"
        duplicate_files = write_table(duplicates_df, dup_dir, "event_date", scope=covered_dates)
        if duplicate_files:
            logger.info("Duplicates written to %s", dup_dir)
        metrics.increment("silver_rows", len(deduped_df))
        # DATA-DESIGN.md section 2.3: _processed_timestamp is added automatically at
        # write time (pipeline processing timestamp, UTC), injected by the
        # entry boundary rather than read here (AGENTS.md section 3 red line 10)
        deduped_df["_processed_timestamp"] = run_ts

        # 5. Write Silver layer
        silver_path = Path(config["storage"]["output_root"]) / config["storage"]["silver_subpath"]
        # Partition by event_date, written atomically through the shared helper
        # so a crash cannot destroy the partition that was already there.
        silver_files_written = write_table(deduped_df, silver_path, "event_date", scope=covered_dates)
        logger.info("Silver data written under %s (%s file(s))", silver_path, len(silver_files_written))

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

        # Write Gold outputs. Gold is rebuilt from the on-disk Silver snapshot,
        # so the partitions it owns are exactly the ones that snapshot holds;
        # every write goes through the shared helper for the same atomicity as
        # the rest of the pipeline.
        gold_base = Path(config["storage"]["output_root"]) / config["storage"]["gold_subpath"]
        # Fact table (partitioned)
        write_table(fact_df, gold_base / "fact_daily_events", "event_date")
        # Dimension tables (full snapshot, single file)
        for dim_name, dim_df in dims.items():
            write_table(dim_df, gold_base / dim_name)
        # Wide table (partitioned)
        write_table(wide_df, gold_base / "wide_daily_user_events", "event_date")

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
