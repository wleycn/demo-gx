# CODING-STANDARD — 编码规范（Python）

> **级别**：🔴 红线（违反即阻断）｜🟡 强烈建议。示例 `✅ Correct` / `❌ Wrong`。

## 1. Python 语言规范

- 🔴 所有函数带 **type hints**；CI 跑 `mypy`（至少 strict 于新增模块）
- 🟡 统一 `ruff` lint + format，配置集中于 `pyproject.toml`（不散落 flake8/pylint 配置）
- 🔴 生产代码**禁止 `print`**，统一 `utils/log.get_logger`
- 🔴 **禁止裸 `except:`** 与 `except Exception: pass`（静默失败 = 排查盲区）
- 🔴 依赖必须进 `pyproject.toml` 并提交 lock 文件；禁止 ad-hoc `pip install`
- 🟡 优先标准库与既有收口文件，禁止为单点需求引入重依赖
- 🔴 注释与 docstring 与代码一起维护：解释「**为什么**」，不复述「是什么」（见 §13）

## 2. 配置与凭证

- 🔴 凭证 / endpoint / 路径经 `config.py` 从 env 或 secret manager 加载，**禁止明文出现在代码、notebook、调度参数中**
- 🔴 路径不得 `Path.home()` / `expanduser` / 直接 `import dotenv`——统一走 `path_anchor.py` / `load_shared_env()`（见 `path-ssot-governance`）
- 🟡 配置项全部有 typed 默认值与校验（Pydantic Settings），启动即暴露配置错误

## 3. 错误处理与重试

- 🔴 **统一闸**：非零退出 / 空输出 / 超时 / 异常 **四类**均须触发 fallback 或告警，不许只判非零退出
- 🔴 失败必须**留痕**（日志 + 状态文件/库表），禁止静默吞异常
- 🔴 重试走 `utils/retry.py`；**重试必须以幂等为前提**（否则重试 = 制造重复数据）
- 🟡 外部调用必须有超时；无超时的网络调用视为缺陷

```python
# ✅ Correct：显式分类 + 留痕 + 幂等
try:
    r = call_api(url, timeout=10)
    if r.status_code != 200:
        raise ApiError(f"http {r.status_code}")
except (ApiError, TimeoutError) as e:
    log.warning("call failed: %s", e)
    write_state("failed", reason=str(e))
    raise
```

```python
# ❌ Wrong：静默失败 + 无超时
try:
    r = call_api(url)
except Exception:
    pass
```

## 4. 日志与可观测

- 🔴 统一 `get_logger(__name__)`；禁止 print 与自建 handler
- 🟡 关键任务运行输出指标：`run_id` / 目标对象 / 行数 / 耗时；失败走统一告警通道
- 🟡 日志字段结构化，可被检索（便于按 session id / run_id grep 排障）

## 5. 外部 I/O 与批量操作

- 🔴 批量请求外部 API 前**先做限流探测**（见 skill `probe-rate-limit-before-bulk`），禁止直接打满
- 🔴 写外部系统后**回读校验**（写成功 ≠ 生效），声明式总数必须复核
- 🟡 大结果集流式处理，禁止无条件 `list(...)` 全量加载

## 6. 数值与金额

- 🔴 金额禁止 `float` 存储或计算；用 `Decimal`（DB 侧 `DECIMAL(18,2)`，元）
- 🔴 单位换算**只在一个边界做一次**，走统一收口函数；全链路其它位置禁止手写 `/100`
- 🔴 比率统一用小数表示（`0.1234` = 12.34%），不得与百分数混用；舍入方式（half-up / half-even）必须声明
- 🟡 高精度字段（单价/均值/分位数）精度要求写入契约文档

## 7. 安全与脱敏

- 🔴 PII（手机号 / 证件号 / 详细地址 / 银行卡）在对外层必须脱敏或哈希；明文只允许存在于原始层且配置访问控制
- 🔴 脱敏实现集中在 `utils/mask.py`，禁止手写正则散落各处
- 🔴 无敏感上下文泄露：代码 / 日志 / 提交中不得含生产数据样本、凭证（见 skill `secret-sprawl-audit`）

## 8. 测试

- 🔴 金额换算、去重/合并、边界过滤逻辑**必须有边界用例**（空集、重复键、跨边界、超限）
- 🟡 `tests/` 镜像 `src/`；fixture 小样本放 `tests/fixtures/`
- 🟡 测试隔离外部服务（DB / 向量库）用 env 注入独立资源名，禁止直连生产

## 9. AI 生成代码审计追踪 🔴

```markdown
- 每个由 AI 生成或修改的文件，文件头注释标注：
  # [AI-GENERATED] model=<model-name> date=<YYYY-MM-DD> reviewed_by=<human>
- commit message 含 `[AI]` 标记，便于审计追溯
- AI 生成的迁移/DDL 脚本必须由人类在 PR 中逐行 review 并 comment 确认
- 不得将 AI 生成的代码直接推送到 main；必须经 feature 分支 + PR 流程
```

