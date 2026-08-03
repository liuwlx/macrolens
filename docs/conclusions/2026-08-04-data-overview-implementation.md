# 数据概览重构实现工作报告

## 1. 本次问题与场景

本次任务把 MacroLens 现有 `/data` 数据概览重构为已确认的“指标树 + 明细表 + 指标详情 + 分析区”数据浏览器。视觉以 1536×1024 参考图为准，布局以用户确认的字符图为准，同时必须保留现有 MacroLens AppShell、登录态、工作区和产品导航。

这不是单纯的静态页面复刻。筛选、树、分页、排序、详情、历史、修订、收藏、对比、导出和 AI 上下文都需要真实合同；数值读取还必须遵守 `data_as_of`、唯一主数据源、append-only vintage、许可用途和账号缓存隔离规则。页面必须在 1280px 桌面、1024/768px 中屏和 390px 手机端可用，并保留旧版回滚入口。

## 2. 分析过程

1. 先读取组织规则、工程约束、既有页面、类型、API、测试和设计系统，冻结任务卡、视觉源、结构源和成功标准。
2. 把问题分成后端读模型/合同、前端信息架构/交互、集成、安全、质量和视觉验收六条证据链，而不是让截图复刻掩盖数据语义。
3. 后端追踪 `data_as_of` 到 `ObservationVintage` SQL，检查唯一主源 0/1/>1、display/download/AI 许可、导出预检、AI 幂等和 RFC 9457 错误。
4. 前端追踪 URL 状态、React Query 身份边界、树懒加载、表格分页/排序、详情联动、抽屉和 feature flag。
5. 首轮复核发现静默 latest、匿名数值读取、全量历史先加载后分页、账号缓存串用、AI 许可/配置和跨页排序等问题，分两轮整改后重新集成。
6. 浏览器验收不只看截图：先在同一状态把参考图和实现图放入一张对照图，再量测根页面、内部滚动容器、分析区位置和控制台；由此发现并关闭了 390px 根级横向溢出。

## 3. 解决流程

### 后端

- 新增 taxonomy children、series browser/export、series analytics/export 和 AI capability 合同，并同步 SDK/Web 类型。
- 数值查询按 `data_as_of` 从 append-only vintages 选每期最后版本；历史、修订、browser、analytics、export 和 AI series context 共用冻结快照语义。
- 主源 resolver 对 0 条返回 not-ready、1 条返回唯一来源、2 条及以上返回 `409 source_mapping_conflict`。
- 五种动态排序 `current_period/current/change/period_change/yoy` 使用批量窄窗口生成全局稳定 sort key，先排序分页，再只为页内来源加载最多 420 点。
- 导出在写入任何字节前完成全量 `download_allowed` 预检；AI 文档上下文使用严格许可；历史不可复现上下文 fail closed；AI run 使用 `Idempotency-Key`。

### 前端

- 按参考结构完成筛选带、懒加载指标树、明细表、详情列和跨列分析区，保留 MacroLens AppShell。
- URL 保存筛选、树节点、指标、分页、排序、tab 和 `data_as_of`；刷新与回退可复现状态。
- 收藏、对比、导出、AI 上下文、历史、修订、相关文档和说明均有实际交互。
- 1024px 以下将树、筛选和详情切换为抽屉/底部面板；390px 表格与 tabs 保持内部横向滚动，根页面不再横向溢出。
- `NEXT_PUBLIC_DATA_BROWSER_V2` 和管理员 `?view=v1|v2` 保留旧版回滚通道。

### 集成与验收

- 研发候选由 Integration/Release 分阶段 cherry-pick；两轮后端整改和两轮前端布局整改均有独立提交、报告和 focused gate。
- 最终 Quality：PASS，功能/视觉 P0=0、P1=0；26 项后端 focused tests、17 项 Web tests、typecheck、build、changed-path lint、SDK typecheck、compileall 和四视口 Chromium overflow E2E 全部通过。
- `design-qa.md` 末行严格为 `final result: passed`；同状态源图/实现对照和各视口截图已提交到 `artifacts/design-qa/`。
- 本地验收运行于 `http://localhost:3000/data`，使用固定 mock API 快照，便于稳定复核界面和主交互；未切换生产 feature flag，未部署服务器。

## 4. Agents、Skills、Tools 与文档

### Agents

- `/root`：任务冻结、跨席位协调、浏览器视觉/交互 QA、本地验收和最终收口。
- `engineering-01`：后端合同、批量查询、快照/许可、主源与全局排序整改。
- `engineering-02`：前端页面、响应式交互、缓存隔离和移动端 overflow 整改。
- `integration-release-01`：候选集成、冲突/副作用清理、门禁和资产白名单提交。
- `quality-01`：Standards/Spec 双轴审查、focused 测试和最终 PASS。
- `security-01`：许可、快照、导出、AI 和缓存审查；正式 Codex Security Start scan 工具门禁未返回 authoritative scan id，报告保持 REVIEW/INCOMPLETE，但不构成新的代码 finding。

