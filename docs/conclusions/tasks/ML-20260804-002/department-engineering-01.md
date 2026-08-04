# ML-20260804-002 / Engineering-01 工作报告

## 1. 问题与场景

登录后的所有后台页面由 AppShell 承载，但主内容被 `max-w-[1720px]` 居中限制，在 2560px 超宽屏上左右形成大块无效留白。数据总览桌面网格又固定为 `500px / minmax(300px, auto)`，不能随高视口吸收剩余空间，页面底部出现明显空白。修复必须保留移动端 16px、桌面端 24px 内边距和 1280px 以下既有响应式行为。

## 2. 分析过程

先检查 AppShell 的侧栏、顶栏、主区宽度与 padding，确认宽屏留白来自 main 的最大宽度而不是数据表自身。随后逐项计算桌面视口中的顶栏 68px、main 顶部 24px、底部 32px，得到数据总览内容可用高度 `100dvh - 124px`。通过 Playwright 实测不同视口的 document width、main/page 边界、网格实际行高与底部间距，验证横向溢出和纵向填充，而非只依赖静态 CSS 断言。

## 3. 解决流程

1. 移除 AppShell main 的 `mx-auto max-w-[1720px]`，改为 `min-w-0 w-full`，保留 `p-4 md:p-6` 和既有底部 padding。
2. 为满足 React 19 lint，将渲染过程中声明的 Sidebar 提升为文件级组件；导航、折叠和移动端关闭行为不变。
3. 在 `min-width: 1280px` 下，把 `.data-browser-page` 设置为最小高度 `calc(100dvh - 124px)` 的纵向 flex 容器；workspace 使用 `flex: 1`，两行改为 `minmax(500px, 3fr) minmax(300px, 2fr)`，短视口由页面自然滚动。
4. 扩展 Vitest 静态契约，锁定 AppShell 无最大宽度、16/24px padding 和桌面网格约束。
5. 扩展 Playwright 到 390、768、1280、1440、1920、2560 六种宽度，验证根节点无横向溢出、表格局部滚动、内容边缘、最小行高、3:2 比例和底部空白。

## 4. Agents、skills、tools 与文档

- Agent：仅 `engineering-01`，未创建子 Agent。
- Skills：未使用额外 skill。
- Tools：`exec_command` 用于代码检索、Node 22 门禁、构建和 Playwright；`apply_patch` 用于全部白名单代码与报告修改；协作消息工具用于主线程同步；`update_plan` 用于进度管理。
- 阅读文档：工作树根 `AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`，以及主线程任务卡。

## 5. 值得沉淀的经验与模式

- 应由 AppShell 统一控制后台页面可用宽度；页面级组件只管理自己的内容网格，避免多层 max-width 叠加。
- 视口填充应把固定 chrome 与 padding 显式纳入 `dvh` 计算，同时用 `minmax` 保证短视口可滚动而不是压缩关键面板。
- 宽屏验收不能只检查 screenshot 主观观感，应同时断言根 scrollWidth、内容左右间距、网格实际行高和 viewport 底部差值。
- Next 构建可能自动改写 tsconfig 并生成类型文件；白名单任务提交前必须复核并清理构建副作用。
- Windows worktree 复用外部 node_modules junction 会被 Turbopack 拒绝；生产构建应在 worktree 内按 lockfile 安装依赖。

## 6. 更好的初始提示词

“请修复 MacroLens 登录后台的宽屏布局：移除 AppShell 1720px 最大宽度，移动端保持16px、桌面保持24px padding；数据总览在 >=1280px 时用扣除68px顶栏和main上下padding后的可用 `dvh` 填满视口，workspace 两行用最小500/300px且约3:2分配，短视口允许纵向滚动，<1280布局不变。请补 Vitest 和 390/768/1280/1440/1920/2560 Playwright，断言无根横向溢出、2560底部空白<=32px，使用 Node22 跑 lint/test/build，清理构建副作用后只提交白名单文件和报告。”

## 7. 更优方案反思与一次解决提示词

当前用明确的顶栏和 padding 常量计算高度，改动小且验证稳定。长期更优方案是把 AppShell 的顶栏高度和内容 padding 提升为 CSS custom properties，由 Shell 与各需填满视口的页面共享，避免未来 chrome 尺寸变化后手工同步 `124px`。

一次解决提示词：

“请为 MacroLens AppShell 建立 `--app-header-height`、`--app-content-padding-inline/block` 等布局变量，移除后台主区最大宽度，并提供通用 `.app-viewport-page` 容器。数据总览使用该容器和 `minmax(500px,3fr) minmax(300px,2fr)`；补覆盖折叠/展开侧栏和390至2560宽度的几何 Playwright 断言，确保无根横向溢出、宽屏边缘仅保留规定padding、底部空白<=32px。完成 Node22 lint/test/build、清理生成物、报告和独立提交。”

## 检查结果

- Node：通过隔离 Node `v22.23.1/v22.23.2` 执行门禁；系统默认 Node 20.11 不满足仓库 `>=22` engine。
- `npm --workspace apps/web run test`（Node 22）：8 files、19 tests 全部通过。
- `npm --workspace apps/web run build`（Node 22）：通过，15 个路由完成构建；自动生成的 tsconfig/next-env 变化已清理。
- 聚焦 ESLint：`app-shell.tsx`、布局 Vitest、布局 Playwright 全部通过。
- 全量 `npm --workspace apps/web run lint`：未通过，均为白名单外既有问题，共 52 errors / 4 warnings，主要是多个页面的 `react-hooks/set-state-in-effect` 和 `critical-path.spec.ts` 的 `no-explicit-any`；本次未越权修改。
- Playwright Chromium：390x844、768x1024、1280x844、1440x900、1920x1080、2560x1280，6 passed。
- 2560x1280 实测：document width 2560，无根横向溢出；page width 2290；左右内容间距各 24px；网格行高 593.094/395.391（约 3:2）；底部空白 32px。
- `git diff --check`：通过。

## 风险与兼容性

- 1280px 以下媒体规则未修改，390/768 Playwright 通过。
- `100dvh - 124px` 依赖当前 68px 顶栏及桌面 24/32px 上下 padding；未来调整 Shell chrome 时需同步，长期建议改为共享 CSS 变量。
