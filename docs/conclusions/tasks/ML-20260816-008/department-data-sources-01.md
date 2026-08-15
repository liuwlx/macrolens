# ML-20260816-008 数据源部实现报告

部门实现状态：`COMPLETE`。任务总体状态：`BLOCKED`，等待集成发布阶段在服务器执行 registry 应用、真实 MappingProbe/approval 与显式四源 `audit-live`；本席位未获授权执行这些运行态写操作。

## 1. 问题与场景

基线 `97f20a839f4b53ca0b8bdd58d777682cd8d25954` 上存在四项互相独立的真源阻塞：BLS CPI 2025-10 官方停摆缺值被通用质量门禁拒绝；EIA legacy `seriesid` 路由忽略 `start/sort` 且返回派生行 identity `RWTC`；Census EITS 不接受业务维度作为 URL 过滤条件；BEA Real GDP 与 Census Retail Sales 仍是未固定候选 locator。目标是在不执行 migration、seed、sync、backfill、部署、重启或服务器写入的前提下，修好 adapter、probe、质量门禁、registry 和离线回归。

## 2. 分析过程

先核对专属 worktree、分支和 `origin/master` 均指向指定基线，并确认初始未跟踪内容只有用户提供的任务目录。代码证据显示：质量门禁只支持空值数量豁免；EIA probe 以升序首行代替历史边界，增量 fetch 遇到 cutoff 前行即失败；Census probe/fetch 把 `seasonally_adj/category_code` 等维度发给上游，并把矩阵非目标行视为错误；registry 的 Census/BEA 映射状态仍未就绪。

按公开测试缝拆成四个纵向 TDD 切片：`validate_ingestion_completeness`、`EIAAdapter.probe/fetch`、`CensusEITSAdapter.probe/fetch`、registry 契约。有效 RED 原始结果依次为：BLS 精确日期测试 `1 failed`；EIA 双响应 probe `1 failed`；EIA 本地 cutoff 过滤 `1 failed`；Census probe 参数/矩阵过滤 `1 failed`；Census fetch 参数/矩阵过滤 `1 failed`；registry identity `1 failed`。首次直接调用系统 pytest 落入 Python 3.11 且缺项目导入路径，只是环境失败，不计作行为 RED；后续全部使用现有 Python 3.12 venv、`PYTHONPATH=backend/src` 与 `PYTHONUTF8=1`。

## 3. 解决流程与结果

- BLS：新增 `allowed_null_periods_by_date` 严格 ISO 日期白名单；仅 `2025-10-01` 可豁免，2025-09 的相同脚注仍产生 `missing_observation_value`。registry 只为 `US.CPI.HEADLINE` 加入该日期。
- EIA：probe 先以 `offset=0,length=1` 读取总数/元数据，再以 `offset=total-1` 读取历史边界；校验 `PET.RWTC.D → RWTC`、daily、`YYYY-MM-DD`、`$/BBL`、首期和首期值，并用两份原始响应共同计算 SHA-256。legacy `seriesid` 增量抓取完整分页、对全量行检查重复/完整性，再本地保留 cutoff 后观测；普通路由继续发送 `start/sort` 并拒绝 cutoff 前行。
- Census：probe/fetch 上游参数限定为 `get/time/key/for`；时间范围以空格值交给 httpx 编码。返回矩阵按 `SM/yes/44X72/no/us:*` 全维度过滤，非目标行跳过，零匹配或同一期多匹配 fail closed。
- Registry：`US.RETAIL.SALES` 固定 EITS marts 完整维度、字段、2025-01 probe 月和 1992 历史边界；`US.REAL.GDP` 固定 `T10106/Q/A191RX/Line 1/Gross domestic product`、2025 probe 年及 `Chained Dollars/Level/6`。两者静态状态改为 `READY`，但没有把数据库映射伪造为 `verified/primary`。

最终检查原始结果：

