# ML-20260804-001 Web Remediation 02 工作报告

## 1. 问题与场景

390px 浏览器中 `innerWidth=390`，但 `documentElement.scrollWidth=545`，页面底部出现第二条全局横向滚动条。表格 wrapper 已是正确的内部滚动容器（约 326/690px，`overflow-x:auto`），但宽表及 sticky 单元格的溢出仍从数据浏览器页面传播到根文档。

## 2. 分析过程

检查集成基线 `79e65c` 后确认，table card 已有 `min-width:0` 与 `overflow:hidden`，table wrapper 已有 `min-width:0`、宽度约束和 `overflow:auto`，移动端 tabs 也已有 `overflow-x:auto`。focused test 在修复前准确失败于 `.data-browser-page` 缺少收缩和横向裁剪边界，因此无需修改 AppShell、`body/html` 或取消表格最小宽度。

## 3. 解决流程

1. 从 `79e65c07298e19e2d183300ec9ef9fad2bc4ce41` 创建独立 worktree。
2. 强化 CSS 回归测试，覆盖 page boundary、table wrapper、tabs 和移动端 690px 宽表。
3. 证明测试在修复前因 page boundary 缺失而失败。
4. 仅为 `.data-browser-page` 增加 `min-width:0; max-width:100%; overflow-x:clip;`。
5. 新增独立 Playwright 用例，通过 API mock 在 390/768/1024/1280 四档真实 Chromium 中验证根文档宽度和内部表格滚动。
6. 运行 Node 24 typecheck、完整 Vitest、changed-path lint、production build 与 `git diff --check`，并清理 Next.js 自动生成差异。

## 4. Agents、skills、tools 与文档

- Agents：研发部席位 `engineering-02`；来源主线程 `/root`；未派生子 Agent。
- Skills：本次为任务卡明确限定的最小 CSS 修复，未调用额外 skill。
- Tools：`exec_command`、`apply_patch`、Playwright Chromium。
- 已读：`.codex/organization.toml`、`docs/organization/README.md`、追加 Web Remediation 02 后的任务卡、全局样式、现有布局测试、Playwright 配置和数据浏览器组件。

## 5. 可沉淀经验

- 内部滚动容器正确并不保证根页面不会被子元素的 scrollable overflow 撑宽；复杂 grid/sticky 组合应在模块根节点建立明确的 overflow propagation boundary。
- `overflow-x:clip` 比全局 `body { overflow-x:hidden }` 更符合模块边界：不创建额外滚动容器，也不会掩盖其他页面问题。
- 响应式溢出修复应同时断言“根文档不滚动”和“内部容器仍能滚动”，避免把问题从双滚动误修成内容不可达。

## 6. 更好的初始提示词

> 390px 下数据浏览器的 table wrapper 已能在 326/690px 内部横向滚动，但根文档仍被撑到 545px。请只在 `.data-browser-page` 建立 `min-width:0; max-width:100%; overflow-x:clip` 边界，不改 body/html/AppShell，不取消表格和 tabs 的内部横向滚动。补充静态 CSS 回归与 390/768/1024/1280 浏览器实测，运行 Node 24 typecheck、tests、changed lint、build 和 diff check。

## 7. 更优方案与一次解决提示词

> 将验收写成三个不变量后做最小修复：所有视口 `documentElement.scrollWidth === innerWidth`；`.data-browser-table-wrap` 始终 `overflow-x:auto` 且 `scrollWidth > clientWidth`；390px `.data-browser-tabs` 保持 `overflow-x:auto`。只允许修改数据浏览器根容器 CSS、focused test、独立布局 E2E 和报告，禁止全局 overflow workaround，并在提交前清除 Next 自动生成文件。

## 验证证据

- 390px：document `390/390`；table wrapper `356/690`；table `auto`；tabs `auto`。
- 768px：document `768/768`；table wrapper `496/820`；table `auto`。
- 1024px：document `1024/1024`；table wrapper `752/820`；table `auto`。
- 1280px：document `1280/1280`；table wrapper `506/820`；table `auto`。
- Focused Playwright：4/4 通过；Vitest：8 files / 17 tests 通过；Node v24.14.0 typecheck、changed-path ESLint、production build、`git diff --check` 均通过。
- Playwright 初次执行发现本机缺少项目锁定 Chromium，安装 build v1187 后原样重跑通过；无生产部署、push 或外部状态变更。
