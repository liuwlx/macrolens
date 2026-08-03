# ML-20260804-001 安全合规部 01 集成候选复核报告

## 部门交付回执

- 席位状态：`REVIEW`
- 任务 ID：`ML-20260804-001`
- 复核范围：`b5ab5ed3cb2eec553bba4c4bc878c3abec5d0da8..2e3484981c0696e960ec3b27cb78464454830b1c`
- 后端候选：`62a9d5626ffc10e74baa77e9af992e74dc1f3e11`
- 前端候选：`2e3484981c0696e960ec3b27cb78464454830b1c`
- 修改文件：仅本报告；未修改业务代码
- 提交 SHA：无，由主线程与集成发布部统一集成
- 结论：确认 1 项 P0、2 项 P1；均已即时回传主线程并进入 Engineering remediation。除这些项目外，未确认新的独立 P0。

## 1. 问题与场景

本次复核检查集成后的数据浏览器是否真正落实任务卡中的许可、快照、导出、工作区和 AI 安全边界。重点不是按钮是否显示，而是直接调用 API、切换账号、缺少许可记录和绕过 capability 提示时，服务器及客户端缓存是否仍然 fail closed。

测试部已经单独确认 observations/revisions 认证与快照、browser 先计算后分页、AI 多上下文历史 cutoff、RFC 9457 validation 和 AI 创建幂等性问题。本报告不把这些问题重复计为安全部独立发现。

## 2. 分析过程

1. 完整读取组织规则、任务卡、任务计划、许可规则和安全模型。
2. 检查固定 Git diff 及新增 browser、analytics、export、AI capability、AI context、React Query 和 SDK 路径。
3. 用预审 P0/P1 清单逐项追踪输入、权限判定、数据查询、序列化和客户端缓存消费链。
4. 对可复现问题立即回传主线程；对任务卡 amendment #1 明确允许的 authenticated in-product audience 重新定级。
5. 去除测试部已报问题和无法由代码证据支持的推测，只保留以下三个独立发现。

## 3. 已确认发现与解决流程

### P0：React Query 私有 AI 数据可跨账号复用

证据：

- `apps/web/app/(app)/ai/page.tsx:36-39` 使用固定 query key `['ai-runs']` 和 `['ai-citations', runId]`，没有用户或工作区维度。
- `apps/web/components/providers.tsx:10-16` 创建跨登录会话常驻的 QueryClient，默认 `staleTime=30_000`。
- `apps/web/components/auth-provider.tsx:59-62` 退出登录只清空 React 用户状态，没有清理 QueryClient。

可复现场景：用户 A 打开 AI 结果后退出，用户 B 在同一浏览器 30 秒内登录并打开 `/ai`。固定 key 命中仍为 fresh 的 A 缓存，页面可在 B 的授权请求发生前直接渲染 A 的 prompt、结果和 citations。

要求的修复：在身份建立、退出和身份切换时清除用户私有缓存；所有 AI runs/citations、saved views、notes 等私有 query key 加入稳定的 user/workspace scope。该项已派发 Engineering 02。

### P1：AI 文档上下文仍会从 provider redistribution 推导 AI 授权

证据：

- `backend/src/macrolens_api/services/ai_context.py:162-168` 的 document context 使用 `get_license_for_provider()`。
- `backend/src/macrolens_api/services/licenses.py:63-79` 在没有有效 `LicensePolicy` 时，以 `Provider.redistribution_ok` 同时推导 `ai_context_allowed=True`；该查询也没有把同优先级多个有效 policy 视为冲突。

可复现场景：Provider 设置 `redistribution_ok=true`，但没有显式 AI policy；将其文档加入 AI run 时，文档 chunks 会通过检查并进入外部模型上下文。可公开再分发不等于允许 AI 使用，违反四类许可独立判定规则。

要求的修复：document context 与 series context 共用严格许可解析器；缺失或同层冲突 policy 均拒绝 AI context。该项已派发 Engineering 01。

