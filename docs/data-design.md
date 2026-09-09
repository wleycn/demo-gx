# 数据流与数据结构设计

## 1. 物理数据路径（存储布局）

采用 **按环境隔离** 的目录结构。本地开发以 `./data` 为根目录，生产环境可映射至 S3/ADLS（通过配置切换）。
data/
├── bronze/ # 原始 JSON 存档（不可变）
│ └── {source_system}/ # 按源系统分目录
│ └── dt={YYYY-MM-DD}/ # 按摄入日期分区
│ └── events.json
├── silver/ # 清洗后的明细层（Parquet）
│ └── event_date={YYYY-MM-DD}/ # 按事件日期分区
│ └── data.parquet
├── gold/ # 聚合/维度层（Parquet）
│ ├── fact_daily_events/
│ │ └── event_date={YYYY-MM-DD}/
│ │ └── data.parquet
│ ├── dim_customer/
│ │ └── data.parquet （全量快照，非分区）
│ ├── dim_event_type/
│ │ └── data.parquet
│ └── wide_daily_user_events/
│ └── event_date={YYYY-MM-DD}/
│ └── data.parquet
└── errors/ # 异常数据隔离区
├── bad_schema/ # 字段缺失/额外字段/格式错误
│ └── {timestamp}_errors.json
├── type_mismatch/ # 类型转换失败（含 _raw 列）
│ └── {timestamp}_errors.json
└── duplicates.log # 去重记录日志（纯文本，追加）


---

## 2. 详细数据流（含异常分支）

下图展示从输入到输出的完整路径，以及坏数据和特殊情况的处理流向。
┌─────────────┐
│ 输入文件 │
│ (JSON/CSV/ │
│ Parquet) │
└──────┬──────┘
│ ingestion.read()
▼
┌─────────────────────┐
│ 附加 raw_json 列 │ ← 保留原始行用于审计
└──────────┬──────────┘
│
▼
┌─────────────────────────────────┐
│ validation.validate_schema() │ ← 严格校验 8 个必填字段，拒绝额外字段
└──────────┬──────────┬───────────┘
│ │
校验成功│ │校验失败
│ ▼
│ ┌─────────────────────┐
│ │ 写入 errors/bad_schema/ │
│ │ + 发送告警（可选） │
│ └─────────────────────┘
▼
┌─────────────────────────────────┐
│ transformation.clean() │ ← 时间戳 UTC 标准化、货币归一化
│ 生成 raw* 列（若类型转换失败） │ ← 标记 validation_status
└──────────┬──────────────────────┘
│
▼
┌─────────────────────────────────┐
│ transformation.deduplicate() │ ← 按 event_id 去重，保留最新 ingestion_timestamp
│ 重复记录写入 duplicates.log │
└──────────┬──────────────────────┘
│
▼
┌─────────────────────────────────┐
│ 写入 Silver (Parquet) │ ← 按 event_date 分区，覆盖写入
└──────────┬──────────────────────┘
│
├─────────────┬─────────────┐
▼ ▼ ▼
┌─────────────────┐ ┌──────────────┐ ┌──────────────────┐
│ curation. │ │ curation. │ │ curation. │
│ build_fact_table│ │ build_dims │ │ build_wide_table │
└────────┬────────┘ └──────┬───────┘ └────────┬─────────┘
│ │ │
▼ ▼ ▼
┌─────────────────┐ ┌──────────────┐ ┌──────────────────┐
│ fact_daily │ │ dim_customer │ │ wide_daily_user │
│ events │ │ dim_event_ │ │ events │
│ (分区表) │ │ type │ │ (分区表) │
└─────────────────┘ └──────────────┘ └──────────────────┘


**关键分支说明**：

- **坏数据流（红色路径）**：在 `validation` 阶段，若记录缺少必填字段、类型不符或包含额外字段，则被隔离至 `errors/bad_schema/`，并附带 `error_reason` 列。管道**继续处理**其余有效数据，不中断。
- **类型变更流（黄色路径）**：在 `clean` 阶段，若 `amount` 等数值字段无法转换为数字，则保留原始值于 `_raw_amount` 列，并标记 `_validation_status = 'type_mismatch'`。此类记录仍进入 Silver，同时触发日志告警。
- **去重流**：重复的 `event_id` 仅保留 `ingestion_timestamp` 最新的一条，其余写入 `duplicates.log`（含原始值和重复时间），用于事后核查。

---

## 3. 数据结构定义（精确 Schema）

### 3.1 Silver 层（Cleaned Parquet Schema）

**分区键**：`event_date`（从 `event_timestamp` 提取的日期，类型为 `date`）

