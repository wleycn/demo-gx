# Pipeline Project

## Local Run Steps

1. Install dependencies: `pip install -r requirements.txt`
2. Generate sample data: `python scripts/generate_sample_data.py`
3. Run the pipeline: `python pipeline/cli.py --input sample_data.json --env dev`

## Design Notes

See the `docs/` directory for details.

## Trade-offs

- Uses Pandas for single-machine processing, suitable for <10GB data.
- Partition overwrite writes ensure idempotency.
- Strict mode rejects unknown fields to maintain data contracts.
- Runtime constraint: the target production shape is a big-data framework
  (Spark + Iceberg); this repo is validated locally on Pandas because no
  cluster environment is available. Design & Iceberg SQL assets reflect the
  big-data shape — see docs/architecture.md §5 and docs/data-design.md §6.

## Production Readiness Improvement Plan

- Migrate to PySpark for larger data volumes.
- Integrate Great Expectations for data quality validation.
- Use Airflow for orchestration and scheduling.
- Add OpenLineage for lineage tracking.

---
All code and configuration files are now provided. Save the above content
to the corresponding files. Ensure the directory structure is as follows:

```text
project_root/
├── pipeline/
│   ├── __init__.py
│   ├── cli.py
│   ├── ingestion/
│   │   ├── __init__.py
│   │   └── reader.py
│   ├── validation/
│   │   ├── __init__.py
│   │   └── schema_validator.py
│   ├── transformation/
│   │   ├── __init__.py
│   │   ├── cleaner.py
│   │   └── deduplicator.py
│   ├── curation/
│   │   ├── __init__.py
│   │   └── builder.py
│   └── common/
│       ├── __init__.py
│       ├── config.py
│       ├── logger.py
│       └── metrics.py
├── config/
│   ├── dev.yaml
│   ├── test.yaml
│   ├── prod.yaml
│   └── schema.yaml
├── tests/
│   ├── __init__.py
│   └── test_validation.py
├── scripts/
│   └── generate_sample_data.py
├── requirements.txt
└── README.md
```

Test commands:
Generate data: python scripts/generate_sample_data.py
Run the pipeline: python pipeline/cli.py --input sample_data.json --env dev
Run tests: pytest tests/


git repo:
https://github.com/wleycn/demo-gx
