# AGENTS.md — AI 编码约束（数据处理类项目模板）

> 规则分两级。🔴 红线：AI 不得生成违反它的代码，评审直接打回。🟡 建议：偏离时要在回报或 `CHANGELOG` 里说明理由。
> 在本仓库工作的 AI 编码工具和 agent 运行时，都受本文件约束。
> 这包括 Hermes Agent 自己，以及它派出的 coder profile、委托子代理和 cron 任务。
> Claude Code、Codex、Cursor 及其它 CLI / IDE 助手同样适用。
> 判断标准只有一条：**以本仓库为 cwd 即受约束**。没被上面点名的工具，不因此不受约束。Hermes 侧的生效路径见 §8。

## 0. 规范优先级

本文件效力最高。往下依次是 `docs/rules/` 四件套、`docs/business/` 九文档、既有代码风格、通用业界实践。几层冲突时取效力高的那层。

发现既有代码与高层规则冲突时，**不得默然跟随既有代码**。要在变更记录里指出冲突。

## 1. 技术栈

- **语言与运行环境**：Python 3.11（最低 3.10）。虚拟环境在项目内 `.venv/`，不进版本库，命令一律以 `.venv/bin/python` 开头
- **存储引擎**：本地文件系统，无数据库。三层数据落 `data/`，测试环境落 `test/data/`，由配置项 `storage.base_path` 隔离
- **编排**：`src/demo_gx/cli.py`，以 `python -m demo_gx.cli` 调用，无调度器。分区参数由 `--event-date` 注入，运行时间戳由 `--run-timestamp` 注入；入口只在未注入时读一次系统时间
- **表格式**：Parquet 分区目录 `event_date=YYYY-MM-DD`，无 Iceberg，无 catalog
- **依赖与工具链**：`pyproject.toml`（依赖与工具链唯一入口）、`Makefile`、`.gitlab-ci.yml`
- **目标形态**：设计面向 Spark 加 Iceberg 的大数据形态，本地以 Pandas 单机验证。技术选型与被否方案见 `docs/business/PROJECT.md`

## 2. 上下文加载（动手前必做）

按顺序读完再动手：

1. 读本文 §3 红线清单
2. 读 `docs/rules/PROJECT-STRUCTURE.md` 的「目录职责」与「收口点」
3. 读 `docs/rules/CODING-STANDARD.md` 的本类型红线
4. 涉及数据变更 → 读对应 `docs/tables/{table}.md` 表契约
5. **合计不超过 3 个规则文件**（防上下文过载）

## 3. 红线清单

> AI 不得输出违反以下内容的代码；违反即阻断，不接受「先合入后续再改」。

1. 🔴 **写入必须幂等**（MERGE 或分区级 overwrite），**禁止裸 append**
2. 🔴 **查询必须带分区裁剪**。禁止全表扫描，禁止把全量数据拉到驱动端
3. 🔴 **金额禁止用 `float`**。单位换算只在接入边界做一次
4. 🔴 **PII 在明细层必须脱敏**。禁止明文外泄到日志或对外表
5. 🔴 **凭证、endpoint、路径不得硬编码**，统一走配置收口
6. 🔴 **计算与 catalog 走收口文件**。禁止散建会话实例
7. 🔴 **破坏性操作必须有人类显式授权**，包括 DROP、DELETE、snapshots expire
8. 🔴 **schema evolution 只走迁移**。禁止隐式加列
9. 🔴 **每张表必须有快照保留与压缩策略**。禁止无限保留
10. 🔴 **分区参数由调度注入**。禁止代码读系统当前时间

## 4. Agent 行为准则

- **不做「顺手改进」**：只改授权范围内的文件。发现相邻问题另行提出，不代改。
- **失败必留痕**：异常要记日志。禁止捕获后空处理。
- **不确定就停**：想不清接口形状、目录结构、改动该落在哪个文件时，先提问。
- **不擅自执行破坏性操作**：DROP、DELETE、批量覆盖、快照过期，一律先问。
- 🔴 不得直接向 `main` 推送。必须走 feature 分支，再提交 MR。

