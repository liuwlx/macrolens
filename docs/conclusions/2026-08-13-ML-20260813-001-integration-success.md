# ML-20260813-001-INTEGRATION remediation-1 集成成功报告

- 状态：`COMPLETE`
- 任务 ID：`ML-20260813-001-INTEGRATION-remediation-1`
- 来源控制线程：`019fc72a-2fc5-7660-b13b-431482f147e4`
- 执行席位：`ML｜集成发布部｜01`
- GitHub Issue：`https://github.com/liuwlx/macrolens/issues/8`
- 锁定基线：`aa739273710358e5f84efe724554df13efe4d3ea`
- 来源分支：`codex/ML-20260813-001-live-deep-catalog`
- 来源提交：`7521bb2f1b9cf1cc20c8f9d9ac7af2e1b709fd40`、`4ca016e4bf9097abab954c7644548f2dece354ad`
- 最终分支：`codex/indicator-source-integration`
- 集成 worktree：`E:/workerspace/projects/20260709/macrolens-tasks/ML-20260813-000-integration`
- 集成提交：`a1478c2e163d7b6669f2aa6aec1f3ea77e898545`、`1e2bffd50b995a3acaf0a960ffb8a36d3a59c207`
- 集成方式：按来源顺序逐笔 cherry-pick；无冲突；既有独立阻塞报告和来源更新报告均保留
- 解锁 Ticket：`#02`、`#21`

## 1. 本次遇到的问题以及场景

首次集成复审发现四个阻断：深链在 browser readiness 未解析时提前请求数据接口；全 null Point 被
误判为 available；series browser 的 taxonomy node filter 没有执行完整 parent graph 校验；
pending_credentials 与 pending_license 缺少浏览器端到端零请求证据。来源分支在第二笔提交中整改，
本轮必须独立验证修复，而不能只采信来源报告；只有无 P0/P1、无本票回归且共享门禁达到与锁定基线
等价或更好，才能写入唯一最终分支并关闭 Issue #8。

最终结果是四个原 finding 全部关闭。两个来源 patch 以相同 patch-id 机械集成，无业务冲突；本票
定向 Ruff/mypy/pytest、Web、OpenAPI、repository validator、build 与 Chromium E2E 全绿。全量门禁
仍包含锁定基线已有的 Ruff、mypy、Web lint 和 FastAPI 路由测试债务，但数量和位置没有本票新增。

## 2. 分析这个问题的过程

先完整重读项目规则、组织规则、实施命令、总计划、Ticket/work order、首次集成阻塞报告和来源更新
报告。Git 事实显示 source 是 `aa739273 → 7521bb2f → 4ca016e4` 的线性两提交序列；source worktree
干净。最终分支开始于 `b64cda0`，其产品基线仍为 `aa739273`，只额外包含集成发布部阻塞报告，且
source commit 尚未成为其祖先。

固定 `git diff aa739273...4ca016e4` 后，逐项阅读 20 文件完整 diff 和 remediation direct patch，
并独立复现实例。后端 21 项、Web 14 项、Chromium 6 项均通过；其中 Chromium 主动延迟 browser
响应，证明 pending_credentials/pending_license 在 readiness 解析前后都没有 detail、analytics、
observations、revisions、documents 或 AI 请求。

`code-review` 的两个只读轴结论保持分离：

### Standards

- `P0=0, P1=0, P2=0, P3=0`。
- 三态 `unknown | catalog_only | data_ready` 关闭未解析及目录态的数据能力；
  `_has_displayable_point` 排除全 null；共享投影校验覆盖 parent graph、61-set 和 owner。
- 许可保持默认拒绝，凭据只从 settings 读取；未发现浏览器 Provider 直连、vintage/lineage 破坏、
  敏感信息或需单列的 Fowler smell。

### Spec

- `P0=0, P1=0, P2=0, P3=0`。
- 三个 61-code 集合、直系子节点、祖先搜索、五类筛选/计数/列表、目录/发布 fail-closed、
  OpenAPI/TS 与禁止范围均符合 Ticket 和派工单；四个旧 finding 均 CLOSED。

主席位另记录一个非阻塞防御项：`validate_catalog_projection()` 把“root 指向不存在的 parent ID”经
字典 `.get()` 折叠为 `None`。正式 PostgreSQL 外键不允许该悬空引用，错误重挂到任何合法节点已经
统一返回 503，因此按 P2 防御纵深风险记录，不构成本票 P0/P1 或生产可达回归。后续可显式拒绝任何
非空且不在 node ID 集合中的 parent，增加纯函数负例。

## 3. 解决这个问题的工作流程

1. 核验两 worktree、锁定基线、source/final branch、两提交父链和 Issue OPEN 状态。
2. 固定两提交完整 diff，扫描范围、冲突标记、敏感信息、Provider 直连和公共契约同步。
3. 并行启动 Standards/Spec 两个独立只读审查 Agent；主席位逐项复验四个旧 finding。
4. 在 source candidate 原样运行后端、Web 与 Chromium 定向用例，确认修复真实可执行。
5. 在最终分支按顺序 cherry-pick `7521bb2f` 和 `4ca016e4`；无冲突，不改来源分支。
6. 在真实集成 HEAD 重新运行 changed-file、相关 pytest、OpenAPI、Web、build、Chromium 和 AGENTS
   全量门禁；对照锁定基线拆分既有债务与本票结果。
7. 生成并提交本七节报告；报告 commit 提供外部证据 SHA 后，由本席位向 Issue #8 添加脱敏结果并
   关闭，通知来源线程 `#02` 与 `#21` 可基于最终分支新 HEAD 启动。

## 4. 使用的 Agents、skills、tools 以及读取文档

