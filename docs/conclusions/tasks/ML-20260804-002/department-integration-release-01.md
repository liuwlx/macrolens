# ML-20260804-002 / Integration & Release-01 工作报告

- 席位状态：REVIEW
- 来源主线程：`/root`
- 集成基线：`bf8d41e6d98befd042682b4f7b913eb9d650f8a9`
- UI 候选：`b3a7f56468fe74c9f9ba0725b00b426d3d3ffab5` → main `66efd386d2ce44afaa81a37dbf260378b750d51a`
- 远程开发候选：`0b79ff74331934cf0a31daf8a9e1f3990ec6e549` → main `517d7cba90363e23b34af92ab7a8345ecc893e57`
- 结果：两个候选按指定顺序无冲突集成，关键门禁通过；未 push、未部署、未 Provision、未启动隧道或修改服务器。

## 1. 问题与场景

本次需要把两项已审查、同基线开发的变更安全集成到 main。第一项修复登录后台在超宽屏上的无效留白和数据浏览器纵向填充；第二项新增 Windows PowerShell 远程开发工作流，通过本机回环 SSH 隧道连接现有 PostgreSQL，并提供 Provision、Start、Status、Stop、Deprovision 五个动作。

集成只允许落地各候选白名单，且必须保留 main 上两个未跟踪的上轮资产：`artifacts/design-qa/local-preview-server.mjs` 和 `docs/conclusions/2026-08-04-local-preview-connection-refused-fix.md`。验证不能执行任何会创建远程角色、启动隧道或修改服务器的动作。

## 2. 分析过程

先读取根 `AGENTS.md`、组织配置和运行手册，确认 Integration & Release 是唯一集成席位。两个候选的父提交都严格等于基线 `bf8d41e`，提交级 `git diff --check` 均通过；UI 候选只包含四个 Web 文件和 Engineering-01 报告，远程开发候选只包含 README、主脚本、两份测试和 Engineering-02 报告，二者没有文件重叠。

未跟踪资产在集成前分别记录 SHA-256：preview server 为 `619B913D3CF470A7A7F02C18AEE4AA1C5BEF5143F4BB14F1B33ECB7B8C23846F`，连接拒绝修复报告为 `6D30C0B7FA9563740DEB52147BE26844CA1B654095DA98AFD8317FF9D49EC904`。两次 cherry-pick 后哈希均不变。

PowerShell 门禁只运行静态/本地进程安全测试：解析脚本、检查五动作与安全字符串、验证 `.env.remote` 忽略规则、发现本地 Node/Python，并创建后立即回收一个本地探针进程；没有调用 Provision、Start 或 Deprovision，也没有远程访问。

## 3. 解决流程

1. 复读工程规则和组织文档，记录 main HEAD、工作区与两个未跟踪文件哈希。
2. 审计两个候选的父提交、文件白名单、提交说明和 `git diff --check`。
3. 先 cherry-pick UI 候选，生成 `66efd38`；确认无冲突且未跟踪哈希不变。
4. 再 cherry-pick远程开发候选，生成 `517d7cb`；再次确认无冲突且未跟踪哈希不变。
5. 在 PowerShell 5.1 中运行只读静态/本地进程安全合同测试。
6. 使用隔离 Node 22 运行布局 focused test、完整 Web tests、changed ESLint 和 production build。
7. 清理 Next build 自动改写的 `tsconfig.json` 与生成的 `next-env.d.ts`。
8. 复核完整集成范围、冲突标记、diff check 和工作区状态，仅新增并提交本报告。

## 4. Agents、Skills、Tools 与文档

- Agents：Engineering-01 提供宽屏 UI 候选；Engineering-02 提供远程开发脚本候选；Integration & Release-01 完成 main 集成和门禁。本席位未创建子 Agent。
- Skills：未使用专用 skill；本任务属于组织规则明确的 Git 集成、脚本静态验收和 Web 回归门禁。
- Tools：`exec_command` 用于 Git、哈希、PowerShell、Node、Vitest、ESLint 和 Next build；`apply_patch` 用于清理构建副作用与生成本报告；`update_plan` 管理执行进度；协作消息用于主线程交接。
- 已读文档：根 `AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`、主线程任务卡、两份 Engineering 报告、候选差异、README 和 PowerShell 静态/Pester 测试。

