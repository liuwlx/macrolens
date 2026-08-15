# 四源 MappingProbe 本地集成总结

## 1. 问题与场景

ML-20260815-006 要把质量门禁候选 `6b0cbd8` 和四源 MappingProbe 候选 `a16f2ca` 合并为单一本地生产前候选。难点不是简单叠加文件，而是在 9 个冲突文件中同时保留 MappingProbe fail-closed、凭据不落盘、响应指纹、显式 live-audit 语义，以及基线 ruff/mypy/Web 门禁修复。任务只允许本地集成，不允许任何发布、部署、Docker、数据库、真实 Provider 或 Scheduler 操作。

## 2. 分析过程

Git 证据确认共同基线为 `aa739273`，且候选从该共同基线到 `a16f2ca` 的完整依赖链可达。9 个冲突集中在 API seed/admin、live audit、四源 adapter 基类与实现、sync pipeline；其本质分为安全/治理行为与基线格式/类型修复两类。

逐 hunk 选择后，seed 继续要求有效 probe approval 与 fingerprint 才能保持 verified/primary；显式 audit 继续评价所有请求 Provider；三源异常不泄漏响应内容；BLS raw/request 保持脱敏并使用稳定 captured time；scoped sync 与 ingestion 类型修复同时保留。

首轮定向测试暴露一个输入候选未覆盖的 Windows 兼容缺口：三个单行 JSON fixture 在 `core.autocrlf=true` 下变成 CRLF，导致 raw SHA 与固定 literal 不同。候选 blob、测试 literal 和生产代码都正确，缺少的是工作树 EOL 契约。因此新增仅覆盖 MappingProbe fixture 的 `.gitattributes` LF 规则。静态门禁随后只需一处装饰器换行和一处 BEA 可空 Key 类型收窄。

## 3. 解决流程与结果

执行流程为：规则与任务卡加载 → 候选祖先链核验 → `--no-ff --no-commit` merge → 按冲突 skill 追溯和逐 hunk 解决 → 固定 SHA 诊断环 → 定向测试 → 六项全量门禁 → Scheduler/migration/seed/diff 审计 → 报告与本地提交。

最终结果：

- 定向 pytest：`81 passed`
- ruff：全部通过
- mypy：70 个源文件无问题
- 后端全测：`228 passed, 5 warnings`
- Web lint：0 errors、2 warnings
- Web test：10 files、32 tests passed
- Web build：Next 16.2.12 编译、类型检查和 15 个页面生成通过
- `git diff --check`：通过

生产 `backend/src/macrolens_worker/scheduler.py` 在两个输入和当前 index 的 blob 均为 `1d857304659b829d9d741ee07463de29d77135a5`。`test_scheduler.py` 的两输入原有 ruff-only 差异由基线版本保留，没有新增 Scheduler 行为。migration `0002` 与 seed registry 仅纳入候选历史；没有执行 migration、seed、数据库同步/backfill 或数据库连接。Docker/Compose、真实 Probe、approve、Key 操作、Scheduler 修改/重启、push、PR、master merge、tag 和 deploy 均未发生。

## 4. Agents、skills、tools 与文档

- Agent：集成发布部席位 01；未启动子 Agent。
- Skills：`resolving-merge-conflicts` 约束 primary-source 追溯和逐 hunk 合并；`diagnosing-bugs` 约束 SHA 失败的紧凑反馈环、假设排序和最小兼容修复。
- Tools：PowerShell、Git、`rg`、`apply_patch`、计划工具、Python 3.12.9、pytest、ruff、mypy、Node 22.14.0、npm、ESLint、Vitest、Next。
- 文档：worktree 的 `AGENTS.md`、组织配置/手册、任务卡、ML-002/003/005 报告及两个 skill 文件。
- 宪法：从根工作区绝对路径只读完整加载开发宪法索引、01 本地开发与候选冻结、02 PR 合并与版本发布；这些用户未提交治理文档未修改、未复制、未纳入候选。
- 阶段：实际完成 01 本地集成与冻结；02 只用于确认发布禁区，没有进入 PR/发布；03 不适用。

## 5. 值得沉淀的经验与模式

- 原始响应 SHA 的测试 fixture 必须声明 `eol=lf`，否则平台 checkout 会改变证据字节。
- 安全合并要按语义层处理：治理状态、脱敏/指纹、审计 verdict、类型/格式分别核对，不能用“测试能跑”替代意图审查。
- Scheduler 零修改证明应以生产 blob 三方一致为主，并把输入已有测试差异单列。
- 有相同 lockfile 不代表外部 symlink 依赖能完成生产构建；Turbopack 要求依赖位于项目文件系统根内。
- 数据库变更文件的 Git 集成不构成执行授权，必须在命令日志中证明没有迁移或 seed 行为。

## 6. 更好的初始提示词

> 把质量门禁分支和四源数据探测分支在指定独立 worktree 做一次本地合并。冲突时优先保护“未探测不得上线、Key 不落盘、响应原始字节可指纹、显式审计有缺项就失败”，同时保留基线格式和类型修复。使用指定 Python/Node 跑定向与全量门禁；Windows 下固定响应 fixture 必须保持 LF。证明生产 Scheduler 与两个输入完全相同，迁移和 seed 只合并文件不执行。生成七节报告和一个本地候选提交，不做任何远程或生产操作。

## 7. 当前场景的一次性更优方案提示词

> 从 `6b0cbd8` 无提交 merge `a16f2ca`，先保存 9 个冲突文件清单和双方 commit/report 意图。按 fail-closed、脱敏/指纹、audit verdict、类型门禁四列逐 hunk 决策；`sync.py` 同时保留 scoped IDs、captured raw time、`.tuples()` 和精确 cast。先以三个固定 SHA 用例构建 Windows 可复现环，并用 `.gitattributes` 锁定 fixture LF。使用 Python 3.12.9 和 Node 22.14.0 依次跑 81 项定向、ruff、mypy、228 项后端全测、Web lint/32 tests/build；依赖按当前 lockfile 安装在本 worktree。最后比较两个输入与 index 的 Scheduler 生产 blob，检查 build 后 Git 状态和 staged diff，记录 migration/seed/DB 零执行，写两份七节报告并创建本地双 parent merge commit。
