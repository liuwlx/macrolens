# ML-20260820-052｜数据浏览器同步后快照发现修复

## 1. 问题与场景

`DataBrowserPage` 的 Provider latest、单 Series history、bulk history 三条同步路径在成功后只失效当前 `data_as_of` 对应的查询。页面继续停留在同步前的研究快照，且没有执行无 `data_as_of` 的 latest-check，因此旧标签不会出现已有的“检测到新数据快照 / 切换到新数据”提示。

目标行为是：同步成功并完成原有 invalidation 后检查最新快照；只有 `latest.data_as_of` 与当前研究上下文不同才显示 banner；用户点击“切换到新数据”后才更新路由。同步失败不得执行 latest-check 或显示 banner。

## 2. 分析过程

事实：基线 `fd500fc379d7088471f1849faf3adb58c14a8264` 中已有 `refreshAll`，其请求不带 `data_as_of`，并已有 banner 与手动切换行为；三个同步成功分支都没有调用它。bulk 的 failed terminal 仍执行原有 invalidation，因此 latest-check 必须额外受成功状态约束。

通过公共组件 seam 新增确定性的回归测试，先在基线观察到失败：bulk 同步显示完成，但找不到新快照 banner。按优先级验证后，根因确认是成功路径遗漏 latest-check，而不是 API 参数、banner 渲染或 router 行为。

同时识别两项实现风险：长轮询可能捕获旧 `state`；并发刷新可能重复请求。实现使用最新 BrowserState ref，并复用一个 in-flight latest-check Promise；组件卸载后通过统一 mounted ref 阻止 `setState`。

## 3. 解决流程

1. 从指定基线创建独立 worktree 和 `codex/ML-20260820-052-data-browser-snapshot` 分支。
2. 在 `data-browser-page.test.tsx` 依次完成 bulk、single history、provider latest 的红→绿测试。
3. 将 `refreshAll` 改为读取最新 BrowserState、合并并发 latest-check，并在响应后检查组件是否仍挂载。
4. 三条成功路径在原有 invalidation 后调用共享 latest-check；Provider 有失败计数时不检查，bulk 仅在 `succeeded` 终态检查。
5. 保留当前 `data_as_of`，只显示 banner；点击按钮后才通过 router 切换新快照。
6. 补充 bulk failed 终态断言，确认无 latest-check、无 banner。

## 4. Agents、skills、tools 与文档

- Agents：当前研发执行 Agent；未创建或调用子 Agent。
- Skills：`diagnosing-bugs`（构建红色反馈环、排序并验证假设）、`tdd`（公共 seam 上逐条红→绿）。
- Tools：`exec_command` / `write_stdin`（读取、测试、构建与 Git 检查）、`apply_patch`（源码、测试和报告编辑）、`update_plan`（任务进度）。
- 项目文档：`AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`、`CONTEXT.md`、`docs/governance/development-constitutions/README.md`、`01-local-development-and-freeze.md`、`docs/architecture.md`。
- Skill 文档：`diagnosing-bugs/SKILL.md`、`tdd/SKILL.md`、`tdd/tests.md`、`tdd/mocking.md`。
- 代码文档/源码：`data-browser-page.tsx`、`data-browser-page.test.tsx`、`browser-query.ts`、`browser-availability.ts`、`series-detail-panel.tsx`、`analysis-panel.tsx`、`apps/web/lib/types.ts`。

## 5. 验证结果与可沉淀经验

- 目标测试：11/11 通过。
- 全 Web test：14 个文件、54 个测试通过。
- Web lint：通过；有 2 条与本任务无关的基线 warning（alerts 未使用导入、postcss 匿名默认导出）。
- Web typecheck：通过。
- Web build：通过，14 个页面生成成功。
- Backend 门禁：按用户最后指示不等待、不执行；本任务无 backend/API/OpenAPI 变更。
- Docker/远程服务：未启动、未修改、未使用。

可沉淀模式：固定研究快照的页面在 mutation 后不能只 invalidate 固定快照查询；应将“刷新当前上下文”和“发现最新快照”作为两个不同动作。latest-check 必须无 `data_as_of`、可合并并发请求、读取最新 UI state、卸载安全，并只在 mutation 的明确成功终态执行。

## 6. 更好的初始提示词

> 修复数据浏览器同步成功后仍停留在旧快照且没有新数据提示的问题。请覆盖“数据同步”“单个指标历史同步”“批量历史同步”三种操作：成功后检查服务器最新数据时间，但不要自动改变我当前正在研究的快照；发现新快照时显示现有提示，只有我点击“切换到新数据”才更新页面。同步失败不要检查或提示。请用页面测试验证请求不携带旧快照参数、提示出现和点击后的路由变化，并避免卸载后更新页面状态。

## 7. 更优一次解决方案与提示词

更优方案是把所有同步 mutation 的成功收口统一为一个公共流程：先执行各路径自己的 query invalidation，再调用一个“发现最新快照”函数。该函数读取最新页面状态、用不含 `data_as_of` 的稳定查询键请求、合并并发调用，并在组件仍挂载且快照确实变化时设置 banner。每个 mutation 只负责定义什么是成功，失败和 partial failure 不进入发现流程。

> 在现有 DataBrowserPage 内统一三个同步动作的成功后处理。先用组件级 TDD 复现：当前 URL 固定旧 `data_as_of`，同步 API 成功，随后 `/series/browser` latest-check 必须不带 `data_as_of`，显示现有新快照 banner，点击后 router 才写入新快照。至少分别覆盖批量历史和单指标历史，并覆盖 Provider latest；再覆盖一个失败终态，断言没有 latest-check/banner。实现时复用或提取一个公共 success-finalizer/latest-snapshot checker：先完成原 invalidation，再检查最新快照；读取最新 state，合并并发检查，卸载后不 setState。不要修改 backend/API/OpenAPI，不自动替换研究上下文。
