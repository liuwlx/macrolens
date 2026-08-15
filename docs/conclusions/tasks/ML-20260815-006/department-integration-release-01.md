# ML-20260815-006｜集成发布部席位 01 工作报告

- 席位：集成发布部 01
- 执行阶段：01 本地开发与候选冻结；只读加载 02 以确认发布边界
- 起点：`6b0cbd8d48c0b049b65c664c379606db09bfde87`
- 合并候选：`a16f2ca99e2102862d95a515c07429d6354adbb4`
- 共同基线：`aa739273710358e5f84efe724554df13efe4d3ea`
- 结果：本地无提交合并、冲突解决、完整门禁和冻结提交均在指定独立 worktree 内完成；最终 SHA 由本报告所在提交及交付消息确定。

## 1. 问题与场景

任务要求把已通过仓库六项门禁的基线修复候选 `6b0cbd8` 与四源 MappingProbe 候选 `a16f2ca` 合并成一个可追溯的本地生产前候选。必须完整保留 `a16f2ca` 自 `aa739273` 起的依赖链，并同时保留 MappingProbe 的 fail-closed、凭据脱敏、原始响应指纹和显式 live-audit 判定语义。

工作边界是只做本地集成，不 push、不创建或合并 PR、不修改 `master`、不打标签、不部署；不得启动 Docker/Compose，不执行 migration、seed、数据库同步/backfill、真实 Provider Probe、mapping approve、生产 Key 操作或 Scheduler 修改/重启。根工作区存在用户未提交治理文档，本任务仅按用户明确授权从绝对路径只读加载，不修改、复制或提交这些文件。

## 2. 分析过程

起始检查确认 HEAD 精确为 `6b0cbd8`，`git merge-base 6b0cbd8 a16f2ca` 为 `aa739273`，且 `aa739273` 是 `a16f2ca` 的祖先，因此候选依赖链完整可追溯。任务卡是 worktree 中既有未跟踪输入，最终纳入任务提交。

按任务卡执行 `git merge --no-ff --no-commit a16f2ca` 后产生 9 个内容冲突：

1. `backend/src/macrolens_api/cli.py`
2. `backend/src/macrolens_api/routers/admin.py`
3. `backend/src/macrolens_worker/live_audit.py`
4. `backend/src/macrolens_worker/providers/base.py`
5. `backend/src/macrolens_worker/providers/bea.py`
6. `backend/src/macrolens_worker/providers/bls.py`
7. `backend/src/macrolens_worker/providers/census.py`
8. `backend/src/macrolens_worker/providers/eia.py`
9. `backend/src/macrolens_worker/tasks/sync.py`

逐 hunk 追溯两边提交和 ML-002、ML-003、ML-005 报告后，冲突按以下原则解决：seed 不能直接把 READY 映射设为 verified/primary；显式 live audit 必须把 skipped 计入失败判定；BEA/Census 异常不回显响应行或冲突描述；BLS 保留脱敏 request/raw 和稳定 `captured_at` helper；Census 保留 `for=us:*` 的严格预检与 API 返回结构兼容；`sync.py` 同时保留 scoped sync、raw captured time、SQLAlchemy `.tuples()` 类型收窄和 `coverage_ratio` 精确 cast。没有使用整文件 ours/theirs 覆盖。

定向测试首次为 `78 passed, 3 failed`。三个失败仅是 EIA/BEA/Census fixture 固定 SHA：Windows `core.autocrlf=true` 把每个单行 JSON 的 LF 物化为 CRLF。staged fixture 与 `a16f2ca` 无差异，生产代码仍直接哈希 `response.content`；将工作树字节在内存归一化为 LF 后，三个 SHA 与候选 literal 完全一致。最小兼容修复新增 `.gitattributes`，只钉死 `backend/tests/fixtures/mapping_probes/*.json text eol=lf`，不改 fixture、测试 literal 或生产哈希逻辑。

静态门禁又发现两个最小兼容点：MappingProbe admin 路由装饰器为 101 字符，仅做换行；BEA probe 的可空 Key 在脱敏 helper 调用处收窄为“有 Key 时单元素 tuple、无 Key 时空 tuple”，不改变 Key 发送或脱敏行为。

Scheduler 审计需要区分生产源码和输入既有测试格式差异：

