# ML-20260804-001 前端返修 01 工作报告

## 1. 问题与场景

在 1536×1024 桌面验收视口中，当前数据概览页的下方分析区约从 y=699 开始，首屏表格约能看到 8 行；参考图的分析区约从 y=750 开始，表格区域更高。任务要求只修正 `>=1280px` 桌面布局的工作区首行高度，不改变平板、移动端、列宽、AppShell 或交互功能。

## 2. 分析过程

检查 `apps/web/app/globals.css` 后确认：默认 `.data-browser-workspace` 使用 `440px` 首行；`max-width:1279px` 使用 `470px`；`max-width:767px` 使用 `500px`。默认规则正是桌面端入口。把默认首行增加 60px，可将既有 y≈699 的分析区边界理论上推到 y≈759，接近参考图 y≈750，同时不影响两个窄屏媒体查询。

## 3. 解决流程

1. 核对组织规则、任务卡、基线提交和当前 worktree。
2. 仅将桌面默认规则的 `grid-template-rows` 从 `440px minmax(300px, auto)` 改为 `500px minmax(300px, auto)`。
3. 再次检查三处响应式规则，确认平板 `470px auto`、移动端 `500px auto` 未变化。
4. 使用 Node.js v24.14.0 安装锁定依赖，并运行类型检查、测试、生产构建和变更路径 lint。
5. 清理 Next.js 构建自动生成的 `next-env.d.ts` 以及对 `tsconfig.json` 的自动格式化，确保候选提交只保留目标样式和本报告。
6. 执行 `git diff --check` 并检查最终差异。

## 4. Agents、skills、tools 与文档

- Agents：研发部席位 `engineering-02`；来源主线程 `/root`。本次返修未派生其他子 Agent。
- Skills：桌面高度与移动溢出返修直接依照任务卡执行；P0 跨账号缓存修复使用 `codex-security:fix-finding`，先复现泄露再修复并复跑回归用例。
- Tools：`exec_command` 用于只读检查、依赖安装和验证；`apply_patch` 用于 CSS 修改、构建生成物清理及报告创建。
- 已读文档：`.codex/organization.toml`、`docs/organization/README.md`、`docs/conclusions/tasks/ML-20260804-001/task-card.md`，以及目标样式文件 `apps/web/app/globals.css`。

## 5. 值得沉淀的经验

- 视觉位置偏差若能归因到明确的网格轨道，应优先修正单一布局变量，避免联动调整列宽、内边距和组件结构。
- 响应式 CSS 返修必须同时核对默认规则与所有覆盖规则，才能证明变更只影响目标断点。
- Next.js 构建可能自动改写 TypeScript 配置；提交前应清理生成差异，防止一次视觉修复夹带无关变更。
- 当前 ESLint 配置不解析 CSS。变更路径命令退出码为 0，但 CSS 质量主要由构建、差异检查和后续视觉验收保障；若需要真正的 CSS lint，应单独引入 Stylelint，而不是在本次窄范围返修中扩展工具链。

## 6. 更好的初始提示词

> 在 1536×1024 浏览器中，数据概览页下方分析区现在约从 y=699 开始，参考图约从 y=750 开始。请只把 `>=1280px` 桌面端数据浏览器工作区首行从 440px 调为 500px；不要修改 `<=1279px` 的 470px 规则、移动端 500px 规则、列宽、AppShell 或任何交互。使用 Node 24 运行 Web typecheck、现有测试、生产 build、变更路径 lint 和 `git diff --check`，清理构建生成物后提交。

## 7. 更优方案与一次解决提示词

当前方案已经是本场景风险最低的最小修复。更优之处在于把视觉测量、断点边界、允许修改的唯一属性及验证命令一次写清，并要求提交前证明窄屏规则未变：

> 基于已确认的 1536×1024 实测结果，修改 `apps/web/app/globals.css` 中默认 `.data-browser-workspace`：只将第一行 `440px` 改成 `500px`。修改后输出三处 `grid-template-rows` 的最终值，必须分别为桌面 500px、平板 470px、移动端 500px；预计分析区起点从约 699px 下移到约 759px。不要动任何其他视觉尺寸或功能。用 Node 24 完成 typecheck、全量现有 Vitest、production build、CSS 变更路径 lint 与 `git diff --check`，移除 Next.js 自动生成差异，只提交目标 CSS 和结论报告。

## 验证结果

- Node.js：v24.14.0。
- `npm --workspace apps/web run typecheck`：通过。
- `npm --workspace apps/web run test`：通过，8 个测试文件、17 条用例全部通过。
- `NEXT_PUBLIC_API_URL=/api/v1 NEXT_PUBLIC_DATA_BROWSER_V2=false npm --workspace apps/web run build`：通过，15 个页面路由生成成功。
- `npm --workspace apps/web exec -- eslint app/globals.css --no-warn-ignored`：退出码 0；仓库当前无 CSS parser，限制见上文。
- `git diff --check`：通过。
- 补充发现：全仓 Web lint 仍有基线遗留的 55 errors / 4 warnings，均位于未修改的 TS/TSX/MJS 文件；本返修未扩大范围处理。

## 风险与兼容性

变更仅影响宽度不小于 1280px 的数据浏览器工作区纵向尺寸，不改变数据请求、状态、交互、桌面列宽或窄屏抽屉规则。最终像素位置仍应由集成后的 1536×1024 浏览器截图复验。

## Remediation 02/03 补充报告

### 1. 问题与场景