### P1：AI capability 的模型配置判断未在创建端再次执行

证据：

- `backend/src/macrolens_api/routers/ai.py:37-41` 只有 capability GET 根据 `OPENAI_API_KEY` 返回 `configured`。
- `backend/src/macrolens_api/routers/ai.py:44-106` 的 `POST /ai/runs` 未检查模型是否配置，直接持久化 run 并 enqueue。
- `apps/web/app/(app)/ai/page.tsx:72` 只在 URL 附带指标时用 capability 禁用按钮；普通搜索添加的指标或文档不受该提示约束。
- `backend/src/macrolens_worker/tasks/ai.py:127-132` 直到 Worker 执行时才把任务标为失败。

可复现场景：无 `OPENAI_API_KEY` 时，从普通上下文选择器添加文档并直接 POST `/ai/runs`，服务器返回 202、创建 run/job，随后 Worker 失败。攻击者可持续制造确定失败的任务和审计噪声。

要求的修复：创建端与 capability 共用配置判定，在持久化 run/job 前返回稳定的 409/503 problem details。该项已派发 Engineering 01。

## 4. 已验证通过、撤销项及使用资源

已验证通过：

- 新 browser/analytics/export 路由要求 `CurrentUser` 与 `CurrentWorkspace`。
- 新 browser license resolver 对缺失或冲突策略 fail closed；display denied 不返回 current、previous 或派生数值。
- 唯一主源按 0/1/>1 三态处理，多主源不静默选择。
- `_points_by_source` 从 append-only `ObservationVintage` 按 `vintage_at <= data_as_of` 和每期最后版本查询。
- 整表导出在内存缓冲前检查完整结果的 `download_allowed`，单指标导出也在服务端授权；响应带 `private, no-store`、`nosniff`，CSV 文本单元格中和公式前缀及记录控制字符。
- 贡献分析因现有 schema 无法证明 dependency-definition version 绑定而统一 fail closed，未执行 `weight_expression`。
- sort/order 使用路由正则和内部枚举映射；limit、offset、查询文本和 taxonomy 遍历均有边界。
- 新页面 URL 使用 `URLSearchParams`/`encodeURIComponent`，新增文档链接使用内部 UUID 路由，未发现新增的任意协议导航。

撤销项：

- 初步把 `api_redistribution_allowed=false` 的 authenticated JSON 返回列为 P1。任务卡 amendment #1 明确 browser/analytics 可服务 authenticated in-product audience，且 `@macrolens/sdk` 为 `private:true` 的同仓内部客户端。当前路由已认证，不存在公开 SDK 或未认证数值端点证据，因此该项撤销，不要求改成 `display && api_redistribution`。

Agents、Skills、Tools 与文档：

- Agents：安全合规部 01；曾派发两个只读 diff 子任务用于后端和前端并行核对，其中后端子任务因同一安全扫描启动门禁未形成额外发现。
- Skill：`codex-security:security-diff-scan`。技能已完整读取并打开工作区，但 `await_codex_security_scan_start` 长时间未收到 Start scan；为不阻塞工程闭环，终止纯等待后降级为固定 diff 的普通只读安全审查。本报告不是完成态 Codex Security 四阶段扫描。
- Tools：Git diff/status、Ripgrep、PowerShell 文件读取、只读代码追踪、协作消息与 `apply_patch`。
- 文档：`.codex/organization.toml`、`docs/organization/README.md`、任务卡、完整实现计划、`docs/licensing.md`、`docs/security.md`、根 `AGENTS.md`。

## 5. 值得沉淀的经验与模式

- 客户端权限隔离不仅是 query key 设计，还必须处理身份切换时的缓存生命周期；只在新 query key 中加 user ID 无法清除旧的私有缓存。
- capability 接口只是用户体验提示，真正授权与运行条件必须在产生持久化副作用的 POST 中再次检查。
- 许可 resolver 不能按资源类型分叉成宽松和严格两套实现；series 严格而 document 宽松仍会从 AI 聚合入口泄漏。
- 安全预审中的保守解释应服从后续任务卡 amendment。站内认证 JSON 与外部 API redistribution 必须用明确 audience 边界解释，而不是简单把两个许可位求交。

