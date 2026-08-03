# ML-20260804-001 研发部 02 前端交付报告

## 1. 本次遇到的问题以及场景

现有 `/data` 是一个同时承担搜索、列表、图表、详情、修订和下载的大型客户端页面，无法表达用户确认的“指标树纵向贯穿、分析区横跨表格与详情”结构，也没有聚合浏览接口、可分享 URL 状态、快照一致性、移动抽屉和区域级失败隔离。此次工作需要在不修改 AppShell 品牌、不删除旧版、不绕过许可的条件下，为后端新增契约准备完整的新数据浏览器前端。

## 2. 分析这个问题的过程

先读取组织规则、任务卡与 580 行完整计划，并打开中文字符图和 1536×1024 视觉参考。随后检查旧 `/data`、AppShell、全局 token、图表、API 客户端、类型、收藏、对比、AI、Vitest 和 Playwright。基线显示 Web lint 已有 62 个错误/5 个警告，Vitest 有配置 ESM 启动问题，typecheck 有 1 个测试类型问题；这些均在实现前记录。实现中与后端研发和主线程同步契约，按安全预审把选中指标导出改为认证的 `/series/{id}/export`，并确保 AI 跳转与创建任务携带 `data_as_of`。

## 3. 解决问题的工作流程

1. 把旧页面原样迁移为 `legacy-data-page.tsx`，增加 `NEXT_PUBLIC_DATA_BROWSER_V2`，关闭时普通用户继续旧版，管理员可 `?view=v2` 预览。
2. 建立严格的 taxonomy children、series browser、analytics、capability、facet、revision 和 Problem Details 类型；让 API 客户端透传 `AbortSignal`，增加带刷新认证的二进制下载。
3. 新建 URL schema、格式化和 LTTB 可视降采样工具，再实现懒加载 ARIA tree、汇总表、详情和跨列分析区。
4. 接入收藏、对比、服务端导出、AI 快照、趋势、历史、修订、文档、统计和贡献不可用说明；刷新只检查无 cutoff 的最新快照，发现新数据后由用户显式切换。
5. 用 CSS 实现 `"tree table detail" / "tree analysis analysis"`；`>=1280px` 保持三列，1024–1279 使用抽屉，手机详情使用底部面板，并加入焦点陷阱、Escape、键盘树/行/标签操作和 reduced-motion。
6. 修复 Vitest ESM 配置与测试 setup，增加 URL、数值格式、树和表格组件测试；使用 Node 24 跑 typecheck、test 和生产 build。
7. 将 feature flag 加入 Docker 构建参数、根 Compose 和生产环境示例，保留默认关闭。

## 4. 使用的 Agents、Skills、Tools 以及读取的文档

- Agents：主线程 `/root` 负责任务统筹；`engineering_01` 提供后端契约同步；本席位 `engineering_02` 独立实现前端。未再派生子 Agent。
- Skills：`product-design:image-to-code`，并按其要求读取 Product Design index、user-context、critical overrides、communication protocol、local prototype preflight 与 design-qa；预检确认无持久化用户设计上下文。
- Tools：PowerShell/`rg`/Git 用于只读检查与验证，`apply_patch` 用于全部代码和文档修改，`view_image` 打开两张设计依据图，协作消息用于接口和安全约束同步。
- 文档：根 `AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`、任务卡、完整实现计划、用户确认字符图、1536×1024 参考图，以及相关前端源码、后端路由和部署环境示例。

## 5. 值得沉淀的经验或模式

- 数据浏览器必须用一个快照键同时驱动列表、分析、导出和 AI；手动刷新应先无 cutoff 检查新快照，再由用户显式切换，不能静默破坏研究上下文。
- 树选择和分页表格不是同一个状态空间。树叶选择应同时定位节点和可检索代码，避免下一次分页响应把选中项重置成首行。
- Feature flag 属于 Next.js 构建期契约，除了页面逻辑，还必须进入 Docker build ARG 和部署环境示例。
- 视觉结构、数据能力和许可失败要独立建模；贡献不可用是正常产品状态，不应通过填 0 或绘制假图掩盖。
- 独立 worktree 使用指向外部目录的 `node_modules` 联接会触发 Turbopack 根目录安全检查；生产构建必须使用工作树内真实安装。

## 6. 更好的初始提示词

> 请在现有 MacroLens 项目中实现新版 `/data` 数据浏览器：保留 AppShell 和旧版回退，字符图决定布局，1536×1024 截图决定密度。先读取项目规则和现有 API，再建立严格 TS 契约与 feature flag。桌面 `>=1280px` 必须是指标树、明细表、详情三列，树贯穿上下两行，分析区横跨表格与详情；窄屏使用抽屉和底部详情面板。URL 保存全部筛选、排序、分页、选中项、标签、变换、范围和 `data_as_of`。接通真实 browser/analytics/taxonomy/export/AI capability API、收藏、对比和 AI；所有授权相关 query key 包含用户上下文，导出必须走服务端许可校验。完成键盘、ARIA、错误隔离、组件测试、Node 22+ typecheck/test/build，并保留旧版一个发布周期。

## 7. 更优方案反思及一次解决的提示词

更优的执行方式是后端先提交并导出 OpenAPI/SDK 契约，前端在同一提交 SHA 上生成类型和固定 fixture，再用 MSW 或路由拦截运行五视口视觉 QA。此次并行开发依赖计划中的 JSON 约定，虽然通过消息对齐字段，但集成时仍需一次契约差异检查；同时独立分支没有运行中的新后端与认证数据，完整设计截图必须在集成后完成。

> 请先在一个集成分支完成数据浏览器后端契约与固定测试 fixture，生成 OpenAPI 和 TypeScript 类型；然后实现受 `NEXT_PUBLIC_DATA_BROWSER_V2=false` 保护的 `/data` 新版。用 fixture 登录管理员，在 1536、1280、1024、768、390 五个视口逐一验证树、筛选、表格、详情、趋势、历史、修订、文档、贡献不可用、许可受限和抽屉状态，并把每次截图与两张源图同视口比较，直到 `design-qa.md` 为 `final result: passed`。最后运行全仓检查，区分既存基线与新增错误，只提交可 cherry-pick 的前端实现和报告，不切换生产默认 flag。

## 交付状态与检查

- 席位状态：`REVIEW`
- 起始提交：`b5ab5ed3cb2eec553bba4c4bc878c3abec5d0da8`
- Node 24.14.0 `npm --workspace apps/web run typecheck`：通过。
- Node 24.14.0 `npm --workspace apps/web run test`：6 个文件、15 个测试全部通过。
- Node 24.14.0、`NEXT_PUBLIC_API_URL=/api/v1` 生产 build：通过，`/data` 静态路由生成成功。
- 变更路径定向 ESLint：通过。
- 全量 Web lint：仍为既存基线失败，现为 55 errors/4 warnings；实现前为 62 errors/5 warnings，本次未新增 lint 错误。
- `git diff --check`：通过。
- 截图能力与风险：参考图已打开，响应式实现和生产构建可运行；由于本工作树没有包含新后端契约、认证 fixture 和本地 API 实例，未生成可代表最终集成状态的实现截图。集成后必须由 Quality 在相同视口捕获并完成根 `design-qa.md`，前端提交本身不宣称视觉 QA 已通过。
