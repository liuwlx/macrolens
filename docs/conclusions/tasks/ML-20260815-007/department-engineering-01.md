# ML-20260815-007｜研发部 01 工作报告

## 1. 问题与场景

验收 Web 使用 `NEXT_PUBLIC_API_URL=/api/v1`，浏览器因此把登录等 API 请求发送到 Web 同源路径。起点候选 `1974e8955e6b529a89fdfb3a7d73052d2c5e4453` 的 `apps/web/next.config.ts` 只保留安全响应头，没有把 `/api/v1/:path*` 转发到 Compose 内部 API，公网 API `:8100` 不可达时登录链路因此中断。历史可用提交 `4e03845` 已证明同源 rewrite 能关闭该故障，但合并后的当前候选遗漏了它。

本席位所有权严格限制在 `apps/web/next.config.ts`、直接回归测试、任务卡副本和本报告。未 push、PR、merge、tag、deploy，未运行 Docker、migration、seed、sync、真实 Probe，未修改或运行 Scheduler。

## 2. 分析过程

`diagnosing-bugs` 要求先建立能命中用户症状的快速反馈环，再提出和验证可证伪假设。为此新增 `apps/web/next.config.test.ts`，直接加载 Next 配置，并在 `NEXT_PUBLIC_API_URL=/api/v1` 条件下断言生产 rewrite。

有效 RED 命令使用 Node 22.14.0 从 `apps/web` 运行单文件 Vitest。原始摘要为：`1 test | 1 failed`，断言显示期望 `[{ source: "/api/v1/:path*", destination: "http://api:8000/api/v1/:path*" }]`，实际为 `undefined`，总时长约 `0.9s`；第二次重复运行得到相同结论。扩展为默认目标、自定义目标和 headers 三项后，修复前摘要为 `3 tests | 2 failed | 1 passed`：两个 rewrite 断言失败，既有 headers 断言通过。

按优先级验证了四个假设：

1. 候选合并时丢失 `rewrites`：成立；当前 `nextConfig.rewrites` 为 `undefined`，而 `git show 4e03845:apps/web/next.config.ts` 含目标实现。
2. 客户端没有走同源路径：排除；`apps/web/lib/api.ts` 使用 `NEXT_PUBLIC_API_URL` 拼接请求，值为 `/api/v1` 时请求保持同源。
3. 仓库中已有其他生产代理 seam：排除；检索未发现 middleware、route handler 或其他 `/api/v1` 生产代理，命中的 Playwright routes 仅为测试 mock。
4. rewrite 会覆盖或改变 headers：排除；修复前后同一精确 headers 回归均通过。

事实结论是候选缺少 Next rewrite。关于“为何在合并时丢失”的具体过程没有本轮证据，因此不把它陈述为已证实事实。

## 3. 解决流程

1. 核对独占 worktree、分支和起点 SHA，确认初始工作区 clean。
2. 建立并实际运行正确 seam 的 RED；第一次从仓库根运行时因 Vitest 相对 `setupFiles` 路径错误而未收集测试，该入口错误未计作 RED，改从 `apps/web` 运行后取得有效证据。
3. 给出四个可证伪假设并逐项取证，不等待外部确认。
4. 在 `next.config.ts` 中最小恢复 `rewrites()`：读取 `API_INTERNAL_URL`，默认 `http://api:8000/api/v1`，将 `/api/v1/:path*` 转发到 `${apiInternalUrl}/:path*`；未改动 `headers()`。
5. GREEN 原始摘要：目标文件 `1 passed`、`3 tests passed`；默认内部 URL、自定义 `API_INTERNAL_URL` 和既有安全 headers 全部通过。
6. 用 `apply_patch` 将根任务卡加入 worktree，根副本和候选副本 SHA-256 均为 `F1CDF140B0FC93A4D06A4B7B1E27CD5C06D085FA487B3E0A9291D0D282AF9B37`。
7. 固定 Node 22.14.0/npm 10.9.2 并在当前 worktree 以 `npm ci` 安装锁文件依赖；固定 Python 3.12.9 完整 venv 执行后端门禁。
8. 检查候选 diff、历史可用配置差异、调试标记、构建副作用和空白错误，然后提交。

## 4. Agents、skills、tools、文档与验证