## 6. 更好的初始提示词

> 请审查数据浏览器集成 diff，并把登录用户切换视为完整攻击场景。逐项验证：所有数值 API 是否认证、许可缺失或冲突是否拒绝、展示/下载/AI 是否由独立服务器端门禁控制、指定 data_as_of 是否只读 ObservationVintage、CSV 是否全量预检并防公式注入、AI capability 是否在创建端重验、React Query 私有缓存是否同时按 user/workspace 分区并在 logout/login 时清除。只报告可用直接 API 或浏览器步骤复现的问题，给出文件行号，并与任务卡的 audience amendment 对齐。

## 7. 更优方案与提示词

更优方案是把“身份—许可—快照—用途”收敛为共享的访问决策对象：后端 series/document/export/AI 全部复用，前端 QueryClient 由身份边界统一清理，随后用双账号浏览器测试和许可矩阵测试一次性验证。

> 请先实现并测试一个共享 AccessDecision 服务：输入 actor/workspace、资源、用途（display/download/in-product-api/AI）和 data_as_of，输出 allow/deny、policy version 和稳定 reason code；series 与 document AI context、browser、analytics、export 必须共用。前端在认证身份变化时清空私有缓存，所有私有 query key 包含 user/workspace。用用户 A→退出→用户 B、缺失/冲突 policy、display-only、download-denied、AI-denied 和历史 cutoff 组成端到端矩阵，全部通过后再集成。

## 检查与阻塞说明

- 已执行：固定 diff 逐文件安全审查、行号证据核对、`git status`、任务卡 amendment 复核。
- 未执行：完整项目测试和正式 Codex Security 四阶段扫描；前者由 Quality/Integration 统一执行，后者受安全工作区 Start scan 未返回阻塞。
- 给集成发布部：三个发现对应修复进入 main 后，应重新执行双账号缓存测试、AI 文档缺省/冲突 policy 测试和无模型配置的 POST 创建测试；在此之前安全状态保持 `REVIEW`，不可视为最终放行。

## 8. Remediation 复核（`d53c115` / `2acf33a`）

### 原始三项发现的复核结论

- **CLOSED — P0 跨账号 React Query 私有缓存复用。** `auth-provider.tsx` 在用户 ID 或角色变化时清空共享 QueryClient；AI runs/citations、saved views 与 notes 的 query key 均加入当前用户身份维度，并新增 A→logout→B 回归测试。
- **CLOSED — P1 文档 AI 上下文从 redistribution 推导 AI 授权。** 文档上下文改用严格许可解析；缺少 policy 或同优先级多条有效 policy 时，四类许可全部 fail closed。
- **CLOSED — P1 POST `/ai/runs` 未重复校验模型配置。** capability GET 与创建 POST 共用 `ai_runtime_configured()`；未配置 key 或模型时，POST 在预留、持久化与入队之前返回稳定的 503 problem details。

### 追加路径复核

- **PASS — AI 创建幂等性。** `Idempotency-Key` 为必需请求头；预留键按 workspace、user 和 key 隔离，payload 摘要不同时返回 409，相同 payload 重放返回已有 run，预留与 run/context 在同一事务提交。未发现新绕过。
- **PASS — observations/revisions 的认证与 cutoff。** 两条路由均要求 `CurrentUser` 与 `CurrentWorkspace`，规范化 `data_as_of` 后仅查询 `ObservationVintage.vintage_at <= data_as_of`。
- **OPEN P1 — observations/revisions 的多主源冲突未 fail closed。** 两条服务仍调用 `backend/src/macrolens_api/services/series.py` 中的 `get_primary_source()`；该函数对 `is_primary=true` 且 `mapping_status='verified'` 的结果直接 `.first()`。当存在两条 verified primary source 时会静默选择一条，违反任务卡 Security amendment #5 的“0 条或多条均 fail closed”，也绕过 browser/analytics/AI 已采用的严格唯一主源判定。修复应查询至多两条并要求结果数恰好为一，同时增加 observations 和 revisions 的多主源冲突回归测试。

