# ML-20260813-001-INTEGRATION 集成发布门禁报告

- 状态：`BLOCKED`
- 任务 ID：`ML-20260813-001-INTEGRATION`
- 来源控制线程：`019fc72a-2fc5-7660-b13b-431482f147e4`
- 执行席位：`ML｜集成发布部｜01`
- GitHub Issue：`https://github.com/liuwlx/macrolens/issues/8`（保持 `OPEN`）
- 锁定基线：`aa739273710358e5f84efe724554df13efe4d3ea`
- 来源分支：`codex/ML-20260813-001-live-deep-catalog`
- 来源提交：`7521bb2f1b9cf1cc20c8f9d9ac7af2e1b709fd40`
- 最终分支：`codex/indicator-source-integration`
- 集成 worktree：`E:/workerspace/projects/20260709/macrolens-tasks/ML-20260813-000-integration`
- 集成提交：`N/A`；发现 P1 后未 cherry-pick
- 解锁 Ticket：无；`#02` 与 `#21` 保持等待 #01 绿色集成

## 1. 本次遇到的问题以及场景

Ticket #01 要把完整 61 项深层目录与采集 readiness 分离，并在唯一验收分支形成可供后续票使用的
绿色基线。来源提交是锁定基线的单一直接后继，19 个文件的范围、OpenAPI/TypeScript availability
枚举和目录 fail-closed 主体实现均与派工方向一致；但独立集成审查发现三项 P1，说明在特定入口和
数据库漂移状态下仍可能提前开放数据能力或静默返回错误目录。因此不能仅凭来源分支自测绿色而关闭
Issue，也不能把该提交写入最终分支。

## 2. 分析这个问题的过程

先只读核对主工作区、来源分支、来源 worktree、提交拓扑和目标分支。主工作区已有用户修改与未跟踪
文件，整个任务期间保持只读。来源提交 `7521bb2f` 的唯一父提交是锁定基线 `aa739273`，来源分支
精确指向它，来源 worktree 干净；最终分支原先不存在，因此从锁定基线创建指定隔离 worktree。

随后固定 `git diff aa739273...7521bb2f`，完整检查 19 文件、敏感信息、冲突标记、浏览器 Provider
直连、OpenAPI/后端/TS 枚举同步、catalog/data binding、availability、taxonomy 搜索和测试。敏感
模式仅命中设置字段或 Schema 名称，没有凭据字面量；没有冲突标记或浏览器直连 Provider。

按 `code-review` skill 将审查拆成两个互不共享结论的只读轴：

### Standards

- `P1`：`apps/web/components/data-browser/data-browser-page.tsx:80-84` 在 `selectedItem` 尚未加载或
  placeholder 不含深链目标时把 `catalogOnly` 视为 `false`。带 `series` 参数直接打开 pending 指标
  会先请求 detail、analytics 与 AI capability，违反 catalog-only 数据能力 fail-closed。
- `P1`：`backend/src/macrolens_api/services/data_browser.py:717-718` 使用 `if points` 判定
  `available`。若观测列表存在但所有 `value` 均为 `None`，API 会开放数据能力，生成的 browser item
  却没有可展示 current，状态互相矛盾。
- 计数：`P0=0, P1=2, P2=0, P3=0`；未发现需单列的 Fowler 判断项。

### Spec

- `P1`：规格要求树、列表、API、筛选与计数使用一致事实。`data_browser.py` 的 node filter 通过
  `taxonomy_descendant_ids()` 直接信任数据库父子关系，而 catalog 校验只核对 61 canonical code 和
  叶子 owner；节点被错误重挂时，树接口返回 503，`/series/browser?node_id=...` 却可能静默返回错误
  集合，未 fail closed。
- `P2`：多层树 E2E 只覆盖 available、not_ingested 和 pending_mapping；pending_credentials 与
  pending_license 只有单元测试，没有规格要求的浏览器端到端覆盖。
- 计数：`P0=0, P1=1, P2=1, P3=0`；未发现范围扩张。

两个轴分别包含 P1，触发“任何 P0/P1 或本票回归必须停止”的硬条件。未 cherry-pick、未尝试业务
修复、未修改来源分支、未评论或关闭 Issue #8。

## 3. 解决这个问题的工作流程

1. 完整读取项目规则、组织手册、implement 指令、总计划、Ticket #01 和派工单。
2. 确认来源提交是锁定基线的唯一直接后继，来源分支和 worktree 状态准确。
3. 从锁定基线创建 `codex/indicator-source-integration` 的唯一指定本地 worktree；不写主工作区。
4. 固定单提交 diff，执行范围、敏感信息、冲突标记、契约同步和 fail-closed 只读检查。
5. 并行运行独立 Standards/Spec 审查，并由集成席位复核每项 P1 的代码路径。
6. 在尚未集成的锁定基线保存全量门禁快照，用于区分既有失败、Windows 编码差异与本票问题。
7. 因 P1 在集成前已成立，停止 cherry-pick；只提交本集成发布部七节阻塞报告，保持 Issue 与后继票
   状态不变。

## 4. 使用的 Agents、skills、tools 以及阅读文档

- Agents：主执行席位 `ML｜集成发布部｜01`；只读 `standards_ml_20260813_001` Agent；只读
  `spec_ml_20260813_001` Agent。未创建或联系替代用户可见线程。
- Skill：`code-review`，固定 merge-base 后分开执行 Standards 与 Spec，分别保留发现和计数。
- Tools：Git/worktree 只读核验和本地分支创建、`rg`、Python 3.12、ruff、mypy、pytest、Node 24、
  npm、TypeScript、Vitest、Next build、Playwright Chromium、GitHub CLI 只读 Issue 查询、
  `apply_patch`、任务计划和内部只读审查 Agent。