## 5. 值得沉淀的经验与模式

1. 同基线候选仍应逐个 cherry-pick 并在每一步复核未跟踪资产哈希，不能因文件互不重叠而跳过中间检查。
2. 运维脚本的集成验证应严格区分静态/本地安全测试与远程动作；默认只运行前者，避免测试本身扩大授权。
3. Windows 进程管理不能只信任 PID，应组合启动时间、绝对可执行路径、角色和命令行哈希，降低 PID 复用误杀风险。
4. 超宽屏验收需要同时锁定 AppShell 宽度、页面纵向填充、根滚动宽度和局部 scroller，单看截图不足以证明几何正确。
5. Next build 后必须审计并清理 TypeScript 配置副作用，防止把工具生成差异混入集成提交。

## 6. 更好的初始提示词

> 请从 main `bf8d41e` 按顺序集成两个已审查提交：先集成宽屏 UI `b3a7f56`，再集成远程开发脚本 `0b79ff7`。开始前读取 AGENTS/组织规则，记录并哈希保护 `artifacts/design-qa/local-preview-server.mjs` 和本地预览连接修复报告；核对两个候选都直接基于 main、文件范围符合各自白名单且 diff check 通过。任何冲突立即停止。集成后只运行 PowerShell 静态/本地进程安全测试，禁止 Provision/Start/Deprovision、SSH、隧道或服务器修改；用 Node 22 运行布局 focused/full tests、changed ESLint 和 Web build，清理 Next 生成物，输出 candidate→main SHA、检查证据和工作区状态，不 push、不部署。

## 7. 当前方案反思与更优方案提示词

当前方案已通过静态合同锁定安全关键字符串和本地进程身份，但长期更优方案应把远程角色 SQL、端口分类、进程身份和动作调度拆成可注入纯函数，由 Pester 在完全 mock 的 SSH/Docker/进程适配器上验证每个动作的命令序列与失败回滚；UI 则把 AppShell chrome 尺寸提升为共享 CSS 变量，避免未来顶栏/padding 调整与页面高度公式漂移。

> 请把 remote-dev 拆成纯计划层和副作用适配器：五个动作先输出结构化 execution plan，Pester 使用 mock SSH/Docker/Process 验证最小权限 SQL、回环隧道、Alembic 只读比较、PID 复合身份和失败回滚；只有显式 `-Execute` 才执行副作用。与此同时为 AppShell 建立共享 header/padding CSS 变量和通用 viewport page 容器，补 390–2560px 几何 E2E。CI 默认只运行 plan/static tests，远程 smoke 必须人工审批并使用临时凭据。

## 检查结果与 residual risk

- 两个候选提交级及完整集成范围 `git diff --check`：通过。
- Cherry-pick：按指定顺序完成，无冲突；最终候选集成 HEAD 为 `517d7cba90363e23b34af92ab7a8345ecc893e57`。
- PowerShell 5.1 `remote-dev-static.ps1`：PASS；五动作、安全边界、gitignore、运行时发现和本地进程复合身份验证通过。
- Node `v22.23.1` focused layout Vitest：1 file / 3 tests passed。
- Node `v22.23.1` 完整 Web Vitest：8 files / 19 tests passed。
- Changed ESLint：`app-shell.tsx`、布局 Vitest 和 overflow Playwright 通过。
- Node 22 production build：通过，15 个路由生成成功。
- `apps/web/tsconfig.json` 已恢复，`apps/web/next-env.d.ts` 不存在。
- 两个未跟踪资产内容和哈希保持不变，未被任何提交纳入。
- 未重跑六视口 Playwright；复用候选的 6 passed 证据并以静态布局测试、完整 Vitest 和 production build 做集成复核。
- 未运行完整 Web lint；候选报告记录基线仍有白名单外 52 errors / 4 warnings。
- 未运行 Pester wrapper；其唯一测试调用的是本轮已直接通过的同一静态脚本。
- 未执行 Provision、Start、Deprovision、SSH、隧道、远程角色创建、服务器修改、push 或部署。