因此，本轮三项原始 finding 已全部闭合，但整体安全门禁仍为 **REVIEW**，当前仍有 **1 项 P1**，不能写入“PASS / 无开放 P0/P1”。

### 验证与工具门禁

- `$env:PYTHONPATH='backend/src'; pytest -q backend/tests/test_data_browser.py`：`7 passed, 9 skipped`；异步安全用例因当前 Python 3.11 环境缺少可用的 pytest-asyncio 支持而跳过，不能把跳过视为覆盖通过。
- `npm --workspace apps/web run test -- --run components/auth-provider.test.tsx`：测试收集前被现有 Node/CommonJS 与 `@csstools/css-calc` ESM 兼容错误阻断；这不是本次修复引入的断言失败，但双账号回归仍需在集成发布环境完成。
- `codex-security:security-diff-scan` 的 Start scan 门禁仍未返回。本轮按主线程要求不再重复等待，使用固定提交与逐路径人工复核完成结论；正式四阶段扫描仍标记为工具门禁未完成。
- `codex_app__load_workspace_dependencies` 的运行时发现调用长时间无输出，已终止纯等待，没有将其计为验证成功。

### 本轮追加使用的 Agents、Skills、Tools 与文档

- Agents：安全合规部 01；未新增子 Agent。Engineering 01/02 的修复提交作为只读复核对象。
- Skill：继续遵循已加载的 `codex-security:security-diff-scan`，但因 Start scan 阻塞，本轮仅执行其人工固定 diff fallback，未宣称完成正式扫描。
- Tools：`rg`、`git log/status/diff`、PowerShell 文件读取、`pytest`、Vitest、`apply_patch`、协作消息、workspace dependency runtime 探测。
- 文档：根 `AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`、任务卡及其 Security amendments、`docs/licensing.md`、`docs/security.md`。

### 追加沉淀

- “严格唯一来源”必须成为共享服务不变量；如果新路径复用旧的 `.first()` helper，即便相邻新模块已正确 fail closed，仍会形成策略分叉。
- 安全复核不能只回归原 finding。修复同时触达认证、cutoff 和幂等性时，应沿调用链复查共享 helper，否则容易漏掉独立的授权/完整性绕过。

### 更好的初始提示词（复核版）

> 请对数据浏览器 remediation 提交做固定 diff 安全复核：先验证跨账号缓存、AI 文档许可和模型配置预检三项原 finding 是否闭合，再沿 observations/revisions、AI 幂等性和共享 primary-source helper 检查新绕过。任何取唯一资源的逻辑都必须对 0 条和多条 fail closed；给出可定位的文件与函数证据，并且只有在没有开放 P0/P1 且安全回归实际运行通过时才写 PASS。

### 一次解决的更优方案提示词（复核版）

> 请把 verified primary source 的“结果必须恰好一条”收敛为一个共享严格 resolver，并让 browser、analytics、AI、observations、revisions 全部调用它；为每条入口添加 0/1/2 主源矩阵测试。同时运行 A→logout→B 缓存隔离、缺失/冲突许可、未配置模型 POST、幂等重放与历史 cutoff 回归。完成固定 diff 安全审查并修完所有 P0/P1 后，再返回可发布结论和证据。

## 9. Remediation02 最终安全工具门禁（`79e65c07298e19e2d183300ec9ef9fad2bc4ce41`）

### 本轮范围与执行状态

本轮按主线程要求，仅计划复核以下安全边界：

1. legacy `get_primary_source` 是否对 0/1/>1 条 verified primary source 严格 fail closed；
2. observations/revisions 是否继承同一个严格 resolver；
3. current、previous、change、period change、YoY 五种动态排序是否仅使用严格 `display_allowed` 许可和 `data_as_of` cutoff 后的值，且不会通过排序次序泄漏不可显示数值。