## 5. 输出要求

- 只给代码或明确的 diff，不夹带无关说明
- 在改动文件头部加 `[AI-GENERATED] model=<m> date=<d> reviewed_by=<human>` 注释。commit message 含 `[AI]`。
- 单次变更不超过文件总量的 **40%**。超出就拆成多次，逐步验证。
- 注释与 docstring 要和代码在同一个提交里改。不许留下与实现不符的注释。注释解释「**为什么**」，不复述「是什么」。细则见 `docs/rules/CODING-STANDARD.md` 的注释一节。
- 写文档、写回报、写交付说明之前，先载入技能 `docs-writing-discipline`，按其检查表通读一遍再交
- 迁移脚本必须由人类逐行 review 并在 PR 中 comment 确认

## 6. 变更留痕

功能或契约变更，在 `docs/changes/{module}.md` **追加**一条目。条目 slug 与分支名同名，七项模板见 `docs/rules/DEVELOP-FLOW.md` §4。`{module}` 取 `src/demo_gx/` 顶层模块目录名，即 `ingestion`、`validation`、`transformation`、`curation`、`common`；非功能变更落 `engineering.md`。该目录**只放条目文件**，不放 README、说明或附件。模块清单见 §9.1 项目地图。

- 上线后追加部署记录。

## 7. 不确定行为

- 规范没覆盖但改动可以安全回退时，照本仓库最相近的类比规则执行，并在变更记录里说明类比的是哪一条。
- 下面四类必须向人类确认，不得自决：金额怎么算、去重怎么做、回刷范围、破坏性操作。
- 不许自行引入新的第三方依赖。要引入就写进依赖清单，并走评审。
- 规范没覆盖或互相冲突时：**停止 → 提问 → 等确认**。不许自行放宽红线，也不许「先合入，之后再改」。

## 8. 本文件如何被读取（生效路径）

- 生效方式：工具按 **cwd → git 根** 的目录链在**会话启动**时注入本文件。它不是「放进项目就自动生效」。
- 会话、委托、测试 harness 都必须**以项目根为 cwd 启动**。从项目外启动只会晚一步懒加载，在那之前动作等于没有约束。
- **三种情况本文件不生效**：非 git 项目从子目录启动、`delegate_task` 子代理、未设 `workdir` 的 cron 任务。
- **Hermes 侧保证**：Hermes 及其委托链路一律**以项目根为 cwd 启动**。委托链路包括 coder profile、`delegate_task` 子代理和 cron 任务。委托任务书必须写明 `cwd=/home/hermes/workspace/demo-gx`。**不得假设执行者已读过本文件**，拿不准时把 §3 红线**内联**进任务书。
- 红线要**可执行化**：能写成 lint、检查脚本或 CI check，就不要指望「模型会读到」。

## 9. 地图（去哪找什么 · 用什么技能）

两张地图缺一不可。9.1 回答「东西在哪」，9.2 回答「这个阶段该用哪个技能」。

### 9.1 项目地图（文件索引）

> 生成规则：把**项目里真实存在**的文件填进下表，删掉不适用的行。表内路径必须真实可访问，`pre_commit_gate.py` 会检查。

