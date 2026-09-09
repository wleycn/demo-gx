#!/usr/bin/env python
import argparse
import sys
from pathlib import Path
import pandas as pd

from common.config import load_config, load_schema
from common.logger import setup_logging, get_logger
from common.metrics import MetricsCollector
from ingestion.reader import read_input
from validation.schema_validator import SchemaValidator
from transformation.cleaner import DataCleaner
from transformation.deduplicator import Deduplicator
from curation.builder import GoldBuilder

"""
数据管道 CLI 入口：读取 → 校验 → 清洗 → 去重 → Silver → Gold。
环境配置与 schema 契约统一由 common.config 加载（项目根 config/）。
"""
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default="dev", choices=["dev", "test", "prod"])
    parser.add_argument("--input", required=True, help="Path to input file")
    parser.add_argument("--event-date", help="Override event date for processing (YYYY-MM-DD)")
    args = parser.parse_args()

    # 加载配置
    config = load_config(args.env)
    logger = setup_logging(
        level=config["logging"]["level"],
        log_file=config["logging"].get("file")
    )
    logger.info(f"Starting pipeline with env={args.env}, input={args.input}")
    metrics = MetricsCollector()

    try:
        # 1. 读取
        logger.info("Reading input...")
        raw_df = read_input(args.input)
        metrics.increment("input_rows", len(raw_df))
        logger.info(f"Read {len(raw_df)} rows")

        # 2. 校验
        logger.info("Validating schema...")
        schema_cfg = load_schema()
        validator = SchemaValidator(schema_cfg)
        valid_df, invalid_df = validator.validate(raw_df)
        metrics.increment("valid_rows", len(valid_df))
        metrics.increment("invalid_rows", len(invalid_df))
        logger.info(f"Valid: {len(valid_df)}, Invalid: {len(invalid_df)}")
        # 写入错误
        if not invalid_df.empty:
            errors_path = Path(config["storage"]["base_path"]) / config["storage"]["errors_subpath"] / "bad_schema"
            errors_path.mkdir(parents=True, exist_ok=True)
            invalid_df.to_json(errors_path / f"{pd.Timestamp.utcnow().isoformat()}_errors.json", orient="records", lines=True)
            logger.warning(f"Invalid records written to {errors_path}")

        if valid_df.empty:
            logger.warning("No valid records, stopping.")
            metrics.save(config["metrics"]["output_file"])
            return

        # 3. 清洗
        logger.info("Cleaning data...")
        cleaner = DataCleaner()
        cleaned_df = cleaner.standardize_timestamps(valid_df)
        cleaned_df = cleaner.normalize_currency(cleaned_df)
        cleaned_df = cleaner.check_amount(cleaned_df)
        # 添加 event_date 分区列
        cleaned_df["event_date"] = pd.to_datetime(cleaned_df["event_timestamp"]).dt.date

        # 4. 去重
        logger.info("Deduplicating...")
        deduper = Deduplicator()
        deduped_df, duplicates_df = deduper.deduplicate(cleaned_df)
        metrics.increment("duplicates_removed", len(duplicates_df))
        if not duplicates_df.empty:
            dup_log = Path(config["storage"]["base_path"]) / config["storage"]["errors_subpath"] / "duplicates.log"
            dup_log.parent.mkdir(parents=True, exist_ok=True)
            with open(dup_log, "a") as f:
                duplicates_df.to_csv(f, index=False, header=False)
            logger.info(f"Duplicates logged to {dup_log}")
        metrics.increment("silver_rows", len(deduped_df))

        # 5. 写入 Silver
        silver_path = Path(config["storage"]["base_path"]) / config["storage"]["silver_subpath"]
        # 按 event_date 分区写入
        for date, group in deduped_df.groupby("event_date"):
            date_str = date.strftime("%Y-%m-%d")
            part_path = silver_path / f"event_date={date_str}"
            part_path.mkdir(parents=True, exist_ok=True)
            group.to_parquet(part_path / "data.parquet", index=False)
            logger.info(f"Silver data written to {part_path}")

        # 6. 构建 Gold
        logger.info("Building Gold layer...")
        builder = GoldBuilder()
        fact_df = builder.build_fact_table(deduped_df)
        dims = builder.build_dimensions(deduped_df)
        wide_df = builder.build_wide_table(fact_df, dims)

        # 写入 Gold
        gold_base = Path(config["storage"]["base_path"]) / config["storage"]["gold_subpath"]
        # Fact
        for date, group in fact_df.groupby("event_date"):
            date_str = date.strftime("%Y-%m-%d")
            fact_path = gold_base / "fact_daily_events" / f"event_date={date_str}"
            fact_path.mkdir(parents=True, exist_ok=True)
            group.to_parquet(fact_path / "data.parquet", index=False)
        # Dims
        for dim_name, dim_df in dims.items():
            dim_path = gold_base / dim_name
            dim_path.mkdir(parents=True, exist_ok=True)
            dim_df.to_parquet(dim_path / "data.parquet", index=False)
        # Wide
        if not wide_df.empty:
            for date, group in wide_df.groupby("event_date"):
                date_str = date.strftime("%Y-%m-%d")
                wide_path = gold_base / "wide_daily_user_events" / f"event_date={date_str}"
                wide_path.mkdir(parents=True, exist_ok=True)
                group.to_parquet(wide_path / "data.parquet", index=False)

        metrics.increment("gold_rows", len(fact_df))

        # 保存指标
        logger.info("Saving metrics...")
        metrics.save(config["metrics"]["output_file"])
        logger.info("Pipeline completed successfully.")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        metrics.add_error(str(e))
        metrics.save(config["metrics"]["output_file"])
        sys.exit(1)

if __name__ == "__main__":
    main()