已复读 `.codex/organization.toml`、`docs/organization/README.md`、任务卡及 Security amendments，并把固定提交范围解析为 `62fd1b9ee29691448dbe77cded681c0294b927aa..79e65c07298e19e2d183300ec9ef9fad2bc4ce41`。随后按 `codex-security:security-diff-scan` 技能要求打开 Codex Security workspace session `ea205281-a474-4f66-a9e6-09541c6827ad`，但 `await_codex_security_scan_start` 始终未返回 Start scan 或 authoritative `scanId`。主线程明确要求停止等待且不得越过技能门禁开展源码复核，因此已终止纯等待；本轮没有检查源码、没有运行聚焦测试，也没有修改业务代码。

### P0/P1 与此前 P1 状态

- 此前已经验证关闭的原始 P0 跨账号缓存、P1 文档 AI 许可和 P1 模型配置预检保持 **CLOSED**，本轮没有证据将其重新判为开放。
- Remediation01 复核确认的 legacy `get_primary_source` 多主源 P1，虽然 `79e65c0` 是其声称的修复集成点，但由于本轮安全扫描未越过 Start scan 门禁，安全合规部**无法独立确认该 P1 已关闭**。
- 因此不能宣称当前安全开放项为“P0=0、P1=0”，也不能给出 security PASS。准确状态是：已验证开放 P0 为 0；最后一项 P1 的 Remediation02 closure 尚未完成安全验证，整体门禁保持 **REVIEW / INCOMPLETE**。

### Residual risk 与交接

- 若 resolver 仍允许 0 条或多条 verified primary source 静默选取，observations/revisions 可能继续返回来源不确定的数据。
- 若五种动态排序在许可过滤前或 cutoff 外计算排序键，即使响应体遮蔽数值，结果次序仍可能形成不可显示数据的侧信道。
- 本轮 residual risk 由 Integration/Quality 的 26 项契约测试与人工验收记录承接；这些结果可作为发布综合证据，但不等价于本安全技能扫描已经完成。
- 正式安全结论需在 workspace Start scan 成功后，针对上述三条边界完成 focused scan、聚焦测试与证据核对，再决定最后一项 P1 是否可标记 CLOSED。

### 本轮 Agents、Skills、Tools 与经验

- Agents：安全合规部 01；未使用子 Agent。
- Skill：`codex-security:security-diff-scan`；技能导致本轮在 Start scan 前暂停，未执行后续四阶段扫描。
- Tools：Git revision 解析、PowerShell UTF-8 文档读取、Codex Security workspace/await、协作消息、`apply_patch`、`git diff --check`。
- 经验：工具门禁未完成时，应区分“没有新发现”与“没有完成验证”。前者不能从后者推出；同样，候选修复已经集成也不能自动等于安全 finding 已关闭。

### 更好的初始提示词（最终门禁版）

> 请在 Codex Security 工作区可立即 Start scan 的前提下，对提交 `79e65c0` 做 focused security diff review：只验证主源 resolver 的 0/1/>1 fail-closed、observations/revisions 的继承关系，以及五类动态排序的严格 display license、data_as_of cutoff 和排序侧信道。请确保 workspace 已启动并返回 scanId，同时提供可运行异步数据库测试的 Python 环境；只有扫描和聚焦测试都完成后才判断最后一项 P1 是否关闭。

### 一次解决的更优方案提示词（最终门禁版）

> 请先启动 Codex Security diff scan，再用 0/1/2 verified primary、display allow/deny、cutoff 前后 vintage 的组合矩阵测试 `79e65c0`。对 current、previous、change、period change、YoY 分别验证：被拒绝值不进入排序键，cutoff 后值不影响次序，observations/revisions 与 browser 使用同一个严格 resolver。输出每个矩阵用例和源码调用链证据；全部通过且无开放 P0/P1 后再写 security PASS。