### Skills

- `gpt-plan`：形成完整实现计划和冻结边界。
- Product Design `image-to-code`：以视觉源/结构源为真值执行实现与 `design-qa.md` 验收。
- `browser:control-in-app-browser`：在用户选定的内置浏览器中执行真实视口、交互、URL、DOM、console 和截图验证。
- `code-review`：Quality 将 Standards 与 Spec 分轴复核。
- `codex-security:security-diff-scan`：Security 打开扫描工作区；Start scan 未触发，按工具门禁单独记录。

### Tools

- `apply_patch`：所有源码、任务卡、QA 和结论报告编辑。
- `exec_command` / `write_stdin`：Git、Python/Node 门禁、本地服务和端口检查。
- Node REPL browser、`view_image`：真实浏览器自动化、截图保存、源图/实现同图对照。
- 协作 Agent、plan 工具：隔离工作树、交付回执和执行计划维护。

### 读取的主要文档

- 根 `AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`。
- 完整 task card、实现计划、字符图复核文档、各部门报告。
- `docs/security.md`、`docs/licensing.md`、后端/前端配置、测试和类型合同。
- 两张用户参考图、Product Design critical overrides 和浏览器控制说明。

## 5. 值得沉淀的经验与模式

1. URL 中出现 `data_as_of` 不代表快照成立；必须追到 Router 参数和最终 vintage SQL。
2. 全局排序与页内昂贵历史加载可以分离：先批量计算窄 sort key，分页后再取完整历史。
3. “唯一来源”不能用 `.first()` 消解冲突；最多读两条即可低成本区分 0/1/>1 并 fail closed。
4. 账号级 React Query 数据既要在 key 中带身份，也要在身份变化时清空旧缓存。
5. 响应式验收必须同时量测 root `scrollWidth` 和内部滚动容器；截图看不到的根级 overflow 仍会破坏手机体验。
6. 视觉复刻要用同一指标、同一树展开状态和同一视口比例对照；既有产品壳属于显式约束，不应为贴图而替换。
7. Next dev/build 会改写 `tsconfig.json` 并生成 `next-env.d.ts`；门禁后要精确清理，不能把工具副作用混入业务提交。

## 6. 更好的初始提示词

> 请按我提供的桌面参考图和字符结构图，把 MacroLens 的 `/data` 重构成完整可运行的数据浏览器，并保留现有侧边栏、顶栏和登录体系。桌面要有筛选带、懒加载指标树、明细表、指标详情和下方趋势/历史/修订/文档/说明；1024、768、390px 要用抽屉或底部面板且根页面不能横向滚动。所有数值、排序、分页、详情、导出和 AI 上下文必须使用同一个 `data_as_of` 快照，唯一主源冲突与许可缺失要拒绝，导出和 AI 必须服务端校验。收藏、对比、分页、排序、tab、URL 恢复和旧版回滚都要能操作。请先冻结任务卡，分后端/前端隔离实现，再做安全、质量和源图同状态视觉对照；提交 `design-qa.md`、四视口截图、完整门禁结果和一个本地可点击验收链接，不要切生产开关或部署。

## 7. 更优方案反思与一次解决提示词

当前方案已满足本次范围，但 browser sort 和完整 points query 仍重复 latest-vintage ranked 子查询，长期存在语义漂移风险；真实 PostgreSQL、WebKit/Firefox 和完整仓库历史 lint 债也不应混进本次 UI 改造。更优方案是先建立统一的认证 `SeriesSnapshotReadModel`，再让 browser、trend、revisions、analytics、export 和 AI 只通过该模型读取，并从 OpenAPI 自动生成 SDK/Web 类型。

> 请先实现并验证一个认证、工作区隔离、许可感知的 `SeriesSnapshotReadModel`：输入 actor/workspace、tree identity、filters、sort、pagination 和 `data_as_of`，输出唯一主源、有效用途许可、latest-as-of vintages、facets、全局排序键和分页行。browser、trend/history/revisions、analytics、export、AI context 禁止绕过该模型。先写 PostgreSQL 集成测试覆盖 cutoff 前后 vintages、0/1/2 主源、display/download/AI 许可矩阵、五种跨页排序、10k 指标查询数/P95，再由 OpenAPI 生成 SDK/Web 类型；随后实现确认的三栏 UI、URL 状态、完整树键盘、抽屉、错误反馈、Chromium/Firefox/WebKit 四视口 E2E 和同状态视觉对照。任何匿名数值、静默 latest、分页后全局排序、全量许可未预检、账号缓存串用或根页面横向 overflow 都阻断交付。
