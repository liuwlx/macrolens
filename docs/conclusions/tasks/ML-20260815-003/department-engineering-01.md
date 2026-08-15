# ML-20260815-003 研发部 01 席位报告

- 席位：IMPLEMENTING，交付时状态为 REVIEW
- 起始提交：`7dc982e1deb7e9e223c15e436a464b5717bc341b`
- 实现提交：`8b748823bbedc7bc844534c1b38ec578b27ef5e1`、`060b0a1b78b440d5f2d9a8c95e154bd4f73aa95e`
- remediation 提交：`1446978f4e3cb1e1b93979e023ca2c6e60ef213d`
- 工作边界：仅在指定独立 worktree 和获准文件内修改；未合并、推送、部署或操作根 worktree。

## 1. 问题与场景

现有 mapping probe 主要覆盖 BLS，缺少 EIA、BEA、Census 的统一只读上线判定，也没有统一表达 transport、HTTP、business、identity、authorization 证据与稳定 issue。与此同时，EIA、BEA、Census 的 fetch 结果可能把请求 Key 保存在 URL、参数、raw bundle 或异常信息中，构成 P0 凭据持久化风险。

本任务要求保持旧 `MappingProbeResult` 字段与审批兼容，只增加结构化 evidence/issues；通过 `Adapter.probe(...)` 与 `probe_mapping(...)` 两个公共 seam 完成四源显式分派和 fail-closed 判定，不修改审批模块或公共 API Schema。

## 2. 分析过程

先核对指定 worktree 的 HEAD 与起始 SHA 一致，并检查现有 BLS probe、三源 adapter/fetch、mapping locator 与 dispatcher。分析得到以下边界：

- PASS 必须由 transport、HTTP 2xx、business、identity、authorization 全真且无阻断 issue共同决定；只缺授权才可为 AUTH_REQUIRED，其余均为 BLOCKED。
- 收到 HTTP response 时必须以原始 bytes 计算固定 SHA-256；没有 response 时 hash 为空。
- EIA 必须严格限定 v2 series route 和 metadata/首行 identity；description 只能作为证据。
- BEA 与 Census 的 locator 不完整必须在 HTTP 前阻断，不能靠模糊匹配自动晋级。
- Key 脱敏不能只处理 query 参数，还要覆盖递归数据、异常文本以及 HTTP client 反射的 request headers；保存的 response URL 不得带 query。
- dispatcher 必须复核 adapter 返回的 provider/source/provider_series identity，避免错误 adapter 结果被接受。

双轴 review 后还发现并修复：Census geography 值未核验、异常 headers 可能反射 Key、EIA route 接受首尾斜杠、BEA `unit_mult=0` 被真假值判断跳过，以及内部 helper 暴露为额外公共 seam。BEA 完全重复但 identity 相同的数据行是否应阻断属于规范解释风险；当前按“固定 identity 唯一”执行，没有扩大为“响应行必须唯一”。

## 3. 解决流程

采用 TDD RED→GREEN 纵向切片：

1. 先运行旧 BLS/审批基线，结果 14 passed。
2. EIA PASS 测试先因缺少 `probe` 得到有效 RED，再实现通用 evidence/issues、不变量和严格 EIA probe，取得 GREEN。
3. BEA、Census 各自先以缺少 probe 得到 RED，再逐源实现 preflight、错误结构、identity 与数据校验。
4. dispatcher 测试最初 4 failed/1 passed，加入显式四源注册、未知源 fail-closed、返回 identity 复核和 fingerprint 后 5 passed。
5. P0 fetch 脱敏回归最初 6 failed，修复 URL、参数、raw bundle、异常后转为通过；随后增加递归 Key 哨兵。
6. review remediation 的 route/geography/header 组合先 5 failed/1 passed，修复后 6 passed；BEA 数值零 `UNIT_MULT` 也先 RED 后 GREEN。
7. 最终目标与相关回归为 130 passed、4 warnings；目标切片单独为 65 passed。

固定 fixture SHA literal：

- EIA：`f9ebf22c8b5b50a1af8710d606d84aea3f21d1093cd913a0aab5b34e6d342c1d`
- BEA：`ec36476c1acbb760139727278c167544b5166ead8baf557773ef95f872695509`
- Census：`1fe5601cee0c08a4273ed1d57108ab263959ad44f2ea4eb2a488008cbef4c638`

门禁结果：

- owned-file ruff：通过。
- focused mypy（5 个变更源文件，`--follow-imports=skip`）：通过，0 issues。
- 后端全量 pytest：1 failed、217 passed、5 warnings；失败为既有 `test_api_route_surface` 对 `_IncludedRouter.path` 的假设，单独运行可稳定复现，文件不在本席位所有权内。
- 全量 ruff：303 个既有错误，集中在 Alembic 生成文件和旧测试等非所有权文件。
- 全量 mypy：35 个既有错误、16 个非所有权文件，并有 lxml、boto3、openpyxl、fitz 等缺失 stubs。
- Web lint/test/build：分别因 `eslint`、`vitest`、`next` 不可用而阻塞；按时限记录，未无限等待或安装依赖。

## 4. Agents、skills、tools 与文档

Agents：

- 主 IMPLEMENTING 席位完成实现、测试、门禁与提交。
- Nash 以只读 Standards 轴 review，指出报告缺失和若干非阻断重复/数据簇气味。
- Goodall 以只读 Spec 轴 review，定位 Census geography、header Key、公共 seam 与 EIA route 风险。