- `backend/src/macrolens_worker/scheduler.py` 在 `6b0cbd8`、`a16f2ca` 和当前 index 的 blob 均为 `1d857304659b829d9d741ee07463de29d77135a5`，生产 Scheduler 内容相对两个输入均为零修改。
- `backend/tests/test_scheduler.py` 两个输入本来就不同：候选为 `95e2b497...`，基线为 `619fec3a...`；当前 index 精确保留基线的 ruff-only `setattr(...)` 到属性赋值变化，没有本次新增 Scheduler 行为或测试语义。

## 3. 解决流程与验证结果

1. 完整读取 worktree 的 `AGENTS.md`、组织规则、任务卡；从根工作区授权绝对路径只读加载宪法索引、01 和 02，确认实际执行阶段仅为 01。
2. 核验分支、HEAD、共同基线和候选祖先链；执行指定无提交 merge。
3. 按 `resolving-merge-conflicts` skill 读取 primary sources、逐 hunk 合并、检查冲突标记并暂存全部冲突文件。
4. 按 `diagnosing-bugs` skill 用单一 SHA 测试建立紧凑 RED/GREEN 环，定位 CRLF fixture 根因并加入最小 `.gitattributes` 约束。
5. 使用指定 Python 3.12.9、`PYTHONUTF8=1`、`PYTHONPATH=backend/src` 执行定向与全量 Python 门禁。
6. 使用 Node 22.14.0/npm 10.9.2 执行 Web 门禁。当前 worktree 初始无依赖；与 ML-005 worktree 的锁文件 SHA-256 一致。临时 junction 可用于 lint/test，但 Turbopack 明确拒绝项目根外 symlink，因此将其移动到被忽略的 `tmp/node_modules`，随后在当前 worktree 运行 `npm ci`，取得有效本地 build。
7. build 后检查没有新增跟踪源码差异；执行 Scheduler blob/diff 审计、migration/seed 来源审计和 `git diff --check`。

最终验证摘要：

- MappingProbe/BLS/live-audit 定向 pytest：`81 passed in 6.22s`；BEA 收窄后紧凑回归再次通过。
- `ruff check backend`：`All checks passed!`
- `mypy backend/src`：`Success: no issues found in 70 source files`
- `pytest backend/tests`：`228 passed, 5 warnings in 17.17s`
- `npm --workspace apps/web run lint`：退出 0，`0 errors, 2 warnings`
- `npm --workspace apps/web run test`：`10 files, 32 tests passed`
- `npm --workspace apps/web run build`：Next 16.2.12 编译、TypeScript、15 个页面生成全部通过
- `git diff --check` 与 staged diff check：退出 0，无 whitespace error

pytest 的 5 条 warning 是既有 Starlette `httpx` TestClient 和 FastAPI `ORJSONResponse` 弃用提示；ESLint 的 2 条 warning 是 alerts 未使用 `LoadingBlock` 与 PostCSS 匿名默认导出。均无 error，也未在本票越界清理。

迁移、seed 和数据库操作证明：本任务只把候选已有 `backend/alembic/versions/0002_unique_primary_source.py` 与 `database/seed/source_registry.json` 变更纳入 Git 历史。实际命令日志只有只读检查、Git merge/diff/add、Python 测试/静态检查、npm 依赖安装和 Web 门禁；没有执行 `alembic upgrade`、seed CLI、`seed_all`、sync/backfill、数据库客户端或连接命令，也没有配置数据库端点。Docker/Compose、真实 Probe、approve、生产 Key 和 Scheduler 启停命令同样为零。

## 4. Agents、skills、tools 与文档

