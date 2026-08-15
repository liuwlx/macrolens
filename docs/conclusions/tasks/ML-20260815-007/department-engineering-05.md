# ML-20260815-007｜GitHub acceptance 运行时根因修复

## 1. 问题与场景

PR #11 的 GitHub acceptance 在远程 Compose 环境完成迁移、seed、测试夹具、服务启动和 readiness 后，Playwright 出现两类真实后端失败：首个浏览序列没有修订历史；未显式传入 `data_as_of` 的 AI run 被判定为未来时间。工作流还声称只运行 Chromium，实际却执行了 mobile 项目，带来额外失败和登录重试噪声。本地环境按工程宪法禁止 Docker、Compose 和服务容器。

## 2. 分析过程

先固定失败运行 `31892643671` 和 acceptance job `95031504585`，读取完整日志并区分事实与推测。代码核对确认：运行时夹具只为 `series_index == 0` 的序列生成第二个 vintage，而 `/series` 的首项排序不保证是该序列；AI router 先记录 `request_started_at`，随后对空值调用内部 `datetime.now()`，必然可能晚若干微秒；根 npm script 把参数拼到 `npm --workspace ... run e2e` 的外层，Web workspace 实际日志仅显示 `playwright test`，因此 `--project=chromium` 丢失。mobile mock 用例不是本次 Chromium acceptance 的预期执行范围。

## 3. 解决流程

1. 扩充任务卡允许范围，但不改变本地容器、目标服务器迁移/seed/sync、映射和 Scheduler 禁令。
2. 先新增三组回归断言并得到 3 个后端 RED、1 个工作流静态 RED。
3. 给每个 acceptance fixture 序列在倒数第二期生成一个修订 vintage，并让 `IngestionRun.revised_count` 与序列数一致。
4. 新增 cutoff 解析 seam：缺省 `data_as_of` 直接复用请求开始时间，显式值仍走统一时区规范化和既有未来时间校验。
5. CI 改为直接执行 `npm --workspace apps/web run e2e -- --project=chromium`，并用静态测试锁定参数不会再经根脚本丢失。
6. 定向测试转为 36 passed；随后完成六门禁和 diff 检查。未启动本地 Docker/Compose/服务容器，未执行任何本地 migration、seed、sync、Provider Probe 或 Scheduler 操作。

## 4. Agents、skills、tools 与文档

- Agent：主线程负责后端根因、工作流、验证和交付；Hooke 曾被分配 mobile E2E 辅助调查，在确认工作流参数丢失后立即停止，未产生代码变更，也停止了其短暂启动的本机 Next.js 进程。
- Skill：`diagnosing-bugs`，用于固定失败运行、按假设排序、先 RED 后 GREEN、以最小反馈环验证根因。该技能促使本轮修复真实时间/夹具/参数转发契约，而非放宽断言。
- Tools：PowerShell 只读搜索与测试命令、`apply_patch`、Git/GitHub CLI、subagent 协作工具；没有使用 Docker/Compose 工具。
- 已读文档：`AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`、`docs/governance/development-constitutions/README.md`、阶段 01/02/03 宪法、任务卡、GitHub acceptance 日志，以及相关 AI router、运行时夹具、Playwright 配置和 npm scripts。
- 执行阶段：阶段 01 修复与本地冻结完成；阶段 02 等待提交、push 和 GitHub CI；阶段 03 尚未开始本轮新候选的目标服务器部署。

## 5. 值得沉淀的经验或模式

- “命令文本含参数”不等于子进程收到参数；多层 npm script 必须从实际日志的最终命令验证参数传递，并用静态契约锁住。
- 验收夹具不能依赖未声明的列表排序；凡断言任意首项具备能力，夹具就应让每个候选项满足能力，或显式固定选择键。
- 请求级默认时间必须只采样一次。先采样请求开始时间，再调用另一个 `now()` 作为缺省 cutoff，会制造稳定可复现的微秒级竞态。
- 先区分真实产品失败、夹具失败和意外执行范围，能显著减少重试造成的级联认证噪声。

## 6. 更好的初始提示词

> 继续修复 PR #11 的 GitHub acceptance，先读 AGENTS、组织规则和 01→03 宪法。固定最新失败 run/job，逐项从日志确认实际执行命令和首个失败；为每个根因先加最小 RED 回归测试，再修复到 GREEN。重点检查运行时夹具是否依赖 `/series` 未保证的排序、AI 缺省 `data_as_of` 是否复用了同一个请求开始时间，以及根 npm script 是否真的把 `--project=chromium` 传给 Web Playwright。完成六门禁、报告、提交和 push；本地禁止 Docker/Compose/服务容器，目标服务器禁止 migration、seed、sync、映射改动和 Scheduler 重启。

## 7. 更优方案反思与提示词

当前最小方案正确且风险低。长期更优的是把请求时间冻结做成统一依赖，由所有 snapshot API 共享；让 acceptance fixture 通过显式 canonical code 清单建立确定性能力矩阵；CI 直接调用最终工具，避免脚本多层转发。该结构化改造会跨多个 API 和测试，本次不应扩大。

> 将 MacroLens 的运行时验收做成确定性契约：统一注入一次请求开始时间并让所有 `data_as_of` 缺省值复用；夹具按显式 canonical code 能力矩阵生成，每个入选序列都具备浏览、修订和血缘所需数据；GitHub workflow 直接调用 Web workspace 的 Playwright 并为 project 参数写静态测试。先列出受影响接口与不变量，逐项 RED/GREEN，跑六门禁和远程 acceptance；严格禁止本地容器及目标服务器 migration、seed、sync、映射和 Scheduler 变更。