| 类别 | 位置 | 用途 |
|---|---|---|
| 人类入口 | `README.md` | 这是什么 / 怎么上手（5 秒测试） |
| AI 约束 | `AGENTS.md`（本文） | 红线与行为准则，优先级最高 |
| 规范 | `docs/rules/` | 四件套：结构 / 编码 / 流程 / 验收 |
| 业务文档 | `docs/business/` | 项目说明 / 模块 / 数据 / 接口 / 术语 / 变更 / 已知问题 |
| 接口契约 | `docs/business/INTERFACE-DESIGN.md` | CLI 参数、产物路径、错误封套，唯一真源 |
| 数据契约 | `docs/business/DATA-DESIGN.md` | 分层数据流、表结构、分区与重跑语义 |
| 表契约 | `docs/tables/{table}.md` | 一表一档：粒度 / 主键 / 去重方式 / 生命周期 |
| 字段契约源 | `config/schema.yaml` | 字段类型 / 必填 / 枚举 / 正则表达式 |
| 环境配置 | `config/dev.yaml`、`config/test.yaml`、`config/prod.yaml` | 存储路径 / 日志 / 指标 / 告警 |
| 产品代码 | `src/demo_gx/` | 可安装包；入口 `cli.py`，模块 `common` / `ingestion` / `validation` / `transformation` / `curation` |
| 依赖与工具链 | `pyproject.toml` | 依赖声明、打包与 pytest 配置的唯一入口 |
| 样例数据生成 | `scripts/generate_sample_data.py` | 生成 `data/sample_data.json`，不含业务逻辑 |
| 运行产物 | `data/` | Bronze / Silver / Gold / errors，可重建，勿手改 |
| 变更留痕 | `docs/changes/{module}.md` | 每模块一份，追加式变更条目 |
| 门禁 | `.git/hooks/pre-commit` | 调用 `ng/tools/pre_commit_gate.py` |

### 9.2 技能地图（阶段 → 技能）

> 阶段定义见 `docs/rules/DEVELOP-FLOW.md` §1（十阶段）与 §1.1（阶段 4 子步骤）。下表只接**技能库里真实存在**的技能，名字必须可查，`pre_commit_gate.py` 会检查。
> 用法：进入某阶段前先载入该阶段技能（`skill_view`），按它的 Phase 或 Step 执行。禁用「通用做法」替代技能流程。

| 阶段 | 技能 | 什么时候用 |
|---|---|---|
| 1 需求分析 | `requirement-analysis`；存量改造先 `legacy-recon`；可行性未知 → `feasibility-probe` | 诉求模糊 / 接手陌生仓库 / 方案 A·B 选型 |
| 2 方案设计 | `system-architecture`（架构与 ADR）、`project-doc-system`（文档体系）、`api-contract-design`、`data-layer-design`、`identity-access-design`、`secrets-management`、`threat-modeling`、`ui-foundation-design` | 立架构 / 定文档 / 改契约 |
| 3 任务拆分 | 无专用技能：按 `coding-flow` 七步执行序拆；委托子代理用 `coder-profile-delegation` | 拆到「能独立验证」的粒度 |
| 4 编码实现 | `coding-flow`（流程）、`minimal-diff`（改哪几行）、`engineering-naming-discipline`（命名）；MCP / 工具服务 → `mcp-server-development` | 每次动代码前必载 |
| 4a–4d 编码子步骤 | 同上；4b 接口实现另载 `api-contract-design`；4d 接线自测另载 `http-e2e-testing` | 4a→4b→4c→4d 逐步推进，**不得并行大改** |
| 5 单元测试 | `tdd-discipline`（RED-GREEN-REFACTOR）；卡住 → `python-debugging` / `node-debugging` | 写生产代码前先有失败测试 |
| 6 代码评审 | `pre-commit-gate`（提交闸）、`independent-review`（第三方判定）、`ai-code-audit`（AI 生成代码安全） | 每次提交 / 交付前 |
| 7 集成测试 | `verify-data-layer`（数据层交接独立验证）、`performance-benchmarking`（数据量级基线） | 改数据链路或分区布局时 |
| 8 预发验证 | 本项目**无界面、无预发环境**，界面走查与可访问性审计不适用；端到端验证走 `make run` 加 CI 的 data-quality 阶段 | 产物或分区布局变更时 |
| 9 上线部署 | `ci-cd-delivery`；提交纪律 `git-submit` | 有流水线 / 多环境时 |
| 10 线上观测 | `observability-sre`（SLO / 告警）、`incident-postmortem`（故障复盘）、`performance-benchmarking` | 有生产环境时 |
| 横切（任意阶段） | `doc-code-drift`（契约与代码漂移）、`post-change-cleanup`（改后清理）、`module-retirement`（下线旧模块）、`docs-writing-discipline`（写文档与回报前）；日常纪律 `ops-basics-discipline` / `path-ssot-governance` / `secret-sprawl-audit` | 阶段完成 / 交付前 / 发现漂移时 |
| 任意阶段（本类型专属） | `data-layer-design`（schema 与查询计划）；`verify-data-layer`（数据层交接独立验证）；`pg-query`；`performance-benchmarking` | 涉及表 / 分区 / 数据链路时 |
| 本项目例外 | 本地参考实现：无预发环境、无生产部署、除 CI 外无发布链路。阶段 8 的界面类技能与阶段 9 的发布动作不适用 | 见 §10「阶段模型适用边界」 |