- 完整读取：`AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`、
  `.scratch/indicator-source-integration/dispatch/implement-command.md`、`project-implementation-plan.md`、
  `issues/01-live-deep-catalog-availability.md`、`dispatch/work-orders/01-live-deep-catalog.md`、
  `code-review/SKILL.md`、来源提交全部 19 文件 diff 和来源部门七节报告。

检查原始结果：

- 拓扑：source parent=`aa739273...`；source branch=`7521bb2f...`；PASS。
- 范围：`19 files changed, 1159 insertions(+), 126 deletions(-)`；与任务卡一致。
- 来源 diff：`git diff --check aa739273...7521bb2f` 退出 0；无冲突标记。
- 敏感信息：无凭据字面量；浏览器 Provider 直连扫描无命中。
- 契约：后端 `SeriesAvailability`、`macrolens_openapi.yaml`、Web `BrowserSeriesAvailability` 的三个
  新 pending 值一致。
- 基线 `ruff check backend`：退出 1，`Found 342 errors`；均在来源提交应用前存在。
- 基线 `mypy backend/src`：退出 1，`Found 38 errors in 17 files (checked 66 source files)`。
- 基线原样 `pytest backend/tests`：退出 1，`3 failed, 131 passed, 5 warnings`；其中两项为 Windows
  默认 GBK 读取 UTF-8 registry/OpenAPI 失败。
- 基线 UTF-8 `python -X utf8 -m pytest backend/tests`：退出 1，`1 failed, 133 passed, 5 warnings`；
  唯一功能失败是 `test_api_route_surface` 对 FastAPI `_IncludedRouter.path` 的既有假设。
- 基线 Web lint：退出 1，`56 problems (52 errors, 4 warnings)`。
- 基线 Web typecheck：退出 0。
- 基线 Web test：退出 0，`8 passed` files、`21 passed` tests。
- 基线 Web build：退出 0，`Compiled successfully`，生成 15 个静态页面；构建自动产生的
  tsconfig/next-env 副作用已精确回收，未形成 diff。
- 基线 Chromium data-browser E2E：退出 0，`3 passed (4.6s)`。
- 基线 `git diff --check`：退出 0，worktree 在报告前干净。

未运行来源变更文件 Ruff/mypy、定向 pytest、变更后 Web/E2E 或真实 seed：硬 P1 在集成前已触发
停止条件，不存在可供这些命令验收的集成结果。来源报告中的绿色结果仅作为交付证据读取，不冒充本
席位复跑。Docker/隔离 PostgreSQL 未使用；因此未执行真实 seed 或任何数据库写入。

## 5. 本次执行值得沉淀的经验或者模式

1. fail-closed 不只检查稳定响应，还要检查“状态尚未解析”的瞬间；`undefined` 不能默认等同 READY。
2. “有 Point 对象”不等于“有可展示值”。availability 应由可发布值、许可和时点共同决定。
3. 同一 taxonomy 必须共享结构校验器；仅校验叶子 owner 无法防止中间节点重挂导致 API 分叉。
4. 单元测试覆盖全部枚举不等于浏览器能力门禁已端到端覆盖，尤其是凭据和许可状态。
5. 脏主工作区可以安全集成：把 Git 元数据入口与写入 worktree 分开，所有产品命令显式绑定隔离路径。
6. 在集成前保存基线门禁快照，能把历史 lint/type 债务、平台编码问题和候选语义缺陷明确分层。

## 6. 问题解决后反推的一条更好的初始提示词

> 请让 Live 数据浏览器始终显示 registry 中的 61 项深层目录，但任何 pending 指标在浏览器尚未确认
> 状态、缺映射、缺凭据或待许可时，都不得请求详情、观测、分析、导出或 AI 接口。availability 只有
> 在存在至少一个可展示数值且许可通过时才能是 available。让 taxonomy 树接口和 series browser
> 共用同一个经过 registry 父子结构、owner 和 61 项集合校验的投影；任一漂移统一返回 503。为深链
> pending 状态、全空值观测、节点重挂、待凭据和待许可增加后端、Web 与 Chromium 回归。完成后在
> 独立 worktree 运行定向和全量门禁，提交报告，不 push 或部署。

## 7. 当前场景是否有更优方案及一次解决的更优提示词

更优方案是在目录 read model 边界建立一个不可绕过的 `ValidatedCatalogProjection`：加载时一次验证
双 registry、数据库 canonical set、完整父子图、唯一 owner 和数据 binding，再由 taxonomy children、
series browser、facets 和 counts 共同消费。前端引入显式 `unknown | catalog_only | data_ready`
能力状态机，`unknown` 与 `catalog_only` 都关闭数据请求；这样不会依赖多个组件各自推断 readiness。

> 请把后端目录发布建模为单一 `ValidatedCatalogProjection`，它必须在返回任何 Live 目录前验证
> 61 项 canonical set、完整 taxonomy parent graph、唯一叶子 owner、唯一 verified data binding、许可
> 和可展示 Point；树、列表、筛选、计数全部只能从该投影派生。前端把选中指标状态建模为 unknown、
> catalog_only、data_ready 三态，只有 data_ready 能启用 detail/analytics/observations/export/AI。
> 用固定深链直接打开 pending 指标、全 None 观测、中间节点重挂、缺凭据和待许可五组回归先做 RED，
> 再实现 GREEN；最后在一次性 PostgreSQL 中 seed 两次验证幂等，并运行全量后端、Web、build 和
> Chromium 门禁后再交付。