- Agents：主执行席位 `ML｜集成发布部｜01`；只读 `standards_remediation_1` Agent；只读
  `spec_remediation_1` Agent。未创建或联系替代用户可见线程。
- Skill：`code-review`，固定 `aa739273...4ca016e4` 后把 Standards 与 Spec 分轴审查和汇总。
- Tools：Git/worktree/cherry-pick/patch-id、`rg`、Python 3.12、ruff、mypy、pytest、Node 24、npm、
  TypeScript、ESLint、Vitest、Next build、Playwright Chromium、OpenAPI generator、repository
  validator、GitHub CLI、`apply_patch`、计划和只读审查 Agent。
- 完整读取：`AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`、
  `implement-command.md`、`project-implementation-plan.md`、Ticket #01、work order #01、首次集成阻塞
  报告、更新后的来源七节报告、`code-review/SKILL.md` 和两提交全部 diff。

集成后原始检查结果：

- Patch identity：source/integrated 分别共享 patch-id `747752bc...` 与 `86796cab...`。
- Changed Python Ruff：`All checks passed!`。
- Changed Python mypy：`Success: no issues found in 4 source files`。
- 相关 pytest：`47 passed, 1 warning in 1.68s`。
- OpenAPI：`OpenAPI is current: 68 paths`。
- Repository validator：全局 `py -3.12` 缺少 PyYAML；只读复用主项目现有 `.venv` 的
  `site-packages` 作为 `PYTHONPATH` 后通过：`Repository contract valid: 61 source series, 68 API paths`。
- Changed Web ESLint：退出码 0，无输出。
- Web typecheck：退出码 0。
- Web Vitest：`10 passed` files、`32 passed` tests。
- Web production build：`Compiled successfully`；15 个页面生成；Next 自动产生的 tsconfig/next-env
  副作用已回收。
- Chromium data-browser E2E：`6 passed (6.6s)`，含两个深链 pending 状态的解析前后零数据请求。
- `git diff --check aa739273..HEAD`：通过。
- 后端全量 Ruff：`Found 334 errors`，与锁定基线快照一致；本票 changed files 为 0。
- 后端全量 mypy：`Found 38 errors in 17 files (checked 67 source files)`，与基线一致；本票四个逻辑
  源文件为 0。
- 后端全量 pytest：`1 failed, 146 passed, 5 warnings in 19.56s`；唯一失败仍为基线
  `test_api_route_surface` 对 `_IncludedRouter.path` 的假设。排除该项后：
  `146 passed, 1 deselected, 5 warnings in 17.65s`。
- Web 全量 lint：`56 problems (52 errors, 4 warnings)`，与锁定基线一致且未命中本票文件。

未执行真实 seed、migration 或一次性 PostgreSQL 验收：当前环境没有可用隔离数据库，任务也禁止
真实数据库变更。没有用 mock 结果冒充数据库验收；后续票启动前应在隔离 PostgreSQL 连续 seed 两次，
验证幂等、61 项唯一 owner、完整 parent graph 和 API 分页集合。

## 5. 本次执行值得沉淀的经验或者模式

1. 状态未解析必须显式建模为 unknown；只用 catalogOnly 布尔值会把 undefined 错当 ready。
2. 数据存在性必须下沉到“至少一个可展示值”，不能以查询返回行数代替发布 readiness。
3. 树、列表、筛选和计数必须消费同一个完整投影校验，防止中间节点漂移导致接口分叉。
4. E2E 应延迟 readiness 响应并检查网络历史，才能证明解析前窗口真正 fail-closed。
5. patch-id 是验证 cherry-pick 未改语义的直接证据；提交 SHA 改变不等于内容漂移。
6. 全量门禁非绿时，只有基线可复现、changed-file 全绿且计数不恶化，才能判定无本票回归。
7. Next 门禁会修改 tsconfig/next-env；集成流程必须把这些副作用显式回收后再检查工作树。

## 6. 问题解决后反推的一条更好的初始提示词

> 请把 Live 数据浏览器的目录状态和数据能力拆开：深链指标在 browser readiness 未解析时必须是
> unknown，任何非 available 状态必须是 catalog-only，只有已解析且 available 才能请求详情、分析、
> 观测、修订、文档或 AI。后端只有存在非空可展示 observation 且许可通过时才能 available。树接口、
> series browser、筛选和计数必须共用一套对 61 项集合、完整 parent graph 与唯一 owner 的校验，
> 任何合法节点重挂统一返回 503。先写全 null、节点重挂、pending_credentials/license 深链网络 RED，
> 再实现并运行 changed/full 后端门禁、Web test/build 和 Chromium E2E，不 push 或部署。

## 7. 当前场景是否有更优方案及一次解决的更优提示词

更优长期方案是构造请求级不可变 `ValidatedCatalogProjection`，一次读取并验证 registry、数据库
parent graph、61 series、owner、catalog/data binding、许可和可展示值，再供 taxonomy、browser、
facets、counts 与能力接口共同消费。当前共享校验已统一核心规则，但路由和 loader 仍有重复查询，且
悬空 parent 的防御可加强。

> 请在一次性 PostgreSQL 和精确基线 worktree 中，用 TDD 建立不可变
> `ValidatedCatalogProjection`。构造时必须拒绝重复节点、未知 parent、环、错误 root、61-set 漂移、
> 多 owner、多 verified primary、许可拒绝和全 null observation；失败统一 503。taxonomy children、
> browser、facets、counts、详情、观测、导出与 AI 只能消费该投影。前端只接受 unknown、catalog_only、
> data_ready 三态。用延迟深链、全 null、未知 parent、合法节点重挂、待凭据和待许可先做 RED，连续
> seed 两次验证幂等后运行全量后端、Web、build、Chromium 和 diff 门禁，再生成七节报告和聚焦提交。
