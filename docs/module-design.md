# 功能模块设计（接口契约与职责定义）

> **设计原则**：严格的关注点分离（Separation of Concerns）。每个模块只负责一件事，通过标准化的 DataFrame 契约进行通信。所有配置（路径、验证阈值）由配置中心（`common/config`）统一管理，严禁硬编码。

## 1. 模块总览

| 模块目录 | 脚本文件 | 核心职责 | 对外暴露的接口（功能/类） |
| :--- | :--- | :--- | :--- |
| `ingestion/` | `reader.py` | 适配不同文件格式（JSON/CSV/Parquet），读取原始数据并附加溯源列 | `read_input(file_path)` |
| `validation/` | `schema_validator.py` | 执行严格的数据契约校验（字段存在性、类型、枚举、格式） | `validate_schema(df)` |
| `transformation/` | `cleaner.py` | 数据清洗（时间戳标准化、货币归一化、异常值标记） | `standardize_timestamps(df)`, `normalize_currency(df)` |
| `transformation/` | `deduplicator.py` | 基于业务主键（`event_id`）去重，保留最新记录 | `deduplicate(df)` |
| `curation/` | `builder.py` | 构建金层星型模型（事实表、维度表、宽表） | `build_fact_table(df)`, `build_dimensions(df)`, `build_wide_table(df)` |
| `common/` | `config.py` | 加载 YAML 配置文件，注入环境变量 | `load_config(env)` |
| `common/` | `logger.py` | 提供结构化日志（JSON 格式）和审计指标收集 | `get_logger()`, `collect_metrics()` |
| `cli/` | `cli.py` | 命令行入口，解析参数，串联整个管道流程 | `main()` |

---

## 2. 模块接口契约（输入/输出定义）

### 2.1 `ingestion/reader.py`
- **功能描述**：根据传入文件路径的后缀（`.json`, `.csv`, `.parquet`）自动选择读取引擎。读取后，必须为每一行保留原始 JSON 字符串（存入 `_raw_json` 列），以便在 Bronze 层实现完全可审计的回放。
- **输入**：文件路径（字符串或 Path 对象）。
- **输出**：包含原始数据及 `_raw_json` 列的 Pandas DataFrame。
- **异常处理**：若文件后缀不支持或文件不存在，抛出明确异常，由 CLI 层捕获并记录。

### 2.2 `validation/schema_validator.py`
- **功能描述**：基于配置文件（`config/schema.yaml`）中定义的 8 个必填字段执行校验。采用**严格模式（Strict Mode）**：
  - 拒绝所有未在契约中定义的额外字段（直接丢弃）。
  - 校验字段是否缺失、类型是否兼容（如字符串、数值）、格式是否正确（如 UUID、ISO 时间戳）。
- **输入**：原始 DataFrame。
- **输出**：返回两个 DataFrame 的元组 `(valid_df, invalid_df)`。`invalid_df` 附带 `error_reason` 列，说明具体违规项。
- **失败策略**：无效记录写入 `errors/bad_schema/`，**不阻塞**有效数据的处理。

### 2.3 `transformation/cleaner.py`
- **功能描述**：
  - **时间标准化**：将 `event_timestamp` 和 `ingestion_timestamp` 强制转为 UTC 时区的时间戳（若解析失败，置为空值并标记）。
  - **货币归一化**：将 `currency` 字段统一转为大写，非标准 ISO 码（如 USD、EUR）自动修正为 `USD` 并添加 `_is_invalid_currency` 布尔标记列。
  - **数值检查**：检查 `amount` 是否 ≥ 0，若为负数则标记异常（但不阻断写入）。
- **输入**：校验通过的 DataFrame。
- **输出**：清洗完成、带有额外标记列（如 `_is_invalid_currency`）的 DataFrame。
- **特殊处理**：若发生类型转换失败（如金额字段混入字母），需自动生成 `_raw_<field>` 列保留原始字符串，并修改 `_validation_status` 为 `type_mismatch`。