- 目标文件回归：`89 passed`，随后新增普通 EIA 路由保持测试单独 `1 passed`。
- 相邻 provider/MappingProbe 回归初次 `3 failed, 145 passed`，更新旧 fixture 契约后失败项复跑 `6 passed`。
- `ruff check backend`：`All checks passed!`。
- `mypy backend/src`：`Success: no issues found in 70 source files`。
- `pytest -q backend/tests`：`247 passed, 5 warnings in 15.18s`。
- registry JSON：有效，`indicators=61`；`git diff --check`：通过。
- Web lint/test/build 未执行到工具逻辑：专属 worktree 无 `node_modules`，分别报 `eslint`、`vitest`、`next` 不存在；未安装依赖，也未用其他脏工作区代替验收。

## 4. Agents、skills、tools 与文档

未调用子 Agent。使用 `tdd` skill，按公开 seam 逐切片完成 RED→GREEN。工具为 PowerShell 只读检查、pytest/ruff/mypy、`apply_patch`、计划更新与 Git 只读/提交命令；未使用浏览器、外网 Provider、Docker 或服务器连接。

本轮读取：根 `AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`、任务卡、`database/seed/source_registry.json`、`taxonomy_registry.json`、数据源目录/API 验证文档、active indicator-source-integration 经验，以及开发宪法索引和 `01-local-development-and-freeze.md`。基线 worktree 不含后两组治理/经验文档时，从原主工作区只读加载；代码和测试判断始终以专属 worktree 基线为准。

## 5. 可沉淀经验与边界

兼容路由不能用“声明的排序参数”证明历史边界；应先读取 total，再用可定位的 offset 单独取边界，并让证据哈希绑定两个响应。对于不支持业务维度查询的矩阵 API，唯一性门禁应放在本地完整维度过滤之后：非匹配行不是错误，零匹配和多匹配才是错误。官方缺值豁免必须按 canonical source 的明确日期配置，不能按缺值数量、弱脚注文本或整段时期放宽。

本次零 migration、零 seed、零 sync/backfill、零 observation/run/raw 写入、零直接 SQL、零 Scheduler 修改、零部署/重启。当前阶段若执行 migration、seed、sync/backfill、直接改数据库 `verified/primary`、部署、重启或调度变更，均违反任务卡禁令。服务器后续最小解锁动作必须由获授权席位完成：应用已合并 registry、逐源执行真实 probe 并审批、再运行显式四源只读 `audit-live`，验证 `executed=4/skipped=0/failed=0` 和零观测写入。

剩余风险：尚无服务器真实响应、凭据、approval、PR/CI 或 Compose/readiness 证据；EIA legacy 增量会为完整性读取约 10k 历史行，需在真实 Worker 观察延迟和限流；Census/BEA identity 虽有用户提供的官方证据和离线契约，仍必须由真实 probe/approval 形成生产血缘。

## 6. 更好的初始提示词

> 在指定独立 worktree 和基线上，用 TDD 修复四源真源接入，不做服务器写入。先为 BLS 2025-10 精确缺值日期、EIA seriesid 双阶段历史边界与本地 cutoff、Census 仅支持的 URL 参数和矩阵全维度唯一过滤、Census/BEA 固定 registry identity 分别建立 RED，再做最小实现。跑目标测试、ruff、mypy、完整 pytest，列出禁止的 migration/seed/sync/部署动作，写七节报告并提交；不要修改任务卡或回退他人变更。

## 7. 一次解决的更优方案提示词

> 从 `origin/master=97f20a8` 创建/使用任务指定 worktree，先输出四个公开测试 seam 和预期 RED 信号。逐切片完成：1）质量门禁只允许 `US.CPI.HEADLINE/2025-10-01` 空值；2）EIA probe 用 offset 0 与 total-1，两响应哈希，legacy identity 为 `RWTC`，seriesid 增量全分页后本地 cutoff，普通路由保持 fail-closed；3）Census 请求参数只含 `get,time,key,for`，空格时间范围，按 `SM/yes/44X72/no/us:*` 过滤并要求每期唯一；4）固定 Census 和 BEA registry locator/status。每个切片先单测 RED 再 GREEN，随后运行相邻 provider 回归、全量 ruff/mypy/pytest、JSON/diff/秘密/范围检查。禁止 Docker、migration、seed、sync/backfill、直接 SQL、调度与服务器写入；报告实际未跑项和后续 probe/approval/audit-live 解锁条件，最后只暂存授权文件并提交。
