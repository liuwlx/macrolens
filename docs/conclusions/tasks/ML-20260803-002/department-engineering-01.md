# ML-20260803-002 研发部 01 回执

- 席位状态：REVIEW
- 任务 ID：ML-20260803-002
- 来源主线程：`/root`
- 完成结果：已将 `apps/web` 的 `echarts-for-react` 从固定版本 `3.0.2` 升至固定版本 `3.0.6`，并由 npm 生成根 `package-lock.json`。原始依赖解析复现命令已由 `ERESOLVE` 转为退出码 0；扩展任务卡后，以 `saveReport.mutate(undefined)` 最小修复 TanStack Mutation 必传变量类型错误，`next build` 已全程通过。
- 修改文件：`apps/web/package.json`、`package-lock.json`、`apps/web/app/(app)/reports/page.tsx`、本回执。
- 提交 SHA：未提交（任务明确要求不要提交）。起始提交为 `79eca99e8752a0e467856bf02b971e40e7eac6fb`。

## 1. 问题与场景

生产部署需要从干净依赖树构建 Web，但根工作区执行：

```text
npm install --package-lock-only --ignore-scripts --no-audit --no-fund --dry-run
```

会稳定返回 `ERESOLVE`。`apps/web` 固定使用 `echarts@6.0.0`，而 `echarts-for-react@3.0.2` 声明的 peer 范围仅为 `^3.0.0 || ^4.0.0 || ^5.0.0`，因此 npm 无法生成可复现的生产依赖锁。

## 2. 分析过程

采用 `diagnosing-bugs` 技能建立快速、确定、可无人值守的反馈环：以上 dry-run 命令约 1 秒完成，并直接覆盖用户遇到的依赖树解析失败。修复前实测退出码 1，错误树同时指出 `echarts@6.0.0`、`echarts-for-react@3.0.2` 及不兼容 peer 范围。

排序假设为：

1. 3.0.2 的 peer 上限导致唯一直接冲突，3.0.6 支持 ECharts 6 后会转绿。
2. 消除该冲突后会暴露另一个 peer 冲突。
3. 本机 npm/缓存制造了假冲突。

仅改变一个变量后原命令退出码变为 0，且没有新的 ERESOLVE；`npm ls` 也显示 `echarts-for-react@3.0.6` 使用去重后的 `echarts@6.0.0`，故确认假设 1。

## 3. 解决流程

1. 完整阅读组织规则、任务卡和诊断技能，确认授权边界。
2. 记录基线提交和共享工作区已有未跟踪文件，避免覆盖其他席位工作。
3. 运行最小复现，保存精确的 ERESOLVE 症状。
4. 仅把 `apps/web/package.json` 中 `echarts-for-react` 固定为 `3.0.6`。
5. 运行 `npm install --package-lock-only --ignore-scripts --no-audit --no-fund` 生成根锁文件。
6. 重新运行原 dry-run，确认退出码 0。
7. 通过 `npm ci --ignore-scripts --no-audit --no-fund` 安装锁定依赖，运行 lint、test、build。
8. 扩展任务卡后，将 `next build` 作为逐项 TypeScript 红/绿反馈环；对首个且唯一错误，把可选状态 mutation 的无参调用改为显式传入 `undefined`。
9. 复跑 `next build`，确认编译、TypeScript、页面数据收集及 15 个静态页面生成全部通过。
10. 清理 Next.js build 自动产生的 `next-env.d.ts` 及对 `tsconfig.json` 的纯格式和 `.next/dev/types` include 改写，确保不越出必要修改范围。
11. 使用 `npm ls`、`git diff --check` 和 `git status` 做最终范围核对。

## 4. Agents、skills、tools 与文档

- Agents：研发部 01 单席执行；未使用其他 Agent 或子 Agent。
- Skills：`diagnosing-bugs`。该技能决定先建立红/绿依赖解析反馈环，再以 `next build` 逐项暴露 TypeScript 首错、做单变量最小修复并复跑完整场景。
- Tools：`exec_command` 用于读取、复现、安装、检查和状态核对；`apply_patch` 用于单行依赖修改、清理构建副作用和写回执；`write_stdin` 用于取得长时间 lint 进程的最终结果。
- 已读文档：`.codex/organization.toml`、`docs/organization/README.md`、`docs/conclusions/tasks/ML-20260803-002/task-card.md`、`C:/Users/liuwl/.codex/skills/diagnosing-bugs/SKILL.md`、根 `AGENTS.md`（由任务上下文提供）。项目根未发现 `CONTEXT.md`。

## 5. 检查结果、经验与模式

已执行检查：