| 字段名 | 类型 | 描述 | 约束/说明 |
| :--- | :--- | :--- | :--- |
| `event_id` | `string` | 事件唯一 ID | 非空，UUID v4 格式 |
| `source_system` | `string` | 来源系统 | 枚举值：`web` / `mobile` / `api` |
| `customer_id` | `string` | 客户 ID | 非空；生产环境可按策略进行哈希脱敏 |
| `event_type` | `string` | 事件类型 | 非空，长度 ≤ 64 |
| `event_timestamp` | `timestamp(us, UTC)` | 事件发生时间 | 精确到微秒，UTC 时区 |
| `amount` | `double` | 金额 | ≥ 0，保留原始数值；若转换失败为 `NaN` |
| `currency` | `string` | 货币代码 | ISO 4217 三字母码；非法值已修正为 `USD` |
| `ingestion_timestamp` | `timestamp(us, UTC)` | 摄入时间（来自源系统或处理时） | 必须 ≤ 当前时间 |
| `event_date` | `date` | **分区列** | 从 `event_timestamp` 推导 |
| `_raw_amount` | `string` | （可选）原始金额字符串 | 仅在金额类型转换失败时填充 |
| `_is_invalid_currency` | `boolean` | 货币是否被修正 | `true` 表示原始值非法，已改为 `USD` |
| `_validation_status` | `string` | 校验状态 | `'passed'` 或 `'type_mismatch'` |
| `_processed_timestamp` | `timestamp(us, UTC)` | 管道处理时间 | 写入时自动添加 |

---

### 3.2 Gold 层结构（星型模型）

#### 事实表：`fact_daily_events`
| 字段名 | 类型 | 描述 |
| :--- | :--- | :--- |
| `event_date` | `date` | 分区列 |
| `customer_id` | `string` | 关联维度表 `dim_customer` |
| `event_type` | `string` | 关联维度表 `dim_event_type` |
| `event_count` | `bigint` | 该分组下的事件总数 |
| `total_amount` | `double` | 该分组下的总金额 |
| `avg_amount` | `double` | 该分组下的平均金额 |

#### 维度表：`dim_customer`
| 字段名 | 类型 | 描述 |
| :--- | :--- | :--- |
| `customer_id` | `string` | 主键，唯一 |
| `first_seen_date` | `date` | （预留）首次出现日期，当前设为 `event_date` 的最小值 |

#### 维度表：`dim_event_type`
| 字段名 | 类型 | 描述 |
| :--- | :--- | :--- |
| `event_type` | `string` | 主键，唯一 |
| `category` | `string` | （预留）业务分类，当前置空 |

#### 宽表（非规范化）：`wide_daily_user_events`
将 `fact_daily_events` 左连接 `dim_customer` 和 `dim_event_type`，包含所有事实和维度字段，直接供 BI 工具查询，避免运行时 Join。

---

### 3.3 错误记录 Schema（`errors/` 目录）

每个错误文件采用 **JSON Lines** 格式，每行一个错误对象，包含以下字段：

| 字段名 | 类型 | 描述 |
| :--- | :--- | :--- |
| `original_json` | `string` | 原始输入行的完整 JSON 字符串 |
| `error_type` | `string` | 错误类型：`schema_mismatch` / `type_coercion_failed` |
| `error_details` | `string` | 具体原因，如 `"field 'event_id' missing"` 或 `"amount cannot be parsed as number"` |
| `ingestion_timestamp` | `string` (ISO8601) | 管道处理该记录的时间 |

---

## 4. 数据新鲜度与重处理机制

- **批处理窗口**：管道设计为每日运行一次，默认处理前一日（UTC）`event_timestamp` 的数据。可通过命令行参数 `--event-date YYYY-MM-DD` 指定处理任意历史日期，实现灵活回填。
- **幂等性保证**：Silver 和 Gold 层的写入均采用 **按分区覆盖** 模式（`mode='overwrite'`）。重复运行同一日期的任务会完全覆盖该分区，保证结果一致，不会产生重复数据。
- **迟到数据策略**：若记录的 `event_timestamp` 属于过去日期（如晚到 3 天的数据），管道会将其写入对应历史分区，不会丢弃。此行为依赖于分区覆盖机制，且 Bronze 层保留原始 JSON，可随时重放。
- **安全回填**：通过指定 `--event-date`，可以只重处理特定日期的数据，不影响其他分区的数据，实现精准修复。

---

## 5. 血缘与可观测性（设计要点）

- **血缘追踪**：每条记录从 Bronze（原始 JSON）到 Silver（Parquet）再到 Gold（聚合表）的路径，通过 `_processed_timestamp` 和分区键可追溯。未来可集成 OpenLineage 获取更细粒度的字段级血缘。
- **运行指标**：每次运行结束时，在 `logs/metrics_{timestamp}.json` 中输出总输入行数、校验通过数、校验失败数、去重删除数、各阶段耗时，用于监控和 SLA 评估。
- **数据新鲜度监控**：在编排层（如 Airflow）中，可设置传感器（Sensor）检查最新 Silver 分区的 `event_date` 是否与当前日期一致，若延迟超过阈值则触发告警。

---