# BEA 官方元数据映射结论

## 1. 问题与场景

本轮继续处理 MacroLens 注册表中 BEA 的 23 个 `NEEDS_METADATA_MAPPING` 指标。目标是从 BEA 官方 API 取得真实 `SeriesCode`、`LineNumber`、`LineDescription`、单位和历史首期，补齐生产映射；任何没有单一官方行的概念继续阻塞，不使用模糊匹配或 FRED ID 代替 BEA ID。

官方接口：<https://apps.bea.gov/api/data>。本轮只读请求使用 `GETDATA`、`Year=ALL`、`ResultFormat=JSON`，没有把 API Key 写入代码、报告或响应证据。

## 2. 分析过程

1. 验证当前 BEA API 凭据可用：HTTP 200，BEA 业务层无授权错误。
2. 读取官方 `NIUnderlyingDetail/U20404/M` 全历史数据，得到 398 个唯一 `(SeriesCode, LineNumber)` 身份。
3. 读取官方 `NIPA/T10106/Q` 全历史数据，确认实际 GDP与实际个人消费支出历史边界及单位。
4. 对每个候选逐项检查 SeriesCode、LineNumber、LineDescription、METRIC_NAME、CL_UNIT、UNIT_MULT 和第一期。
5. 发现 21 个指标可以锁定为单一官方行；`US.PCE.NONHOUSING` 没有“核心服务剔除住房”的单行官方序列，`US.PCE.LONGTERM.CARE` 也没有覆盖完整长期护理概念的单行官方序列，因此保留阻塞。

## 3. 已补齐的 21 个映射

### NIUnderlyingDetail / U20404 / M

| MacroLens code | BEA SeriesCode / LineNumber | 官方 LineDescription | 首期 |
|---|---|---|---|
| `US.PCE.HEADLINE` | `DPCERG / 1` | Personal consumption expenditures | 1959M01 |
| `US.PCE.CORE` | `DPCCRG / 374` | PCE excluding food and energy | 1959M01 |
| `US.PCE.CORE.GOODS` | `IA000062 / 375` | PCE goods excluding food and energy | 1959M01 |
| `US.PCE.CORE.SERVICES` | `IA000063 / 376` | PCE services excluding energy | 1959M01 |
| `US.PCE.HOUSING` | `DHSGRG / 153` | Housing | 1959M01 |
| `US.PCE.MEDICAL` | `DHLCRG / 172` | Health care | 1959M01 |
| `US.PCE.HOSPITAL` | `DHSPRG / 183` | Hospitals (51) | 1959M01 |
| `US.PCE.PHYSICIAN` | `DPHYRG / 174` | Physician services (44) | 1959M01 |
| `US.PCE.OTHER.PROFESSIONAL` | `DOMDRG / 179` | Other professional medical services | 1987M01 |
| `US.PCE.DENTAL` | `DDENRG / 175` | Dental services (45) | 1959M01 |
| `US.PCE.MEDICAL.EQUIPMENT` | `DTAERG / 66` | Therapeutic appliances and equipment (42) | 1959M01 |
| `US.PCE.PRESCRIPTION` | `DRXDRG / 123` | Prescription drugs | 1959M01 |
| `US.PCE.HEALTH.INSURANCE` | `DHINRG / 275` | Net health insurance (112) | 1959M01 |
| `US.PCE.TRANSPORT` | `DTRSRG / 190` | Transportation services | 1959M01 |
| `US.PCE.RECREATION` | `DRCARG / 209` | Recreation services | 1959M01 |
| `US.PCE.FOOD.SERVICES` | `DFSARG / 234` | Food services and accommodations | 1959M01 |
| `US.PCE.FINANCE` | `DIFSRG / 252` | Financial services and insurance | 1959M01 |
| `US.PCE.OTHER.SERVICES` | `DOTSRG / 280` | Other services | 1959M01 |
| `US.PCE.DURABLES` | `DDURRG / 3` | Durable goods | 1959M01 |
| `US.PCE.NONDURABLES` | `DNDGRG / 72` | Nondurable goods | 1959M01 |

所有 U20404 行的官方身份字段为 `METRIC_NAME=Fisher Price Index`、`CL_UNIT=Level`、`UNIT_MULT=0`。

### NIPA / T10106 / Q

| MacroLens code | BEA SeriesCode / LineNumber | 官方 LineDescription | 首期 | 平台缩放 |
|---|---|---|---|---|
| `US.PERSONAL.CONSUMPTION` | `DPCERX / 2` | Personal consumption expenditures | 1947Q1 | `0.001` |

该序列官方单位为 `METRIC_NAME=Chained Dollars`、`CL_UNIT=Level`、`UNIT_MULT=6`；平台继续使用十亿美元，因此保留显式 Decimal 缩放 `0.001`。此前使用的 `T20306` 仅从 2007Q1 起，不满足完整历史要求，已改用 `T10106`。

## 4. 仍然阻塞的 BEA 概念

- `US.PCE.NONHOUSING`：U20404 提供 `PCE services excluding energy`，但仍包含住房，不能冒充“核心服务剔除住房”；需要版本化权重公式或重新定义概念。
- `US.PCE.LONGTERM.CARE`：官方行有 `Nursing homes`、`Home health care` 等组件，但没有覆盖完整长期护理服务的单一行；需要明确组件边界和派生公式。

## 5. 修改内容

- `database/seed/source_registry.json`：BEA READY 从 1 增加到 22，新增 21 个精确官方身份；全注册表 READY 从 33 增加到 54。
- `DATA_COLLECTION_MODULE_REVIEW.json`：BEA `enabled_series=22`、`blocked_series=2`；阻塞指标清单同步为 7 条。
- `backend/tests/test_registry_and_schema.py`：新增 BEA 身份完整性和两个明确阻塞项的断言。
- `backend/tests/test_ingestion_completeness.py`、`backend/tests/test_ingestion_module_review.py`：更新 readiness 数量断言。

## 6. 验证结果

- 官方 BEA 全历史身份审计：22/22 PASS。
- BEA 目标测试：116 passed。
- `ruff check backend`：通过。
- `mypy backend/src`：通过。
- 未执行 seed、数据库同步、回填、部署或远程验收。

## 7. 使用的 Agents、skills、tools 和文档

- Agents：当前会话没有可调用的后台 Agent 工具，因此由主线程完成；未伪造后台 Agent 结果。
- Skill：`research`；按其要求使用 BEA 一手 API 并将证据写入本报告。
- Tools：`exec_command`（官方 API 只读核验、测试、静态检查）、`apply_patch`（注册表、测试和报告修改）。
- 文档：根目录 `AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`、`docs/governance/development-constitutions/README.md`、`01-local-development-and-freeze.md`。

## 8. 后续建议

下一步不要继续猜测剩余两项。应为 `NONHOUSING` 和 `LONGTERM.CARE` 建立派生指标定义、组件依赖、权重来源和公式版本；在公式通过宏观研究验收前，保持 `NEEDS_METADATA_MAPPING`。然后再处理 Census Durable Goods 的维度映射。