- 移动端：390×844 实测 `documentElement.scrollWidth=545`，宽度 690px 的 `.data-browser-table` 把最小内容宽度传播到页面，产生页面级第二条横向滚动条；表格自身已有正确的内部滚动条。
- 安全：应用级 React Query `QueryClient` 跨退出/登录持续存在，默认 `staleTime` 为 30 秒。`AuthProvider` 切换用户时没有清理缓存，AI runs、citations、saved views、notes 又使用固定查询键，因此账号 B 可直接渲染账号 A 的新鲜缓存。

### 2. 分析过程

移动端 DOM 路径是 `.data-browser-table-card > .data-browser-table-wrap > .data-browser-table`。宽表本身需要保留 690px 最小宽度，正确边界应由卡片和 wrapper 收缩到单列 grid，再由 wrapper 的 `overflow:auto` 承担横向滚动。

安全路径是 `Providers` 创建长期存活的 `QueryClient`，随后 `AuthProvider` 直接 `setUser`。在修复前的回归测试中，A 的 `ai-runs` 缓存保持 fresh；退出并登录 B 后，组件已显示 B 的邮箱，但仍显示 `user A confidential run`，证明漏洞可达。最窄且覆盖全站私有查询的边界是在每次身份或角色变化时、暴露新 `user` 前同步 `queryClient.clear()`，并对 AI 页四组明确的私有查询增加用户 ID 作为纵深隔离。

### 3. 解决流程

1. 先加入跨账号缓存回归测试和 CSS 容器规则测试，确认两者在修复前失败。
2. 为 table card 和 wrapper 增加 `min-width:0; width:100%; max-width:100%`；card 隐藏外溢，wrapper 保留 `overflow:auto`，宽表的 690px 移动规则不变。
3. `AuthProvider` 使用 `useQueryClient` 和当前用户 ref 检测用户 ID/角色变化；先调用 `queryClient.clear()`，再更新 ref 与 React user state。
4. login、register、logout、refresh 成功或清除身份的所有路径统一经过该身份暴露函数。
5. AI runs、citations、saved views、notes 查询键加入 `user.id`，create/cancel run 的 invalidation 使用同一身份化 key。
6. 复跑两条回归测试，确认 B 只看到 B 的 AI 记录，宽表仍为 690px 且滚动被 wrapper 收纳。
7. 执行 Node 24 typecheck、完整 Vitest、变更路径 lint、production build 与 `git diff --check`。

### 4. Agents、skills、tools 与文档

- Agents：研发部席位 `engineering-02`；来源主线程 `/root`；未派生子 Agent。
- Skill：`codex-security:fix-finding`，用于建立漏洞路径、安全不变量、修复边界和前后回归证据。
- Tools：`exec_command`、`apply_patch`。
- 文档与代码：追加后的任务卡、`.codex/organization.toml`、`docs/organization/README.md`、`components/providers.tsx`、`components/auth-provider.tsx`、`components/auth-gate.tsx`、AI 页面、全局样式和现有 Vitest 配置/测试先例。

### 5. 值得沉淀的经验

- 私有 React Query 数据不能只依赖 cookie 隔离；缓存生命周期必须显式绑定身份。全局身份切换清理负责完整性，查询键身份化负责纵深隔离。
- 清理必须发生在 `setUser(nextUser)` 之前，否则新身份至少有一帧可能观察旧缓存。
- 对宽表不要取消其业务所需的最小宽度；应把外层 grid/flex item 设置为可收缩，并把 overflow 边界固定在内部 wrapper。
- 安全回归应使用 fresh cache 和真实身份切换时序，确保删除清理逻辑后测试确实重新失败。

### 6. 更好的初始提示词

> 在现有数据概览返修分支继续修复两项问题：一是 390×844 下页面宽 545px，`.data-browser-table` 为 690px，要求页面 `scrollWidth` 回到 viewport，但表格内部仍可横向滚动；二是 React Query 的全局缓存会跨账号保留 30 秒，要求 login/register/logout/refresh 的身份变化在暴露新 user 前清除缓存，并将 AI runs、citations、saved views、notes 查询键及 invalidation 加入 user ID。先分别写会失败的回归测试，再做最小修复，使用 Node 24 运行 typecheck、全量 Vitest、changed-path lint、build 和 diff check。

### 7. 更优方案与一次解决提示词

> 请把“页面滚动边界”和“身份缓存边界”作为两个明确不变量实现：移动端 table card/wrapper 必须 `min-width:0` 且不超过 grid 列宽，只有 wrapper 允许 `overflow:auto`，内部 table 保持 690px；身份切换函数必须按 `clear QueryClient → 更新身份 ref → setUser` 的顺序执行，并覆盖 login/register/logout/refresh，AI 四组私有 key 统一包含 `user.id`，所有 mutation invalidation 复用相同 key。测试必须证明：删除 CSS 约束会失败；删除清缓存会重现“页面显示 B 身份但仍渲染 A run”；合法路径则能在切换后请求并显示 B run。

### 补充验证结果与剩余风险

- 修复前证据：缓存测试显示 B 邮箱与 A run 同屏；布局规则测试确认 table card 未声明 `min-width:0`。
- 修复后聚焦测试：2/2 通过；完整 Web 测试：8 files / 17 tests 通过。
- Node 24 typecheck、变更路径 ESLint、production build、`git diff --check` 均通过。
- 安全不变量已由真实 React Query provider、30 秒 fresh cache、logout/login 时序验证；合法 B 数据会重新请求并显示。
- 移动 CSS 不变量由样式规则测试锁定；最终 `document.scrollWidth === innerWidth` 仍需集成环境在 390×844 真实浏览器复测，因为本 worktree 未连接完整运行中的 API 会话。
- 全仓 Web lint 仍有既有 55 errors / 4 warnings；变更路径 lint 已通过，本次未扩展修复未触及文件。