- `npm install --package-lock-only --ignore-scripts --no-audit --no-fund --dry-run`：修复前失败（退出码 1，ERESOLVE）；修复后通过（退出码 0）。
- `npm install --package-lock-only --ignore-scripts --no-audit --no-fund`：通过，生成根锁文件。
- `npm ci --ignore-scripts --no-audit --no-fund`：通过，安装 498 个包。
- `npm ls echarts echarts-for-react --workspace apps/web`：通过，解析为 `echarts-for-react@3.0.6` + `echarts@6.0.0 deduped`。
- `git diff --check -- apps/web/package.json package-lock.json`：通过。
- `npm --workspace apps/web run lint`：失败，现有基线共有 67 个问题（62 errors、5 warnings），主要为 React `set-state-in-effect`、`static-components` 及 E2E `no-explicit-any`；不属于本任务授权范围。
- `npm --workspace apps/web run test`：失败，Vitest 配置加载时以 CommonJS `require()` 加载 ESM 版 `@vitejs/plugin-react`，报 `ERR_REQUIRE_ESM`；不属于本次版本变更。
- `npm --workspace apps/web run build`：首轮生产代码编译成功后，在 `app/(app)/reports/page.tsx:88` 暴露 `mutate()` 缺少必需变量；改为 `saveReport.mutate(undefined)` 后复跑通过，包括编译、TypeScript、页面数据收集、15 个静态页面生成和最终优化。
- `npm --workspace apps/web run typecheck`：清理 Next 自动生成文件后可正常启动，现有 `lib/api.test.ts:35` 的 Vitest `toMatchObject` matcher 类型报错；该测试类型错误不进入已通过的 `next build` 检查范围，未扩改。

环境注意：本机 Node 为 `20.11.1`，项目声明 `>=22`，因此 npm 给出 `EBADENGINE` 警告。依赖解析和锁文件生成仍成功；生产/CI 应使用 Node 22+ 重跑完整门禁。

值得沉淀的模式：依赖冲突应以包管理器的 dry-run 作为直接回归测试；严格固定直接依赖版本并提交锁文件，避免部署时重新解析出不同树；TanStack Mutation 的变量即使是可选类型，`mutate` 的变量形参仍可能是必传，应显式传 `undefined` 表达“沿用默认状态”；构建工具可能自动改写配置，任务结束前必须通过 `git status`/diff 清理越界副作用；共享工作区的既有未跟踪文件必须视为他人资产。

## 6. 反推的更好初始提示词

> 当前 MacroLens 根工作区生成 npm 锁文件时报 ERESOLVE，并阻断生产 Web 构建。请先运行 `npm install --package-lock-only --ignore-scripts --no-audit --no-fund --dry-run` 保存失败证据，检查 ECharts 与 React 包装组件的 peer 范围；若错误确认为 `echarts@6.0.0` 与 `echarts-for-react@3.0.2` 冲突，只把后者固定升级到支持 ECharts 6 的 `3.0.6`，用 npm 生成根 `package-lock.json`，再复跑同一命令与 `next build`。若 build 逐项暴露 TypeScript 错误，只做保持运行语义的最小类型安全修复并每次复跑到绿；不得关闭类型检查或无关重构。清理 Next 自动生成的非必要源码改动，不要提交，并记录 lint/test 的既有失败与 Node 版本。

## 7. 当前场景的更优方案与提示词

更优方案是在与生产一致的 Node 22+ 干净环境中使用 `npm ci` 验证锁文件，再把依赖解析、lint、test、build 分别作为独立门禁；这样能同时消除本机引擎偏差，并准确区分依赖阻断与既有源码门禁失败。对应提示词：

> 请在 Node 22+ 的干净环境中诊断并解除 MacroLens Web 的 npm 生产构建阻断：先以 package-lock-only dry-run 复现并保留错误树，只做最小的直接依赖版本修复，生成并校验根锁文件；随后从空 node_modules 执行 `npm ci`，以 `next build` 为首错反馈环逐项做最小类型安全修复直至通过，再分别运行 lint、test 与独立 typecheck 并分类现有失败。构建工具若改写任务范围外文件必须清理，不得以跳过类型检查、`--force` 或无关重构换取绿色。

## 风险、阻挡与交接

- 风险与兼容性：直接依赖仍采用精确版本；3.0.6 的 peer 接受 ECharts 6；保存草稿仍向 mutation 传入 `undefined` 并沿用原来的 `status ?? selected.status` 语义，未改变公共接口或 Schema。
- 阻挡项：本席的依赖解析与生产 `next build` 阻断均已解除；完整前端门禁仍受上述既有 lint、Vitest 配置及独立测试 typecheck 错误阻挡。
- 给集成/发布部门的说明：使用 Node 22+ 基于根 `package-lock.json` 执行干净 `npm ci`；本次无需 `--force` 或 `--legacy-peer-deps`。集成时接收 `apps/web/package.json`、根 `package-lock.json`、`apps/web/app/(app)/reports/page.tsx` 与本回执。