- Agents：MacroLens 研发部 01 单席位执行；未启用子 Agent，未接管其他线程职责。
- Skill：完整读取并执行 `C:\Users\liuwl\.codex\skills\diagnosing-bugs\SKILL.md`。它直接决定了“先构造 RED、再列四个假设、逐一验证、最小修复、重跑原反馈环、清理调试残留”的顺序。
- Tools：`apply_patch` 用于全部候选文件编辑；PowerShell、Git、`rg` 用于只读检查和验证；计划工具用于进度控制；Node/Vitest/ESLint/Next、Python/ruff/mypy/pytest 用于门禁。未使用浏览器、网络搜索、Docker、数据库、Provider 或部署工具。
- 已读规则与文档：worktree `AGENTS.md`；根工作区只读的 `.codex/organization.toml`、`docs/organization/README.md`、`docs/conclusions/tasks/ML-20260815-007/task-card.md`、`docs/governance/development-constitutions/README.md`、`01-local-development-and-freeze.md`、`02-pr-merge-and-release.md`、`03-server-deploy-and-acceptance.md`；另检查 `package.json`、`apps/web/package.json`、`apps/web/vitest.config.mts`、`apps/web/lib/api.ts`、当前与 `4e03845` 的 Next 配置。
- 阶段 01：完成。形成最小候选、运行完整本地六门禁并生成提交。
- 阶段 02：规则已加载但本席位未执行；按用户边界不 push、不建 PR、不 merge、不打标签，交集成发布部继续。
- 阶段 03：规则已加载但本席位未执行；按用户边界不部署、不运行 Docker 或运行时验收，交运维与支持席位继续。
- Node 22.14.0：目标测试 `3 passed`；Web lint `0 errors, 2 warnings`（`alerts/page.tsx` 未使用导入、`postcss.config.mjs` 匿名默认导出，均为既有告警）；Web 全测 `11 files, 35 tests passed`；Next 16.2.12 production build 成功。
- Python 3.12.9（`E:\workerspace\projects\20260709\macrolens-worktrees\ML-20260815-002-engineering-01\.venv\Scripts\python.exe`）：ruff `All checks passed`；mypy `70 source files` 无问题；pytest `228 passed, 5 warnings in 18.53s`。曾先试用根项目 Python 3.12.9 venv，但其缺少 ruff；这是工具入口错误，不计作代码门禁结果，随后使用指定完整 venv 从头复跑。
- `git diff --check`：通过；`git diff 4e03845 -- apps/web/next.config.ts`：空，证明实现与已知可用配置一致；`[DEBUG-*]` 检索：无残留。

## 5. 值得沉淀的经验与模式

同源 API 代理应在 Next 配置 seam 直接测试，不需要启动 Web/API 或依赖公网环境。一个不足一秒、直接断言 rewrite 对象的测试能把“浏览器公网不可达”“客户端 URL 拼接”“代理缺失”和“内部目标配置错误”拆开，避免用昂贵的部署验收定位静态配置回归。

部署配置是可执行契约，也需要版本化回归：至少同时锁定公开 source、默认 destination、环境变量覆盖和原有 headers。已知可用提交适合作为差分证据，但它不能替代当前候选上的 RED/GREEN。

工具链入口错误必须与代码失败分开记录。Vitest 的工作目录和 Python venv 的工具完整性都可能制造假红；只有测试真正收集并命中目标断言，才可作为缺陷证据。

## 6. 更好的初始提示词

> 验收环境的浏览器只访问 Web 同源 `/api/v1`，不能直接访问 API 的公网端口。请在指定独立 worktree 检查当前 Next 配置是否缺少同源转发：先写一个直接加载 `next.config.ts` 的快速测试，证明 `/api/v1/:path*` 没有转发到内部 API；复现后恢复可由 `API_INTERNAL_URL` 配置、默认指向 `http://api:8000/api/v1` 的 rewrite，并用测试保证原安全 headers 不变。固定 Node 22 和项目 Python 3.12 完整 venv 跑六项门禁，只修改 Next 配置、直接测试、任务卡副本和七节报告，最后本地提交并返回 SHA；不要部署、推送、操作 Docker、数据库、Provider 或 Scheduler。

## 7. 更优方案反思与一次解决提示词

当前最小方案已经是本场景风险最低的修复：它恢复已在真实验收中验证过的配置，不扩展客户端或部署层。可进一步改进的是把该测试保留在长期 CI，并明确验证环境变量含义；若未来允许更多配置输入，再单独决定是否规范化尾部斜杠，不能在本次修复中无证据扩展行为。

> 请把 Next 同源 API 转发视为发布契约修复。先在 `apps/web` 新增配置级 Vitest：设置 `NEXT_PUBLIC_API_URL=/api/v1`，分别断言默认 `API_INTERNAL_URL` 和自定义值生成精确 rewrite，同时快照式断言现有安全 headers。必须先在 Node 22.14.0 下看到 rewrite RED、headers GREEN；再仅在 `next.config.ts` 添加 `rewrites()`，默认 `http://api:8000/api/v1`，复跑目标测试和 Web lint/test/build。随后用指定 Python 3.12 完整 venv 跑 ruff/mypy/pytest，检查与已知可用提交的配置差异、`git diff --check`、调试残留和构建副作用。复制任务卡、写七节报告、提交并确认 clean；禁止 push、PR、merge、tag、deploy、Docker、migration、seed、sync、Probe 和 Scheduler 操作。
