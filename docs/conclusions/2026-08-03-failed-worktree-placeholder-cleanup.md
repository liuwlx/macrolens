# Codex 工作树初始化失败占位项处理报告

日期：2026-08-03

## 1. 问题与场景

MacroLens 部门线程初始化期间曾错误提交 9 次 worktree 创建请求。请求没有成功，但 Codex 桌面端侧边栏留下了 9 个标题为“工作树初始化失败”的占位项。用户要求清理这些残留项，同时不得影响已经正确创建的 30 条本地部门线程。

## 2. 分析过程

1. 查看用户截图，确认失败项位于正常 MacroLens 线程列表下方，并带有失败信息图标。
2. 使用 Codex 原生线程列表查询最近线程，确认项目中只有 30 条真实 `ML｜...` 线程，失败项不在返回结果中。
3. 使用 `git worktree list --porcelain` 确认 Git 只有项目主目录，没有失败请求留下的 worktree。
4. 使用已保存的 `clientThreadId` 调用归档接口，接口明确返回“没有对应 Codex thread”，证明失败项没有真实 `threadId`。
5. 以只读方式检查 Codex 本地 SQLite 的 `threads` 表，没有标题为“工作树初始化失败”的记录。
6. 尝试评估 Windows UI 自动处理方案，但 `computer-use` 安全规则明确禁止自动操作 Codex 桌面端，因此停止 UI 自动化。

## 3. 解决工作流

- 不删除、不归档任何真实 MacroLens 线程。
- 不修改 Codex 内部数据库，避免破坏任务索引。
- 将失败项认定为桌面端临时客户端占位，而不是持久线程或 Git worktree。
- 建议刷新或重启 Codex，让侧边栏从真实线程状态重建；若仍显示，由用户点击失败项右侧红色信息按钮并执行界面提供的移除操作。
- 继续保持组织规则：常驻线程使用 local，只有真实编码任务才按需 handoff 到 worktree。

## 4. Agents、skills、tools 与文档

- Agent：当前主线程 `/root`，未调用子 Agent。
- Skill：读取并遵循 `computer-use` skill；该 skill 的安全限制使 Codex 桌面端 UI 自动操作被停止。
- Tools：`view_image`、`list_threads`、`set_thread_archived`、`exec_command`、`apply_patch`。
- 检查内容：`.codex/organization.toml`、`docs/organization/README.md`、Git worktree 列表、Codex `state_5.sqlite` 的表结构和只读查询结果。

## 5. 可沉淀经验

1. `clientThreadId` 只表示异步创建占位，不能当作真实 `threadId` 使用。
2. 清理前必须同时核对线程 API、Git worktree 和本地持久状态，防止误删真实任务。
3. 失败创建卡可能只存在于桌面端临时状态；服务端归档接口无法处理不存在的线程。
4. 不应为清理 UI 残留而直接修改 Codex 内部数据库。
5. 常驻部门线程必须使用 local；worktree 只在真实编码任务发生时创建。

## 6. 更好的初始提示词

> 请清理 Codex 侧边栏中由本次 MacroLens 初始化错误产生的“工作树初始化失败”项目。先通过线程 API、`git worktree list` 和只读本地状态确认它们不是实际线程或工作树；只处理失败占位项，不归档任何标题以 `ML｜` 开头的正常线程。优先使用 Codex 原生清理接口，禁止直接修改内部 SQLite；如果失败项只是客户端临时状态且没有真实 threadId，请明确说明需要刷新/重启或由用户在 UI 中移除。

## 7. 更优方案与提示词

更优方案是在创建常驻部门线程时从一开始指定 `environment: local`，创建后只接受真实 `threadId`，并立即按项目路径和标题做核验；不要为初始化任务发起任何 worktree 请求。

> 在 MacroLens 项目中创建常驻部门线程时全部使用 local 环境。每次创建必须返回真实 `threadId` 才算成功；返回 `clientThreadId` 时立即停止后续批次并检查状态。初始化阶段禁止创建 worktree，只有收到实际编码任务后才 handoff 到 worktree。批量创建完成后核对线程数量、标题、状态，并确认 `git worktree list` 只有主目录。

## 最终结论

截图中的 9 个失败项不是实际 Codex 线程，也没有创建 Git worktree。真实的 30 条 MacroLens 线程未受影响。失败占位项无法通过线程归档 API删除，应通过刷新/重启 Codex 清除客户端临时状态；若仍存在，只能使用桌面端提供的失败项移除按钮手动清理。