## 10. 类型专项红线不在栈层重复

数据处理 / 智能体等**项目类型专有**红线一律住类型层，栈层不复述（否则 `python × 网站` 项目会继承数据平台规则）：

类型专有红线（数据处理：写入幂等 / 分区裁剪 / 表生命周期 / 数据质量；智能体：输出契约 / 工具边界 / 成本上限 / 评测）随项目类型装配进本文件，**不在栈层复述**。

## 11. Notebook 规范（`notebooks/`，如有）

> **notebook 是什么**：Jupyter 交互式文档（`.ipynb`）——代码、执行输出与说明文字混排，用于**探索与分析**，不进生产链路（不是源码、不被 import、不被调度调用）。
> **不适用可跳过**：项目没有 `notebooks/`（如纯服务 / 站点类项目）即跳过本节，**无需裁剪本文件**（跨形态内容：不适用即整体跳过）。

- 🔴 `notebooks/` 仅探索与分析；**禁止被生产代码 / 调度 / 服务引用**
- 🔴 notebook 内禁止明文凭证与明文 PII 输出（含已执行的输出单元格）
- 🟡 提交前清理 outputs；命名 `EXP-{YYYYMMDD}-{topic}.ipynb`

## 12. 服务层规范（`serving/`，如有）

> **不适用可跳过**：无服务层（`serving/`）的项目跳过本节（跨形态内容：本项目不适用即整体跳过）。

- 🟡 API 框架统一（Python 下为 FastAPI）；响应体统一 `{code, message, data, timestamp}`；分页 `page` 从 1 开始、`size` 默认 20，返回 `PageResult`(items/total/page/size)
- 🔴 服务侧查询必须走收口并带**过滤 / limit 约束**，**禁止无界查询**（全表扫描、无 limit 列表）
- 🔴 认证与角色校验复用统一中间件，禁止接口内手写校验

## 13. 注释与文档字符串（Python）

> **判据**：注释回答「**为什么**」——意图、约束、不显然的取舍、踩过的坑；代码本身回答「是什么」。复述实现 = 噪音。
> **时机**：写代码时**顺手**写，不是「回头补」；改造既有代码时**在同一 diff 内**改注释。

- 🔴 **公共接口必带 docstring**：模块 / 类 / 公共函数写 ① 一句话职责 ② 非显然的参数与返回值 ③ 异常语义 ④ 幂等性与副作用。私有函数按「非显然才写」处理。
- 🔴 **注释与代码一起修改**：一条改动里注释与实现一起改，**不得留下与实现不符的注释**。过期的注释比没有注释更危险，它会主动误导下一个人与下一个 agent。
- 🔴 **注释里禁止写会过期的事**：变更历史（「改成…」）、日期、版本号、「临时方案」承诺 → 归 `docs/changes/` / `CHANGELOG` / `KNOWN-ISSUE`；代码里只留**当前成立**的事实。
- 🔴 **禁止提交注释掉的代码**：直接删（追溯靠 git）；要说明「为什么删」写进变更条目。
- 🔴 **禁止裸 `TODO` / `FIXME`**：必须带可追踪锚点或条件（`# TODO(#issue-123): …` / `# FIXME: 待上游 2.x 修复`）——无锚点的待办等于遗忘。
- 🟡 **必须写**：① 为什么这么写（绕坑 / 平台差异 / 精度与舍入方式）；② 非显然的边界与魔法值来源；③ 与外部系统的约定（协议怪癖、字段单位）；④ 安全假设（哪些输入已净化、哪些没有）。
- 🟡 **不要写**：复述代码（`# i 加 1`）、装饰性横幅 / 分隔线、无信息的修改记录（`# 修改于 xx`）。
- 🟡 **AI 生成代码**：注释不得声称未经验证的事实（「已测试」「线程安全」「性能已优化」），除非同一次改动附上证据。

## 【层：data-processing】CODING-STANDARD — 编码规范（数据处理类项目）

> **通用纪律**（类型注解 / 禁 print / 统一闸 / 金额禁 float / 脱敏收口 / AI 生成标记）见 `../../python/CODING-STANDARD.md`，本文只列**本类型专有**红线。

### 1. 写入与幂等 🔴（本类型第一红线）

- 增量去重表必须 `MERGE INTO` 或**分区级 overwrite**；🔴 **禁止裸 append**（重跑即重复）
- 单表 / 单分区**单写者**；并发生产必须经编排串行化
- 分区覆盖模式（dynamic overwrite）在**会话收口处统一设置**，禁止脚本 ad-hoc 开关
- 提交冲突（乐观并发冲突）经 `utils/retry.py` 捕获重试，🔴 禁止静默跳过
- 🔴 破坏性操作（`DROP` / `DELETE` / 快照过期 / orphan 清理）必须有人类显式授权记录

