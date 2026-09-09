# 数据管道架构设计

## 1. 设计目标

- 构建**可复用、可扩展**的参考实现，支持文件/API/数据库/事件流等源系统。
- 支持 **dev → test → prod** 环境晋升，通过配置切换。
- 强调**生产级思维**：质量检查、错误隔离、审计、成本感知。

## 2. 整体分层（Lakehouse 风格）


| 层     | 名称           | 存储格式        | 消费方            | 说明                               |
| ------ | -------------- | --------------- | ----------------- | ---------------------------------- |
| Bronze | Raw 原始层     | JSON / 原始文件 | 数据工程师/审计   | 存储原始输入，不可变，保留完整溯源 |
| Silver | Cleaned 清洗层 | Parquet（分区） | 数据科学家/分析师 | 验证通过、去重、标准化后的明细数据 |
| Gold   | Curated 聚合层 | Parquet / 宽表  | BI 报表/ML 特征   | 面向主题的聚合、维度建模、数据产品 |

## 3. 模块划分（关注点分离）

pipeline/
├── ingestion/ # 读取原始数据（支持JSON/CSV/Parquet）
├── validation/ # Schema验证 + 质量规则（空值/枚举/类型）
├── transformation/ # 清洗（标准化日期、货币）、去重
├── curation/ # 构建聚合/Gold（按customer/event_type汇总）
├── common/ # 日志、配置、异常处理、审计
└── cli.py # 统一入口（支持 --env dev/test/prod）

### Source Schema Alignment
本管道严格基于需求文档提供的 JSON 事件模板设计，核心字段及验证规则如下：

| 字段 | 类型 | 验证规则 | 错误处理 |
|------|------|----------|----------|
| event_id | string | UUID v4 格式，非空 | 缺失/格式错误 → 隔离至 errors/bad_schema/ |
| source_system | string | 枚举值 [web, mobile, api] | 非法值 → 隔离 + 告警 |
| customer_id | string | 非空字符串 | 缺失 → 隔离 |
| event_type | string | 非空，长度 ≤ 64 | 超长/空值 → 隔离 |
| event_timestamp | string (ISO8601) | 可解析为 UTC，≤ 当前时间 | 解析失败/未来时间 → 隔离 |
| amount | number | ≥ 0，精度 ≤ 2 位小数 | 负数/超限 → 隔离 |
| currency | string | ISO 4217 三字母码 | 非法码 → 默认 USD + 标记 |
| ingestion_timestamp | string (ISO8601) | 可解析为 UTC，≤ 当前时间 | 解析失败/未来时间 → 隔离 |


## 4. 数据流（Data Flow）

[输入文件] → ingestion.read()
↓
validation.validate_schema() → 失败记录写入 errors/ 并告警
↓
transformation.clean() → 填充缺失、格式标准化
transformation.deduplicate() → 基于 event_id 去重，保留最新
↓
写入 Silver (Parquet) → 按 event_date 分区
↓
curation.build_gold() → 生成每日汇总（总金额、事件计数）及宽表
↓
写入 Gold (Parquet) → 供下游查询

### Schema Evolution Compatibility
- **新增字段**: 自动透传至 Silver/Gold，不阻断管道，仅在元数据中标记为 "new"
- **类型变更**: 触发 WARNING 日志 + Slack 告警，但保留原始值于 `_raw_<field>` 列，保障下游不中断
- **字段废弃**: 保留 90 天后在 Gold 层移除，Silver 层永久保留原始字段

## 5. 技术选型与权衡


| 组件     | 选择                                    | 理由                                                                                  |
| -------- | --------------------------------------- | ------------------------------------------------------------------------------------- |
| 语言     | Python 3.10+                            | 必选，生态丰富                                                                        |
| 数据处理 | Pandas（未来可迁移至 PySpark）          | 当前数据量预估 < 10GB，Pandas 轻量快速，单机可跑通；代码结构保持与 Spark 相似以便扩展 |
| 输入格式 | JSON（示例），支持扩展 CSV/Parquet      | 通过工厂模式适配不同源                                                                |
| 输出格式 | Parquet（列式存储，压缩比高，适合分析） | 兼顾性能和成本                                                                        |
| 配置管理 | YAML（环境区分）                        | 敏感信息通过环境变量注入                                                              |
| 测试     | pytest + 自定义数据质量检查             | 满足单元测试+数据测试要求                                                             |
| 编排     | Airflow（提供伪代码蓝图）               | 行业标准，支持依赖/重试/回填                                                          |
| CI/CD    | GitLab CI（提供 .gitlab-ci.yml 骨架）   | 题目要求示例                                                                          |

### Dimensional Modeling Strategy
Gold 层采用星型模型（Star Schema）支撑领域数据产品交付：

- **Fact Table**: `fact_daily_events`  
  粒度：每日每用户每事件类型；度量：event_count, total_amount, avg_amount
- **Dimension Tables**:  
  - `dim_customer`: user_id, first_seen_date, lifetime_value_segment  
  - `dim_event_type`: event_type, category, business_owner  
- **Wide Table (Denormalized View)**: `wide_daily_user_events`  
  预关联 Fact + Dimensions，供 BI 工具直接查询，减少运行时 Join 开销



## 6. 错误处理策略

- **Schema 不符**：隔离到 `errors/bad_schema/`，记录详细错误，继续处理其他记录（不阻塞全量）。
- **缺失文件**：快速失败（抛出异常），由编排层重试。
- **重复记录**：保留 `ingestion_timestamp` 最新的一条，其余记录到 `duplicates.log`。
- **迟到数据**：按 `event_timestamp` 分区存储，支持重处理。

## 7. 安全与成本控制

- **安全**：
  - 敏感字段（如 `customer_id`）可配置脱敏（掩码或哈希），在 Silver 层实施。
  - 凭证通过环境变量或密钥管理服务（如 Vault）注入，不入代码。
  - 审计日志记录每次运行的输入源、输出路径、处理行数。
- **成本**：
  - Silver 层按 `event_date` 分区，查询时可裁剪。
  - Gold 层使用聚合和宽表，减少下游计算消耗。
  - 设置存储生命周期（Bronze 保留 30 天，Silver 永久，Gold 按需）。
  - 单机 pandas 处理控制内存使用（分块读取大文件）。

## 8. 可观测性

- 日志结构化（JSON 格式），记录处理时间、行数、错误数。
- 输出统计指标（总行数、通过数、失败数、去重数）到 `metrics.json`。
- 未来集成 OpenLineage 实现血缘追踪。

## 9. 环境晋升与 CI/CD 适配

- 通过 `--env` 参数切换配置文件（`config/dev.yaml`, `test.yaml`, `prod.yaml`）。
- CI 流水线阶段：lint → 单元测试 → 数据质量测试 → 构建 → 部署到 dev，人工审批后晋升到 test/prod。
- 部署时仅更新代码和配置，数据存储路径按环境隔离（如 `s3://bucket/dev/silver/`）。


## 10. 未来扩展路径

- 从 Pandas 迁移到 PySpark 处理更大数据量。
- 引入 Great Expectations 或 dbt 进行数据契约验证。
- 采用 Apache Iceberg 支持表模式演进和时间旅行。
- 增加流式处理（如 Kafka + Spark Structured Streaming）。