Skills：

- `tdd`：约束每个行为先得到有效 RED，再做最小 GREEN，最后 review/refactor。
- `code-review`：并行执行 Standards 与 Spec 双轴审查；其结论直接促成 remediation。

Tools：PowerShell shell、`rg`、Git、pytest、ruff、mypy、`apply_patch`，以及只读 review 子代理。外部边界测试只模拟 HTTP；未写远程数据库、未启动应用或 Docker。

完整读取：

- worktree `AGENTS.md`
- worktree `.codex/organization.toml`
- worktree `docs/organization/README.md`
- 根项目只读 `docs/governance/development-constitutions/README.md`
- 根项目只读 `docs/governance/development-constitutions/01-local-development-and-freeze.md`
- 根项目只读 `docs/conclusions/tasks/ML-20260815-003/task-card.md`
- `tdd/SKILL.md` 及其测试、mocking 参考
- `code-review/SKILL.md`

执行阶段为本地开发、冻结前实现与 review；完成证据是三个代码提交、目标/回归结果、双轴审查和本报告。

## 5. 可沉淀经验与模式

- probe 结果应由集中式不变量构造，避免各 provider 分别决定 PASS/AUTH_REQUIRED/BLOCKED。
- “凭据不落盘”必须以递归哨兵验证全部 result、URL、params、raw、issues 和异常，并包含 HTTP request headers 反射场景。
- Provider identity 应分两层校验：adapter 校验官方响应，dispatcher 再校验 adapter 结果与 registry mapping，形成 fail-closed 防线。
- locator 不完整应在网络前失败；这既节约调用，也避免用远端模糊结果填补治理缺口。
- geography、units、metric、period 等看似附属字段实际都是 identity；只校验 headers 或行数不足以防漂移。
- 大仓门禁应区分“本次变更目标回归”和“可独立复现的既有阻塞”，但不能因此隐藏全量失败。

安全结论：请求仍把 Key 发送到官方端点，但持久化结果、无 query URL、递归参数/raw、issues 和已覆盖异常不含 Key。剩余安全风险较低，主要是未来新增 HTTP client 异常形态时仍需沿用递归脱敏 helper 与哨兵测试。

仍 BLOCKED 的 registry 项：

- BEA_API 共 24 项，均为 `NEEDS_METADATA_MAPPING`，provider_series_id 为空且缺少 series_code、line_number、line_description：`US.PCE.HEADLINE`、`US.PCE.CORE`、`US.PCE.CORE.GOODS`、`US.PCE.CORE.SERVICES`、`US.PCE.HOUSING`、`US.PCE.NONHOUSING`、`US.PCE.MEDICAL`、`US.PCE.HOSPITAL`、`US.PCE.PHYSICIAN`、`US.PCE.OTHER.PROFESSIONAL`、`US.PCE.DENTAL`、`US.PCE.MEDICAL.EQUIPMENT`、`US.PCE.PRESCRIPTION`、`US.PCE.HEALTH.INSURANCE`、`US.PCE.LONGTERM.CARE`、`US.PCE.TRANSPORT`、`US.PCE.RECREATION`、`US.PCE.FOOD.SERVICES`、`US.PCE.FINANCE`、`US.PCE.OTHER.SERVICES`、`US.PCE.DURABLES`、`US.PCE.NONDURABLES`、`US.REAL.GDP`、`US.PERSONAL.CONSUMPTION`。
- Census 共 2 项，均为 `NEEDS_DIMENSION_MAPPING` 且仍需 dictionary resolution，缺少完整 value/time/required_variables/dimensions：`US.RETAIL.SALES`、`US.DURABLE.ORDERS`。
- EIA `US.WTI` 结构上 READY，运行探测仍需要实际授权；BLS 旧流程保持不变。

## 6. 更好的初始提示词

请检查并修复 MacroLens 的多数据源映射上线探测：让 BLS、EIA、BEA、Census 都能在不写数据库的情况下核对官方数据身份、业务成功、授权和响应指纹。任何身份资料不完整或响应漂移都要拒绝上线，并保证 API Key 只发送给官方，绝不出现在保存结果、URL、原始包或异常中。请先写失败测试再实现，保留旧 BLS 和审批兼容，最后运行后端与 Web 门禁，并列出仍不能上线的映射及原因。

## 7. 更优的一次性方案提示词

请在指定独立 worktree、指定起始 SHA 和文件所有权内，用 TDD 纵向完成四源只读 mapping probe。先冻结旧 `MappingProbeResult` 与 BLS/审批兼容测试，再集中实现 evidence/issues、状态不变量、序列化和递归脱敏；随后按 EIA→BEA→Census 顺序，每源先覆盖 PASS、授权、transport、HTTP、business、identity drift，再做最小实现。EIA 必须严格核验 v2 series route 与 daily 首期；BEA/Census locator 不完整时网络前阻断，只允许固定 identity 精确匹配。最后实现显式 dispatcher、返回 identity 二次校验、fingerprint 和未知源 fail-closed。对三源 fetch 加入“Key 仍随请求发送但所有持久化路径均无 Key”的递归哨兵测试。完成后并行做 Standards/Spec review，修复 confirmed finding，运行目标测试、ruff、mypy、后端全测及 Web 三门禁；对非所有权阻塞给出可复现证据，不越界修复。提交实现、remediation 和七节部门报告，返回全部 SHA、RED/GREEN、门禁、安全风险与 registry BLOCKED 清单，不合并、推送或部署。