## 10. 规则来源与偏离

- **来源**：本项目规则 = 本文 + `docs/rules/` 四件套。四件套由装配工具按 **基线 → 技术栈 → 项目类型** 三层逐字拼装（`rules_assembly.py`）。装配只降标题级别，不改上层文字，也不删上层条目。**不逐项目手工改**。
- **偏离登记**：本项目与上游规范不一致的地方逐条写在本节，四列分别是议题 / 上游写法 / 本项目做法 / 处置。「处置」必须指向真实存在的文档锚点，禁止只写「已说明」。
- 尚未消解的偏离视为**已知问题**，登记进 `docs/business/KNOWN-ISSUE.md`，并在此处留索引行。
- **偏离纪律**：标准做法是**默认值**，偏离是例外。允许偏离，但要同时满足三条：
  - ① 在本节逐条登记，「处置」一列指向真实存在的锚点。
  - ② 说明**为什么不采用标准做法**，禁止「本项目特殊」这类空理由。
  - ③ 标注代价与回退成本。
**本项目偏离登记**（与上游规范不一致处，逐条登记）：

| 议题 | 上游写法 | 本项目 | 处置 |
|---|---|---|---|
| 建环境 | 提交 `uv.lock` 锁文件 | `pyproject.toml` 声明依赖，venv 加 pip 安装，无锁文件 | 见 `docs/business/PROJECT.md` |
| 编排目录 | `dags/` 放任务编排与依赖组装 | 无调度器；编排兼在包内入口 `src/demo_gx/cli.py` | 见下「数据处理骨架适用边界」 |
| 转换模块划分 | `src/{pkg}/pipelines/{domain}/`，按业务域 | 按管道阶段分模块：`ingestion` / `validation` / `transformation` / `curation` | 见下「数据处理骨架适用边界」 |
| 契约模型层 | `src/{pkg}/models/` 放 schema 与类型定义 | 字段契约在 `config/schema.yaml`，表契约在 `docs/tables/`；无 Python 模型层 | 见下「数据处理骨架适用边界」 |
| SQL 资产 | `sql/migrations/` 增量 DDL 与 `sql/transforms/` | 无 `sql/` 资产，无 SQL 引擎；Parquet 直接落盘。Iceberg DDL 只作归档参考，不进执行路径 | 见下「数据处理骨架适用边界」 |
| 测试目录 | `tests/` 与 `src/` 镜像 | 平铺 `tests/test_{module}.py` | 见下「数据处理骨架适用边界」 |
| 数据分层命名 | `ods` → `dwd` → `dws` → `ads` | Bronze → Silver → Gold | 见 `docs/business/DOMAIN-LANGUAGE.md` 术语 `data layer mapping` |
| 覆盖率门禁 | 有 CI 的项目单测覆盖率 ≥ 80% | 未启用覆盖率工具；底线为「每需求至少一条断言」 | 见 `docs/business/KNOWN-ISSUE.md#coverage-gate-off` |
| 计算与 catalog 收口 | 由 `catalog.py` 统一会话与表加载 | 无 catalog：本地 Parquet，不存在会话概念 | 见 `docs/business/KNOWN-ISSUE.md#no-catalog` |
| 快照与压缩策略 | 每张表配置保留期与压缩任务 | 分区目录直接覆盖写，无快照层 | 见 `docs/business/KNOWN-ISSUE.md#no-snapshot-lifecycle` |
| 金额精度 | 金额禁用 `float`，走 DECIMAL 与统一换算 | `amount` 列为 pandas `float64` | 见 `docs/business/KNOWN-ISSUE.md#amount-float` |
| 表契约审批 | 契约 frontmatter 记 `status: approved`，CI 拦截未审迁移 | 本地参考实现，无审批链路 | 见 `docs/business/KNOWN-ISSUE.md#table-contract-approval` |
| 阶段模型 | 基线十阶段（含预发 / 部署 / 观测） | 阶段 8 以端到端 smoke 代替，阶段 9 与 10 不适用 | 见下「阶段模型适用边界」 |

