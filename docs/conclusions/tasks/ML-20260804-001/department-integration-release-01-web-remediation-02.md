# ML-20260804-001 / Integration & Release-01 Web Remediation 02 工作报告

- 席位状态：REVIEW
- 来源主线程：`/root`
- 集成基线：`beaac5eec0515e2f7fde11b5b6cab10fcfc81167`
- Engineering-02 候选：`fdb27fedea29d50066ae07b6f763ff4943092665`
- main 集成提交：`9feeed26180eb8905390cb74b814aefbd32702b8`
- 完成结果：Web Remediation 02 已严格集成，layout、四档 overflow E2E 和 Web 门禁通过；未 push、未部署，尚不宣称整个任务 release pass。

## 1. 问题与场景

数据浏览器在 390px 视口仍存在根页面横向溢出：表格 wrapper 已能内部横向滚动，但 690px 宽表和 sticky 单元格的 overflow 会传播到根文档，使 `document.documentElement.scrollWidth` 大于 `window.innerWidth`。修复必须限制在数据浏览器模块边界，不能用全局 `body/html` 隐藏溢出，也不能破坏表格和 tabs 的内部滚动。

当前 main 还持有未跟踪的完整任务卡、实现计划和 QA 资产。集成必须严格保留这些主线程资产，并确认 Next build 不把 `tsconfig.json` 或 `next-env.d.ts` 带入提交。

## 2. 分析过程

集成前复读组织规则和追加 Web Remediation 02 的完整 task-card，确认候选父提交为上一轮报告提交 `79e65c0`，而当前 main `beaac5e` 只新增安全报告，不与 Web 文件重叠。候选提交仅修改 `globals.css`、布局测试，新增 overflow E2E 和 Engineering 报告，没有触碰任务卡、计划或 QA 资产。

差异审计显示 CSS 只在 `.data-browser-page` 增加 `min-width: 0`、`max-width: 100%`、`overflow-x: clip`。布局测试同时断言页面边界、table wrapper、tabs 和 690px 宽表；E2E 用 API mock 在四档 Chromium 视口断言根文档无溢出、表格仍可内部滚动，并在 390px 验证 tabs 横向滚动。

## 3. 解决流程

1. 读取 `.codex/organization.toml`、`docs/organization/README.md` 和完整 task-card。
2. 核验 main、候选、候选父提交、文件范围和候选 `git diff --check`。
3. 单独 cherry-pick `fdb27fe` 到 `beaac5e`，无冲突生成 `9feeed2`。
4. 复核最终范围只包含四个候选文件，完整 task-card 哈希保持不变。
5. 使用隔离 Node 24 运行 focused layout、完整 Vitest、changed ESLint、typecheck 和 production build。
6. 启动本地 Next 验收进程，在 390/768/1024/1280 四档运行 Chromium overflow E2E，随后关闭进程。
7. 清理 Next 自动改写的 `tsconfig.json`、生成的 `next-env.d.ts` 和 Playwright 报告文件，复核 Git 状态与冲突标记。
8. 单独提交本七节报告；不 push、不部署。

## 4. Agents、Skills、Tools 与文档

- Agents：Engineering-02 提供 Web Remediation 02 候选；Quality/Security 提供验收约束；Integration & Release-01 完成 main 集成与门禁。本席位未创建子 Agent。
- Skills：未使用专用 skill；本任务属于组织规则明确的 Git 集成、响应式回归验证和发布门禁。
- Tools：`exec_command` 用于 Git、Node、Next、ESLint、Vitest、Playwright、哈希和状态核验；`write_stdin` 用于安全关闭本地验收进程；`apply_patch` 用于清理生成文件并新增报告；`update_plan` 用于执行进度管理。
- 已读文档：根 `AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`、完整 task-card、Engineering-02 Remediation 02 报告、既有 Integration/Security 报告、Playwright 配置、Web package scripts 及候选 CSS/测试差异。

## 5. 值得沉淀的经验与模式

