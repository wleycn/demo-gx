# PROJECT-STRUCTURE — 工程结构规范（Python）

## 1. 目录结构（通用骨架）

```text
{project}/
├── README.md                 # 人类入口（必留根）
├── AGENTS.md                 # AI 编码约束（项目根唯一名）
├── pyproject.toml            # 依赖与工具链（ruff/mypy/pytest）唯一入口
├── uv.lock                   # 依赖锁，随库提交 🔴（无 uv 时用 requirements.txt 等效锁定，见 §3）
├── src/{pkg}/                # 产品代码（可安装包，不是平铺脚本）
│   ├── __init__.py
│   ├── config.py             # 🔴 收口：env / secret 加载，typed config
│   ├── <domain>/             # 按业务模块划分
│   └── utils/                # 跨模块通用能力收口
├── scripts/                  # 入口脚本与薄壳（只转发，不含业务逻辑）
├── tests/                    # 测试，与 src 结构镜像
│   └── fixtures/
└── docs/
    ├── rules/                # 本四件套
    ├── business/             # 九文档
    └── changes/              # 变更留痕（每模块一份，追加式）
```

## 2. 目录职责与禁止事项

| 目录 | 职责 | 禁止 |
|---|---|---|
| `src/{pkg}/` | 产品代码 | 硬编码配置；直接散读 `os.environ` |
| `scripts/` | 入口 / 薄壳（cron 壳只 subprocess 转发） | **承载业务逻辑**（真身必须唯一） |

> **`src/` 与 `scripts/` 为什么不合并**：两者被调用的方式不同——`src/` 是被 `import` 的库代码（可能被安装、被打包、被多处复用），`scripts/` 是被 shell / cron / 调度器**当成命令调用**的入口（含 `if __name__ == "__main__"` 与参数解析）。分开的收益：① 库代码不因入口而携带命令行副作用；② 调度壳改参数不影响库；③ 权限与路径假设不同（壳可以有 env / argv 依赖，库不允许）。
> **允许合并的边界**（满足全部三条才可以只留 `src/`）：① 只有 1–2 个入口；② 入口不含调度器专属假设（硬编码绝对路径、固定 env 名）；③ 没有会被 shell 之外复用的库代码。任一条不满足 → 分开。合并后用 `python -m {pkg}.cli` 作为入口，仍不写脚本文件。
| `tests/` | 测试 | 放生产代码；用 `Path.cwd()` 定位项目根（应用 `Path(__file__).parent.parent`） |
| `notebooks/` | 探索与分析 | 被生产调度引用；提交输出与明文凭证 |
| `docs/` | 规范与业务文档 | 与代码漂移（改代码必同步） |
| `docs/changes/` | 变更留痕（每模块一份，追加式） | 写非变更内容（说明、附件、临时文件） |

## 3. 收口文件（单一入口原则）

| 收口点 | 文件 | 职责 |
|---|---|---|
| 配置与凭证 | `config.py` | env / secret 加载，typed 输出（Pydantic Settings），带校验 |
| 路径 | `path_anchor.py` / `path_resolve.py` | **禁** `Path.home()` / `expanduser` / 直接 `import dotenv`；统一 `load_shared_env()` |
| 路径（项目根） | `Path(__file__).resolve().parents[k]` | 项目一律从 `__file__` 推导，**不依赖外部共享库**（共享 `path_anchor` 只适用于托管在统一基础设施目录下的系统脚本） |
| 日志 | `utils/log.py` | `get_logger(__name__)`，含 run_id / 目标 / 行数 / 耗时 |
| 重试 | `utils/retry.py` | 统一重试与冲突处理；**统一闸**：非零退出/空输出/超时/异常四类均触发 |
| 数据访问 | `utils/db.py` | 统一连接与查询入口（PG 操作见 skill `pg-query`） |
| 脱敏 | `utils/mask.py` | 手机号 / 证件 / 地址 / 银行卡 |

> 🔴 **收口点之外不得 reimplement 同类能力**（含重试、脱敏正则、连接参数调优、日志 handler）。新脚本须过 `path_governance_audit.py` 零违规。

## 4. 命名约定

| 对象 | 规则 | 示例 |
|---|---|---|
| 模块 / 文件 | `snake_case` | `order_sync.py` |
| 类 / Pydantic 模型 | `PascalCase` | `OrderRecord` |
| 常量 | `UPPER_SNAKE` | `MAX_RETRY` |
| 测试文件 | `test_*.py`，与源模块同名 | `test_order_sync.py` |
| 环境变量 | `UPPER_SNAKE`，带项目前缀 | `APP_DB_URL` |

> 更细的命名纪律（真实 / 充分 / 易记：「信达雅」）见 skill `engineering-naming-discipline`。

## 5. 依赖与环境

- 🔴 **每项目独立 venv**（`PEP 668` 环境下系统 python 装包必失败；见 skill `python-project-env-setup`）
- 🔴 依赖只进 `pyproject.toml`，锁文件随库提交；**禁止 ad-hoc `pip install`**（环境漂移根因）
- 🟡 国内网络装包走镜像源（见 skill `china-pip-mirrors`）
- 🔴 运行时只读 env，不在代码内写死绝对路径

