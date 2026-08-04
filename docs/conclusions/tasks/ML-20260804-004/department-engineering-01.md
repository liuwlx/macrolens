# ML-20260804-004 Engineering-01 工作报告

## 1. 问题与场景

数据浏览器的指标树只把 `has_children=true` 的分类视为可展开节点，导致“没有子分类、但自身直接挂载指标”的叶子分类无法展开。与此同时，前端没有区分 live 与 demo 数据，也没有把 `not_ingested` 当成正常业务空态：无观测的指标会错误固定 `data_as_of`，DEMO 页面缺少持续提示和写操作限制，导出文件也没有明确的 DEMO 标记。全局搜索还需要在深层树中保留祖先路径，并保持既有响应式布局。

## 2. 分析过程

首先沿真实 UI/API 边界检查 `MetricTree`、`DataBrowserPage`、`BrowserTable`、`SeriesDetailPanel`、`AnalysisPanel` 和公共响应类型。定位到树节点的点击、caret、`aria-expanded`、ArrowRight 四处都只判断 `has_children`；页面副作用无条件使用 browser 响应的 `data_as_of`；表格只区分请求失败与零行，没有 item 级 availability；DEMO 模式也没有驱动 UI 权限。

随后核对 compare 页面：数据页“加入对比”只是 URL 导航，`/compare/query` 是无持久化的分析计算，真正写入发生在保存视图接口，因此 DEMO 中保留只读比较，只禁用收藏、工作台和 AI 等业务写入。公共类型最终与架构契约对齐：browser/taxonomy/analytics 顶层 `data_mode`，observation 使用 `meta.data_mode`，browser item 的 `availability` 必填。

## 3. 解决流程

1. 先写 RTL 红灯：构造 `has_children=false`、`direct_series_count=1` 的分类，点击后必须请求 `parent_id` 并在下一 `aria-level` 渲染指标。
2. 用统一 `expandable = has_children || direct_series_count > 0` 驱动点击、caret、ARIA 和 ArrowRight，保持展开集合与筛选状态相互独立。
3. 先写 `not_ingested` 红灯，再在明细表中显示“尚未采集”；只有存在 `availability=available` 且有 current observation 时才固定快照。
4. 新增页面级 Playwright RED/GREEN：DEMO 固定快照覆盖旧 live URL、持续 banner、写入口禁用并解释、趋势/历史/修订/统计/只读比较可用、CSV 文件名与 `data_mode` 列标记 DEMO。
5. 用三层祖先分类加直系指标的非空 Demo API 响应验证全局搜索保留四级路径，不扁平化。
6. 复跑组件、类型、lint、production build，以及 390/768/1280/1440/1920/2560 六档响应式验收；移除 Next 自动生成的 `next-env.d.ts` 并恢复自动改写的 `tsconfig.json`。

## 4. Agents、skills、tools 与文档

- Agent：`/root/engineering_01`，未使用子 Agent。
- Skill：`tdd`；完整阅读 `SKILL.md`、`tests.md`、`mocking.md`，按真实组件与 HTTP/API 边界执行 RED→GREEN。
- Tools：`exec_command`/`write_stdin` 用于检索、测试、lint、类型检查、构建和 Playwright；`apply_patch` 用于全部代码、测试和报告修改；协作消息用于同步架构契约和里程碑。
- 文档：项目 `AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`；并阅读相关 Web 组件、类型、API、Playwright 配置和既有 E2E。

## 5. 值得沉淀的经验与模式

- 树节点的“可展开性”是领域派生值，不应在 caret、键盘、ARIA、点击中分别手写条件；统一派生值可以避免交互和无障碍语义漂移。
- “目录存在但数据未采集”不是网络错误，也不等于搜索无结果；availability 必须作为 item 级业务状态贯穿 API、类型和 UI。
- 快照固定应以实际可用观测为前置条件；无观测时自动写 URL 会制造不存在的研究上下文。
- DEMO 是数据来源模式，不应粗暴关闭所有分析。只读分析、历史与导出可用，持久化写入明确禁用，且服务端仍以 `409 demo_read_only` 兜底。
- 搜索树验收应使用非空多层契约数据并断言每层 `aria-level`，否则空树或扁平 fixture 无法发现祖先路径回归。

## 6. 更好的初始提示词

请修复数据浏览器中“叶子分类自身挂有指标却无法展开”的问题：用真实页面/API 边界先写失败测试，确保 `has_children=false` 但 `direct_series_count>0` 的分类可通过点击和 ArrowRight 展开，caret 与 `aria-expanded` 一致，指标显示在下一层。还要让 `not_ingested` 显示“尚未采集”且不把 `data_as_of` 写入 URL；按 API 的 `data_mode` 实现 DEMO 固定快照、持续提示、只读分析可用、收藏/工作台/AI 写入禁用并解释，CSV 文件名含 `.demo.csv` 且内容含 `data_mode=DEMO`。全局搜索必须保留多层祖先路径。最后跑组件测试、lint、typecheck、build 和 390–2560px 响应式 Playwright，并提交报告与 commit SHA。

## 7. 更优方案及其提示词

更优方案是先把数据契约和权限矩阵写成可执行验收表，再实现一个统一的前端派生模型：`expandable` 负责树交互，`hasUsableObservations` 负责快照，`dataMode/readOnlyReason` 负责写入口。这样能一次覆盖组件逻辑、页面副作用和无障碍语义，并由服务端 `409 demo_read_only` 做纵深防护。

更优提示词：请先依据最终 API 契约建立三组端到端 fixture（live available、live not_ingested、demo available）和一棵“3 层祖先 + 叶子直系指标”的搜索树，再以 TDD 实现三个统一派生规则：`expandable=has_children||direct_series_count>0`、仅有可用 current observation 才固定快照、DEMO 仅禁用持久化写入并保留只读分析/比较/CSV。所有按钮必须有明确禁用原因，observation 的模式字段使用 `meta.data_mode`，DEMO 写接口契约为 `409 demo_read_only`。验收 URL、副作用、ARIA 层级、下载文件名与 CSV 内容，并复跑全量 Web 检查和六档响应式 E2E。

## 验证证据

- RED（树）：`vitest run components/data-browser/metric-tree.test.tsx` → 2 tests / 1 failed，找不到二级“居民消费价格指数”；GREEN → 2/2 passed。
- RED（availability）：`vitest run components/data-browser/browser-table.test.tsx` → 3 tests / 1 failed，找不到“尚未采集”；GREEN 与树测试合跑 → 5/5 passed。
- RED（页面）：首次 `data-browser-demo.spec.ts --project=chromium` → 3/3 failed，其中 `not_ingested` URL 错误出现 `data_as_of`；最终 → 3/3 passed。
- 全量 Vitest：8 files，21/21 passed。
- focused ESLint：通过，无输出。
- TypeScript：`tsc --noEmit` 通过。
- Next production build：编译、类型检查、15 个静态页面生成全部通过。
- Playwright：Demo/深树 3 条 + 六档响应式 6 条，共 9/9 passed。
- `git diff --check`：通过，仅有 Windows 行尾转换提示。