- Agents：本轮由 MacroLens 集成发布部席位 01 独立完成；未启动子 Agent。输入候选来自 ML-002/ML-003 研发席位与 ML-005 基线门禁席位，其报告只作为 primary-source 证据读取。
- Skills：`resolving-merge-conflicts` 用于追溯双方意图、逐 hunk 解决和完成 merge；`diagnosing-bugs` 用于建立固定 SHA 反馈环、排序并证伪假设、锁定 Windows CRLF 根因。后者直接促成 `.gitattributes` 的窄范围修复，而不是修改业务哈希。
- Tools：PowerShell、Git、`rg`、`apply_patch`、计划工具、Python 3.12.9、pytest、ruff、mypy、Node 22.14.0、npm 10.9.2、ESLint、Vitest、Next 16.2.12。未使用网络检索、浏览器、Docker、数据库、Provider Probe、Key、approve、部署或 Scheduler 工具。
- 已读文档：worktree `AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`、ML-20260815-006 任务卡、ML-002/003/005 部门与总结报告、`resolving-merge-conflicts/SKILL.md`、`diagnosing-bugs/SKILL.md`。
- 宪法来源：完整读取 `E:\workerspace\projects\20260709\macrolens\docs\governance\development-constitutions\README.md`、`01-local-development-and-freeze.md`、`02-pr-merge-and-release.md`。这些文件来自根工作区用户未提交治理文档，只读加载，未复制、未修改、未纳入候选。
- 阶段证据：阶段 01 以独立 worktree、完整门禁、预期 diff、Scheduler 生产 blob 一致、`git diff --check` 和本地候选提交收口；阶段 02 仅加载规则并确认未进入 push/PR/master merge/tag。

## 5. 值得沉淀的经验与模式

- 固定响应指纹测试必须同时固定 fixture 的物理行尾；否则同一 Git blob 在 Windows checkout 后会产生不同 SHA，形成平台假回归。
- 冲突解决不能按文件选边。安全语义、审计集合语义、类型收窄和机械格式化常落在同一 hunk，必须逐项组合并通过定向测试证明。
- “Scheduler 零修改”应至少比较两个输入和 index 的生产源码 blob；测试文件若输入已不同，应单独说明来源，不能宣称所有相关文件字节相同。
- Web 门禁不仅依赖 Node 版本，也依赖依赖树的物理位置。lint/test 可以沿外部 junction 解析，但 Turbopack 会拒绝项目根外 symlink；正式 build 应使用当前 worktree 的锁文件安装。
- migration/seed 文件进入代码历史与执行数据库变更是两件事。报告应分别记录文件来源和命令执行事实，避免把“包含迁移”误报为“已迁移”。

## 6. 更好的初始提示词

> 请在指定独立 worktree，把已通过质量门禁的基线候选与四源 MappingProbe 候选做一次本地 merge。先确认两个 SHA 和共同祖先，完整保留 MappingProbe 的拒绝上线、Key 脱敏、响应指纹和显式审计语义；冲突要逐文件说明，不要整文件选边。使用指定 Python 3.12 和 Node 22 跑 MappingProbe/live-audit 定向测试及项目六项全量门禁。特别检查 Windows 行尾不会改变固定 fixture SHA，并用 blob 同时证明生产 Scheduler 与两个输入一致。只纳入 migration/seed 文件，不执行它们；禁止 Docker、数据库、真实 Probe、approve、Key、push、PR、标签和部署。最后生成两份七节报告并提交一个本地 merge 候选。

## 7. 当前场景的一次性更优方案提示词

> 在 `E:\workerspace\projects\20260709\macrolens-worktrees\ML-20260815-006-integration-release-01` 从 `6b0cbd8` 执行 `git merge --no-ff --no-commit a16f2ca`。合并前只读加载根工作区宪法，但绝不复制或写根工作区。冲突按三层矩阵处理：第一层保留 seed/probe/approve 的 fail-closed 和 fingerprint 绑定；第二层保留 Provider raw/request/error 的递归脱敏与原始 bytes SHA；第三层叠加 ML-005 的 ruff/mypy 类型和格式修复。先运行固定 SHA 的单测反馈环；若 Windows checkout 改变 fixture 字节，使用最窄 `.gitattributes text eol=lf` 修复，不改 literal。随后依次运行定向 pytest、ruff、mypy、后端全测、Web lint/test/build 和 diff check；Web 依赖必须在当前 worktree 按相同 lockfile 安装，不能让 Turbopack 使用项目根外 symlink。用 `git rev-parse <sha>:backend/src/macrolens_worker/scheduler.py` 与 index blob 三方比对证明生产 Scheduler 零修改，单独记录输入既有测试格式差异。报告列出全部原始摘要、未执行操作与只读宪法来源，最后创建一个双 parent 本地 merge commit，不 push、PR、tag 或部署。