### 2.4 `transformation/deduplicator.py`
- **功能描述**：按 `event_id` 去重。当出现重复 ID 时，依据 `ingestion_timestamp` 字段保留**最新**的一条记录。
- **输入**：清洗后的 DataFrame。
- **输出**：去重后的 DataFrame。
- **副作用**：被剔除的重复记录需写入 `logs/duplicates.log`（包含重复 ID 和时间戳），便于事后审计。

### 2.5 `curation/builder.py`（金层构建）
- **功能描述**：将银层明细数据聚合为面向分析的数据产品。
  - **事实表**：按 `event_date`、`customer_id`、`event_type` 分组，计算 `event_count`、`total_amount`、`avg_amount`。
  - **维度表**：从银层提取 `dim_customer`（仅 `customer_id`，未来可扩展）和 `dim_event_type`（仅 `event_type`）。
  - **宽表**：将事实表与维度表进行左连接，生成单张非规范化宽表，供 BI 工具直接查询。
- **输入**：银层 DataFrame。
- **输出**：三个独立的 DataFrame（`fact_df`、`dims_dict`、`wide_df`）。

### 2.6 `common/config.py`
- **功能描述**：读取 `config/{env}.yaml`，将 YAML 内容解析为 Python 字典。支持从环境变量覆盖敏感配置（如存储路径前缀）。
- **输入**：环境标识（`dev`、`test`、`prod`）。
- **输出**：配置字典（包含输入/输出路径、验证阈值、告警 Webhook 地址等）。

### 2.7 管道入口 `cli.py`
- **功能描述**：解析命令行参数（`--env` 和 `--input` 文件路径），按顺序调用各模块，构成完整 ETL。
- **执行顺序（DAG）**：
  1. 加载配置。
  2. 调用 `ingestion` 读取数据。
  3. 调用 `validation` 分割有效/无效数据。
  4. 调用 `cleaner` 和 `deduplicator` 处理有效数据。
  5. 写入银层（按 `event_date` 分区，Parquet 格式）。
  6. 调用 `builder` 生成金层数据，并写入对应目录。
  7. 收集并输出 `metrics.json`（总行数、通过数、失败数、耗时）。
- **幂等性保证**：写入银层和金层时均采用“覆盖特定分区”模式，确保重复运行同一日期不会产生重复数据。

---

## 3. 配置与契约管理（非代码部分）

### 3.1 配置文件结构（YAML 模板）
- `config/dev.yaml`、`config/test.yaml`、`config/prod.yaml`。
- **核心配置项**：
  - `storage.base_path`：数据存储根目录（本地或 S3）。
  - `validation.schema_path`：指向 `schema.yaml` 的路径。
  - `logging.level`：日志级别（INFO/DEBUG）。
  - `alert.slack_webhook`：告警回调地址（仅生产环境配置）。

### 3.2 数据契约（Schema Registry）
- `config/schema.yaml` 明确定义字段、类型、是否必填、枚举值白名单、正则模式。
- 未来扩展时，修改此 YAML 即可生效，无需改动核心 Python 逻辑。

---

## 4. 跨模块通信规范
- **数据载体**：所有模块之间通过 **Pandas DataFrame** 传递数据。
- **元数据传递**：模块可通过 DataFrame 的 `attrs` 属性传递轻量级元数据（如处理时间戳、源文件名），避免依赖全局变量。
- **错误传递**：校验或清洗模块不抛出异常中断流程，而是通过返回的 `invalid_df` 或标记列（如 `_validation_status`）将问题数据传递给下游或隔离区。

## 5. 测试扩展点设计
- 所有模块的接口均以 DataFrame 为输入/输出，不依赖具体文件路径，便于编写单元测试（`pytest`）。
- 在 `common/` 中提供 `test_helpers.py`，用于生成标准化的模拟数据（Fixture），确保测试环境可复现。