## 6. 类型专项结构不在栈层重复

## 7. 测试与服务层结构

> **不适用可跳过**：无服务层（`serving/`）的项目跳过本节的服务层部分（跨形态内容：本项目不适用即整体跳过）。

- `tests/` 与 `src/` **镜像**；fixture 小样本放 `tests/fixtures/`
- 测试隔离外部服务（DB / Qdrant 等）用 **env 注入独立资源名**，不连生产
- 若含服务层（`serving/`）：API 与业务逻辑分离，统一响应体 + 分页约定，认证复用统一中间件（禁止接口内手写校验）

## 【层：data-processing】PROJECT-STRUCTURE — 工程结构（数据处理类项目）

### 1. 结构骨架（在 `python/PROJECT-STRUCTURE.md` 之上增加）

```text
{project}/
├── dags/                        # 编排：仅依赖组装，不含转换逻辑 🔴
├── src/{pkg}/pipelines/{domain}/ # 读写转换逻辑（按业务域）
├── src/{pkg}/models/            # schema / 契约模型，与表契约对齐 🔴
├── src/{pkg}/catalog.py         # 🔴 收口：会话、catalog、表加载、维护操作
├── sql/migrations/              # V{N}__{desc}.sql 增量 DDL
├── sql/transforms/              # SQL 转换脚本（按业务域）
├── docs/tables/{table}.md       # 表契约：一表一 md
└── tests/{fixtures,pipelines}/
```

| 目录 | 职责 | 禁止 |
|---|---|---|
| `dags/` | 任务编排与依赖组装 | 写转换逻辑、直接读写表 |
| `pipelines/` | 按业务域的读写转换 | 编排依赖、硬编码配置 |
| `models/` | schema 与类型定义 | 业务逻辑 |
| `utils/` | 跨模块通用能力收口 | 引用具体业务模块 |
| `sql/migrations/` | schema evolution 增量脚本 | 修改已提交编号、生产手工执行 |
| `notebooks/` | 探索分析 | 被生产调度引用、提交输出与凭证 |

### 2. 分层与依赖方向 🔴

- 业务域与源系统（OLTP 域）对齐，如 `trade / product / user / marketing / fulfillment`
- 数据分层：`ods`（接入）→ `dwd`（清洗明细）→ `dws`（主题聚合）→ `ads`（应用）
- 🔴 依赖方向**仅** `ods→dwd→dws→ads`，禁止反向依赖与跨层引用（如 ads 直读 ods）
- 🟡 同层跨域引用走 dws 公共主题，禁止互读 dwd 明细

### 3. 表契约（一表一档）🔴

每表一份 `docs/tables/{table}.md`，必须包含：层级 / 主题 / 粒度 / 业务主键 / **去重方式** / 分区 spec（含理由与单分区数据量预估）/ 金额单位约定 / PII 字段与脱敏方式 / 生命周期（快照保留、压缩策略、数据保留期）/ 新鲜度 SLA 与 owner / 上下游依赖 / **质量规则清单**。

契约顶部用 frontmatter 记录审批状态：

```yaml
---
status: draft | approved
approved_by: [@owner1, @finance-owner]
approved_at: 2026-09-11
version: 3
---
```
- CI 检查：`status != approved` 时禁止对应迁移合入 `main`
- **契约变更时 status 自动重置为 `draft`**，需重新审批

### 4. 命名约定（在栈规范之上补充）

| 对象 | 规则 | 示例 |
|---|---|---|
| 表名 | `{layer}_{domain}_{entity}_{cycle}` | `dwd_trade_order_di`（`_di` 日增量 / `_df` 日全量） |
| 字段 | snake_case | `pay_amount` / `created_at` |
| 模型类 | PascalCase，与表契约对齐 | `DwdTradeOrderDi` |
| DAG | `dag_{layer}_{domain}_{entity}_{cycle}` | `dag_dwd_trade_order_di` |
| 迁移 | `V{N}__{desc}.sql` | `V12__create_dwd_trade_order_di.sql` |

### 5. 收口点（单一入口）

| 收口点 | 文件 | 职责 |
|---|---|---|
| 计算与 catalog | `catalog.py` | 会话 / catalog / 表加载 / 快照过期 / 压缩触发 |
| 配置与凭证 | `config.py` | env / secret 加载，typed 输出 |
| 金额 | `utils/money.py` | 分↔元换算、舍入方式 |
| 脱敏 | `utils/mask.py` | 手机号 / 证件 / 地址脱敏 |
| 质量 | `utils/quality.py` | `check_table(df, rules)` |
| 日志与指标 | `utils/log.py` | logger + 运行指标（行数 / 分区 / 耗时） |

🔴 收口点之外不得自行 reimplement 同类能力（含会话参数调优、脱敏正则、重试逻辑）。
