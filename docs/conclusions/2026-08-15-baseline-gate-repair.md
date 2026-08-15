# 发布基线门禁修复总结

- 任务 ID：`ML-20260815-005`
- 阶段：01 本地开发与候选冻结
- 起始提交：`aa739273710358e5f84efe724554df13efe4d3ea`
- 结果：六项强制门禁全部通过；候选只在独立 worktree 中形成，未合并、推送、部署或接触数据库与生产数据。

## 1. 问题与场景

四源 MappingProbe 候选不能进入集成，因为仓库基线同时存在四类阻塞：FastAPI 0.141.1 的惰性 `_IncludedRouter` 使旧路由测试访问不存在的 `.path`；后端全量 ruff/mypy 有历史错误；本机默认 Node 20 不满足项目 Node 22 要求且 worktree 没有依赖；安装依赖后 Web lint 又暴露 React effect 状态更新和 E2E `any` 错误。修复必须保持 Scheduler 源文件不变，并禁止迁移、seed、数据库同步、真实 Probe 和部署。

## 2. 分析过程

路由测试在当前 master 和候选上均稳定 RED，证明不是 MappingProbe 回归。运行时检查显示 `app.routes` 包含 FastAPI 私有 `_IncludedRouter`，而 `app.openapi()["paths"]` 有 70 条公开路径并完整覆盖测试要求的 18 条，因此正确 seam 是 OpenAPI 公共契约。

静态门禁方面，既有报告记录 ruff 303 项、mypy 35 项；本轮在边界缩减过程中独立观察到 ruff 249 项 E501 等错误，格式化收口后 mypy 剩余 16 项真实类型错误。Web 在未修改 master 文件上用同一 ESLint 复现 52 errors、2 warnings，其中 9 项是 `react-hooks/set-state-in-effect`，43 项是 E2E 异构 payload 的 `no-explicit-any`。

审查中曾发现自动修复触及 `scheduler.py`，立即要求恢复。最终同时比较工作区、暂存区和 HEAD，Scheduler 内容 diff 均为零。对 Web 状态重写又发现 URL searchParams 可能不再随客户端导航同步，因此在最终 remediation 中为 Documents、FOMC 和 Workspace 补回 URL 外部输入同步，并只对相应 setState 行做精确规则说明。

## 3. 解决流程

1. 从当前 master 创建 `codex/ML-20260815-005-baseline-gates` 独立 worktree。
2. TDD RED→GREEN：将 `test_api_route_surface` 从遍历私有 `app.routes` 改为检查 `app.openapi()["paths"]`。
3. 对 ruff 报错文件做语义不变的换行/import 整理；仅为 Alembic 生成文件长行和必须保持不动的 Scheduler import 顺序配置精确 per-file-ignore。
4. 精确修复 mypy：SQLAlchemy Row 使用 `.tuples()`，收窄可空值和协程类型，调整 Vector fallback 类型构造，并对缺少 py.typed/stub 的具体第三方 import 使用局部说明；没有启用全局 `ignore_errors` 或 `ignore_missing_imports`。
5. 固定 Node 22.14.0/npm 10.9.2，执行 `npm ci`；修复 React hooks lint，给 E2E 异构运行验收边界增加有理由的文件级 `no-explicit-any` 说明。
6. 纳入 Next 16 每次构建都会生成且 tsconfig 已引用的 `next-env.d.ts`，并只向 tsconfig 增加 `.next/dev/types/**/*.ts`。
7. 独立运行六项门禁；构建后复查没有将 `node_modules`、`.next` 或锁文件变化纳入候选。

最终结果：

- `ruff check backend`：通过，`All checks passed!`
- `mypy backend/src`：通过，66 个源文件无错误
- `pytest backend/tests`：134 passed，5 warnings
- `npm --workspace apps/web run lint`：退出 0，0 errors，2 warnings
- `npm --workspace apps/web run test`：8 files、21 tests passed
- `npm --workspace apps/web run build`：Next.js 16.2.12 编译、TypeScript、15 个静态页面全部通过

## 4. Agents、skills、tools 与文档

- Agents：研发席位 Dewey 完成主要实现与静态门禁修复；Darwin 完成边界核对、部门报告和暂存但未完成提交；Aquinas 被分配 Web 窄范围 remediation，但执行通道无进程、无文件变化后关闭；主线程完成独立复验、风险审查、URL 同步 remediation、总报告和提交收口。
- Skill：`tdd`，将 OpenAPI paths 明确为公共测试 seam，并完成路由 RED→GREEN；其要求直接避免继续依赖 FastAPI 私有路由对象。
- Tools：PowerShell、Git/worktree、`rg`、`apply_patch`、Python 3.12.9、pytest、ruff、mypy、Node 22.14.0、npm 10.9.2、ESLint、Vitest、Next build、计划与多 Agent 工具。
- 已读文档：根与 worktree `AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`、`docs/governance/development-constitutions/README.md`、`01-local-development-and-freeze.md`、`ML-20260815-005` 任务卡、`ML-20260815-004` 诊断报告、`tdd/SKILL.md` 及其测试约束。
- 完成证据：六门禁全绿、Scheduler 零差异、构建后生成物边界检查、`git diff --check` 和候选提交 SHA。

## 5. 值得沉淀的经验与模式

- 框架升级后的契约测试应使用 OpenAPI/HTTP 公共 seam，不遍历私有容器结构。
- 基线门禁债务可以需要大量机械格式化，但必须把格式化、类型收窄、规则豁免和真实行为变化分开审查。
- “保持 Scheduler 不动”应落实为 blob/diff 零差异，而不是主观判断“只改 import 没关系”。
- React hooks lint 不能只以消错为目标；派生状态重写后仍要检查 URL、路由和其他外部输入能否继续同步。
- Next build 会维护类型入口；构建后必须再次检查 Git 状态，把稳定构建输入与 `.next` 生成目录区分开。
- 工具链版本错误会制造假阻塞：Python 3.11/Node 20 的结果不能替代项目要求的 Python 3.12/Node 22 验收。

## 6. 更好的初始提示词

> 请在独立 worktree 修复 MacroLens 当前 master 的发布基线门禁。先用 Python 3.12 和 Node 22 复现六项强制检查，按“路由契约测试、ruff、mypy、Web lint、Web test、Web build”分类处理；FastAPI 路由面只断言 OpenAPI 公共路径。只允许门禁必需的格式化、精确类型修复和局部规则说明，Scheduler 源文件必须与 HEAD 完全一致。完成后运行六项全量检查、排除 node_modules/.next、生成七节报告并提交候选；禁止合并、部署、迁移、seed、数据库同步、真实 Probe 和修改 Scheduler。

## 7. 当前场景的一次性更优方案提示词

> 从当前 master 创建基线门禁修复 worktree，先固定 Python 3.12.9、PYTHONUTF8=1、Node 22.14.0 和 npm 10.9.2。用失败测试证明 FastAPI 私有 route 遍历不兼容，再改为 OpenAPI paths。对 ruff/mypy 先导出错误分类：E501/import 只做机械格式化，Alembic 生成文件和 Scheduler 只允许精确配置，第三方缺失 stub 只允许模块级或 import 行说明，真实类型错误逐项修复。安装锁文件依赖后复现 Web lint；React effect 问题要保留 URL searchParams 同步语义，E2E `any` 仅在异构验收边界说明。将 Next 自动要求的 next-env 和 dev types include 固化后，连续运行六项门禁并确认第二次 build 不再制造额外源码差异。最后审查 staged diff 不含 Scheduler、node_modules、.next、锁文件或生产配置，再写报告和提交本地候选。