```sql
-- ✅ Correct：按业务主键增量合并
MERGE INTO dwd_trade_order_di AS t
USING staging.trade_order_inc AS s
  ON t.order_id = s.order_id AND t.ds = s.ds
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;
```
```python
# ✅ Correct：分区级幂等重写          # ❌ Wrong：append，重跑即重复
df.writeTo("dwd.trade.order_di").overwritePartitions()
```

### 2. 分区与查询 🔴

- 🔴 大表必须分区（hidden partitioning：`days(ts)`、`bucket(n, id)`）；单分区数据量目标 1–50 GB；**禁止直接暴露原始列做分区字段**
- 🔴 分区表查询**必须带分区裁剪**条件，禁止全表扫描
- 🔴 禁止 `collect()` / `toPandas()` / `toArrow()` 把大表全量拉到驱动端；抽样必须带 `limit` 并注释用途
- 🟡 生产管道禁止 `SELECT *`；对外输出必须显式列清单
- 🟡 join 策略（维表 broadcast 阈值）在会话收口处统一；禁止对大表手工加 broadcast hint
- 🟡 优先内置函数；Python UDF 仅在必要时使用并注释性能影响（推荐 pandas UDF）

### 3. 表设计与生命周期 🔴

- 🔴 无原生唯一约束：业务主键与**去重方式**（MERGE / row_number）必须写入表契约并代码落地
- 🔴 每表必须配置**快照保留期与压缩策略**（维护任务接入），禁止无限保留
- 🟡 表属性（文件大小目标等）在迁移中统一设置，禁止脚本 ad-hoc 修改
- 🟡 软删除与审计：源层保留 `is_deleted`；明细层提供有效数据过滤方式；历史审计走快照回溯

### 4. 数据质量 🔴

- 🔴 `dwd` / `dws` 表写入后必须接入质量校验：**主键唯一、关键字段非空率、行数环比波动、分区新鲜度**
- 统一入口 `utils/quality.check_table(df, rules)`；🔴 校验失败**阻断下游任务**
- 🟡 阈值与规则清单写入**表契约**（不在代码里硬编码），变更走 PR

```yaml
# 在表契约中声明，而非硬编码在代码中
quality_rules:
  primary_key_unique: [order_id, ds]
  not_null: [pay_amount, user_id]
  row_count: { drift_warn: 0.30, drift_fail: 0.50, min_rows: 1000 }
  freshness: { max_lag_minutes: 120 }
  enum_check: { status: [paid, shipped, delivered, cancelled] }
```

### 5. 金额与数值（收窄本类型要求）🔴

- 🔴 金额禁止 `float`/`double`；DB 侧 `DECIMAL(18,2)`（元），高精度字段 `DECIMAL(24,6)` 且须在契约声明
- 🔴 分→元转换**只在接入层边界做一次**（走 `utils/money.cents_to_yuan`），全链路其它位置禁止手写 `/100`
- 🔴 聚合直接在 DECIMAL 上运算，禁止中途转 float；比率统一用小数表示（`0.1234` = 12.34%），不得与百分数混用
- 🔴 所有 DECIMAL 字段必须**显式 cast**，禁止依赖自动推断；舍入方式（half-up / half-even）在契约声明

### 6. Schema 与类型 🔴

- 🔴 读写 schema 集中在 `models/`，命名与表契约对齐
- 🔴 schema evolution **只走迁移**；禁止写入时隐式改 schema（自动加列 / merge schema）
- 🟡 时间字段统一 `timestamp`（UTC）或日期分区 `ds` 字符串，在契约声明

### 7. 数据安全 🔴

- 🔴 PII（手机号、证件号、详细地址、银行卡）必须在**明细层脱敏或哈希**；明文仅允许存在于接入层且配置访问控制
- 🔴 脱敏实现集中在 `utils/mask.py`，禁止手写正则散落各处
- 🔴 对外表与数据服务响应不得包含明文 PII
- 🟡 列级权限在 catalog / 权限系统统一声明

### 8. 编排 🔴

- 🔴 编排文件只做编排（import pipeline 函数、组装依赖与调度参数），**禁止写转换逻辑**
- 🔴 任务函数签名统一 `run(ds: str, ...)`，分区由调度注入，**禁止隐式使用系统当前时间**（否则重跑不可复现）
- 🟡 task 级重试配在编排层；业务级重试走 `utils/retry.py`；重试必须以幂等写入为前提
- 🟡 每次运行经 `utils/log` 输出指标：`run_id`、表、分区清单、读写行数、耗时