**阶段模型适用边界**：本项目是本地参考实现，没有预发环境、没有生产部署、没有 CI 之外的发布链路。基线十阶段中阶段 1–7 全量适用；阶段 8 以端到端 smoke 代替，界面类检查不适用；阶段 9 与阶段 10 不适用。CI 门禁与提交纪律仍然适用。

**数据处理骨架适用边界**：数据处理类型的结构骨架假定 Spark 加 Iceberg 加调度器的技术栈。本项目是 Pandas 单机参考实现（选型与被否方案见 `docs/business/PROJECT.md`），骨架中依赖该栈的条目经登记后不适用：

- **不设 `dags/`**：没有调度器，编排兼在包内入口，`python -m demo_gx.cli` 就是调用方式。骨架的「入口可合并」边界要求三条全满足，本项目**只满足第一条**：入口写死了 `--env` 的三个取值与默认值，不满足第二条；`reader` / `validator` / `cleaner` / `builder` 是被 `tests/` 当库 import 的，第三条也存疑。本项目仍选择合并，理由是只有这一个入口、也没有第二个调用方；代价是入口带命令行副作用，将来拆分要把参数解析与库代码分开。
- **转换模块按管道阶段划分**：项目只有 events 一个业务域，按域分会得到单元素目录；阶段边界才是真实的可复用边界。`common/` 是跨阶段共享层，不在骨架的列举里但符合 `utils/` 的定位。
- **不设 `src/demo_gx/models/`**：字段契约的唯一真源是 `config/schema.yaml`，表契约在 `docs/tables/`。另设 Python 模型层会产生第二份定义。
- **不设 `sql/`**：没有 SQL 引擎，schema 变更靠 `schema.yaml` 与表契约同步。仓库里存在 Iceberg DDL，但只在 `docs/archive/` 作生产形态参考，不进执行路径。
- **测试平铺不镜像 `src/`**：单文件单模块，镜像会为 4 个测试文件各加一层目录。命名不严格同源模块：`test_validation.py` 对应的是 `validation/schema_validator.py`。
- **分层沿用 Bronze / Silver / Gold**：与上游 `ods` / `dwd` / `dws` / `ads` 的对应关系记在 `docs/business/DOMAIN-LANGUAGE.md` 的术语 `data layer mapping`。

**未被单测直接覆盖的模块**：`ingestion/reader.py`、`validation/error_envelope.py`、`common/*` 与 `cli.py` 目前只有端到端 smoke 覆盖，没有直接单测。这是 `#coverage-gate-off` 的具体表现。

代价与回退：迁到 Spark 加 Iceberg 时，前四条需要重建目录并在其中重新落位逻辑；后两条是命名与组织差异，回退成本为零。

- **禁止无登记地默默降标准**。「这只是个例」不是免于登记的理由。
- **表格里的竖线要转义**：单元格中写 `a|b` 这类含竖线的内容时，写成 `a\|b`，否则 Markdown 会把这一格切坏。
- **本文件结构固定**：共 §0–§10 十一节，**不得新增节**。项目级补充写在对应节。红线写进 §3，行为准则写进 §4，输出要求写进 §5。地图写进 §9.1 / §9.2，与上游不一致写进本节偏离表。自加节会与既有节各自漂移，机器门禁会告警。尤其不要再加一张与 §3 重复的「反模式」对照表。
