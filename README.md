# Pipeline 项目

## 本地运行步骤

1. 安装依赖：`pip install -r requirements.txt`
2. 生成样本数据：`python scripts/generate_sample_data.py`
3. 运行管道：`python pipeline/cli.py --input sample_data.json --env dev`

## 设计笔记

详见 `docs/` 目录。

## 权衡取舍

- 使用 Pandas 单机处理，适用于 <10GB 数据。
- 分区覆盖写入保证幂等性。
- 严格模式拒绝未知字段，维护数据契约。

## 生产就绪改进计划

- 迁移到 PySpark 处理更大数据。
- 集成 Great Expectations 进行数据质量验证。
- 使用 Airflow 编排调度。
- 增加 OpenLineage 血缘追踪。

---
现在，所有代码和配置文件都已提供。请将以上内容保存到对应文件中。确保目录结构如下：

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

测试命令：
生成数据：python scripts/generate_sample_data.py
运行管道：python pipeline/cli.py --input sample_data.json --env dev
运行测试：pytest tests/
请检查，如果需要调整，告诉我。