1. 内部 scroller 正确不代表根页面不会被撑宽；复杂 grid/sticky 结构应在模块根节点建立明确的 overflow propagation boundary。
2. 响应式 overflow 验收必须同时检查两个不变量：根文档不横向滚动，内部宽内容仍然可滚动。
3. `overflow-x: clip` 应放在最小模块边界，避免全局 `body/html` workaround 掩盖其他页面的真实布局问题。
4. 静态 CSS 单测适合锁定声明，Playwright 则验证浏览器计算后的实际 scrollWidth；两者组合比单一截图更稳定。
5. Next build 会自动改写 TypeScript 配置，Playwright 会生成报告目录；绿色门禁之后仍需执行工作区副作用审计。

## 6. 更好的初始提示词

> 请把 Web Remediation 02 候选严格集成到当前 main。先读取组织规则和完整 task-card，记录并保护所有未跟踪任务卡、计划和 QA 资产。确认候选只修改数据浏览器页面边界 CSS、focused layout test、独立 overflow E2E 和部门报告；不要使用 body/html 全局 overflow workaround。用 Node 24 运行 layout 单测、完整 Vitest、changed ESLint、Web typecheck/build，并启动本地 build 在 Chromium 390/768/1024/1280 四档验证 documentWidth 等于 innerWidth、table wrapper 保持 auto 且 scrollWidth 大于 clientWidth、390px tabs 保持 auto。最后清理 tsconfig/next-env/Playwright 生成物，只提交候选和七节报告，不 push、不部署。

## 7. 当前方案反思与更优方案提示词

当前修复是符合模块边界的最小方案。更优的长期方案是建立共享的响应式布局契约测试工具：自动遍历关键路由和标准视口，检测根文档 overflow，并允许为声明过的内部 scroller 配置例外；同时输出元素级 overflow 传播链，帮助定位是哪一层突破容器。这样可以在 CSS 变更进入 main 前发现同类回归。

> 请为 Web 建立响应式 overflow 契约门禁：覆盖 390、768、1024、1280 视口，逐页断言 `documentElement.scrollWidth === innerWidth`；只有 manifest 中声明的 table/tabs/carousel 可以横向滚动，并断言其内容仍可达。失败时输出最宽元素、祖先 min-width/overflow 链和截图。先接入 `/data`，复用 API mock，保持 Chromium 快速门禁，并在完整 QA 中补 Safari/WebKit 与 Firefox。

## 检查结果与 residual risk

- Focused layout Vitest：1 file / 1 test passed。
- 完整 Web Vitest：8 files / 17 tests passed。
- Changed ESLint：`browser-layout.test.ts` 与 `data-browser-overflow.spec.ts` 通过。
- Node `v24.18.1` Web typecheck：通过。
- Node `v24.18.1` production build：通过，15 个路由生成成功，包含 `/data`。
- Chromium overflow E2E：4/4 passed。
  - 390px：document `390/390`；table wrapper `356/690`；table `overflow-x:auto`；tabs `auto`。
  - 768px：document `768/768`；table wrapper `496/820`；table `auto`。
  - 1024px：document `1024/1024`；table wrapper `752/820`；table `auto`。
  - 1280px：document `1280/1280`；table wrapper `506/820`；table `auto`。
- 候选、集成范围和工作区 `git diff --check`：通过；`apps/web` 无冲突标记。
- `apps/web/tsconfig.json` 已恢复基线，`apps/web/next-env.d.ts` 不存在；提交不含 Next/Playwright 副作用。
- 完整 task-card SHA-256 保持 `FC157D55CB28D9AE9AE3D5B8FC2B1A06849AD27C4AFF1B3C9C9E89B914BBD5C2`，未跟踪计划与 QA 资产未被覆盖或提交。
- E2E 使用 Chromium 和 mock API，未覆盖真实数据负载、WebKit/Firefox 或完整视觉差异；这些仍需后续 Quality/Operations 验收。
- 未执行本轮后端门禁、全量 Web lint 或完整 E2E 套件；本提交只验证 Web overflow 修复，不代表整个任务 release pass。
- 未 push、未部署、未切换 feature flag。
