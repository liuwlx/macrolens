# ML-20260820-051｜TradingView 非日度 history_gap warning 集成发布

## 1. 问题与场景

本任务由集成发布部独立审查并发布候选
`48bf97ca0696663e8be0a3f401007ae22b10aaa6`。精确基线为
`origin/master@564c3df2df26bbdcf998bcccc76839bce9587605`，候选是该基线的单一直接子提交。

业务目标是保留真实 `history_gap` 证据，同时只把 TradingView source-native 非日度历史回填中的
该问题降为 warning：Provider 必须是 `TRADINGVIEW_WEB`，mode 必须精确为 `backfill`，frequency
必须是 weekly、monthly、quarterly 或 annual。daily、incremental、vintage_backfill、其他 Provider
不命中该新规则；不修改 API、Web、数据库 schema/migration 或 registry；不部署。

工作在独立 worktree
`E:\workerspace\projects\20260709\macrolens-worktrees\ML-20260820-051-integration-release`
和分支 `codex/ML-20260820-051-tradingview-gap-warning` 中完成。主工作区存在大量其他线程的未提交
改动，本任务没有触碰、覆盖或回滚这些内容。

## 2. 分析与独立审查

固定 diff 为
`git diff 564c3df2df26bbdcf998bcccc76839bce9587605...48bf97ca0696663e8be0a3f401007ae22b10aaa6`，
仅包含 Worker ingestion quality/sync、两个后端测试文件和来源任务结论报告。没有 API、Web、OpenAPI、
schema、migration 或 registry 路径变更，`git diff --check` 通过。

按 `code-review` skill 并行执行 Standards 与 Spec 两个隔离审查轴：

- Standards 轴发现阶段 01 的硬阻断：来源报告明确没有执行 Web lint/test/build。集成任务随后在锁文件
  对应的 Node 22.14.0/npm 10.9.2 环境安装依赖并补齐三项门禁，阻断已关闭。该轴另提出把
  `CompletenessIssue` 的 history-gap 字段封装为领域类型的可选重构；这是判断性 code smell，当前
  数据类规模和单一创建点尚不值得扩大本次发布范围。
- Spec 轴确认本次新分支的 provider、mode、issue code、frequency 四维边界正确，warning 证据确实进入
  `QualityResult` 持久化路径，无超范围文件；同时按最严格字面解释指出基线既有的 TradingView
  `stale_latest_period` 和缺源 warning 仍存在。该行为在基线已由独立测试锁定，本候选没有新增或扩大；
  本任务“审查边界仅本次 history_gap warning 规则”不授权逆转既有质量策略，因此不作为候选回归修改。

实现审查确认：完整性检查仍计算并报告真实缺口，没有补造 observation 或关闭 contiguous 检查；
warning 记录的 `period_start` 保存首个缺口，message 保存 source_series_id、provider_series_id、
missing_period_count、source_frequency 和 allowed count。测试真值表覆盖四个 allow case，以及 daily、
incremental、vintage_backfill、其他 Provider 和未知频率的 blocking case；既有测试继续覆盖其他质量冲突。

## 3. 解决与发布工作流

1. 重新加载 `AGENTS.md`、组织规则、上下文和阶段 01/02 宪法，确认任务卡、授权与禁止部署边界。
2. fetch 远程并核对 `origin/master` 仍精确等于指定基线；确认目标分支和标签在本地与远程均不存在。
3. 从候选 SHA 创建独立 integration worktree 和用户指定分支，不接触主工作区改动。
4. 固定三点 diff/提交列表，执行 Standards/Spec 双轴独立审查，逐项核验规则边界、禁止路径与 warning
   持久化证据。
5. 使用 Python 3.12.9 和 Node 22.14.0/npm 10.9.2 补齐完整本地门禁；OpenAPI YAML check 通过，
   重新生成 YAML/JSON 后 Git 零差异。
6. 只新增本集成结论报告并形成冻结发布提交；随后进入阶段 02，push、创建 ready-for-review PR、等待
   backend/frontend/containers/acceptance 四项 CI 全绿、合并 master，并在 merge SHA 创建唯一正式标签。
7. 不进入阶段 03，不启动本地 Docker/Compose，不连接生产数据源，不部署。

PR、合并 SHA 和标签在本报告进入 PR 时尚不存在，由任务最终回执与 GitHub 不可变记录补充追溯。

## 4. Agents、skills、tools 与已读文档

Agents：

- 当前集成发布 Agent：基线核验、审查汇总、门禁、冻结和阶段 02 发布。
- Standards 独立审查 Agent `Mendel`。
- Spec 独立审查 Agent `Sartre`。

Skills：

- `code-review`：把项目规范与任务规格拆成两个隔离审查轴，直接发现并关闭缺失 Web 门禁。
- `github:yeet`：约束发布前 scope/status 核验、显式提交、push 和 PR 描述；分支名按用户指定值，PR
  按任务要求创建为 ready-for-review。

Tools：Git、PowerShell、`rg`、`apply_patch`、Python 3.12.9、ruff、mypy、pytest、Node 22.14.0、
npm 10.9.2、ESLint、Vitest、Next.js build、OpenAPI 生成脚本、并行审查 Agent、GitHub CLI/应用和计划工具。

已读文档：

- `AGENTS.md`
- `.codex/organization.toml`
- `docs/organization/README.md`
- `CONTEXT.md`
- `docs/governance/development-constitutions/README.md`
- `docs/governance/development-constitutions/01-local-development-and-freeze.md`
- `docs/governance/development-constitutions/02-pr-merge-and-release.md`
- `code-review/SKILL.md`
- `github:yeet/SKILL.md`
- 来源任务报告、相关 Worker 源码、测试、OpenAPI 生成脚本和 CI workflow。

## 5. 门禁证据、阶段结果与经验沉淀

本地冻结证据：

- `ruff check backend`：通过。
- `mypy backend/src`：74 个 source files，无问题。
- `PYTHONPATH=backend/src pytest backend/tests`：346 passed，5 个既有 FastAPI/Starlette deprecation warning。
- `npm --workspace apps/web run lint`：0 error，2 个未修改文件中的既有 warning。
- `npm --workspace apps/web run test`：14 files、51 tests 全部通过。
- `npm --workspace apps/web run build`：Next.js 16.2.12 production build 通过，14 routes 完成。
- `python scripts/generate_openapi.py --check`：current，75 paths。
- `python scripts/generate_openapi.py --json` 后 YAML/JSON Git 零差异。
- `git diff --check`：通过；工作树在新增本报告前为 clean。

执行阶段：阶段 01 在独立 worktree 完成审查与完整门禁；阶段 02 按任务继续完成 PR、四项 CI、合并和
标签；阶段 03 明确不执行。

值得沉淀的模式：

1. source-native 非连续历史应保留真实质量问题，只在处置层用 provider/mode/code/frequency 正向白名单
   改变 severity，不能关闭完整性算法或伪造缺失值。
2. warning 的可审计性要沿完整路径核对：issue 结构化字段、持久化 `period_start`、最终 message 缺一不可。
3. “候选没有 Web 改动”不能豁免发布门禁；集成发布必须在冻结候选上补齐完整 Web lint/test/build。
4. 规格中的“仅”要区分本次新增规则边界与基线既有独立策略；若要求废除既有 warning，任务卡应明确
   列出 stale/missing-source 策略及迁移风险，避免在集成审查中隐式扩大范围。
5. 生成契约无业务 diff 时仍应执行 generator check，并用 YAML/JSON 零差异证明 OpenAPI current。

## 6. 反推的更好初始提示词

> 请独立审查并发布一个 TradingView 历史回填质量规则：只有 TradingView 的完整历史回填，在周、月、
> 季、年数据出现真实历史空档时，才把 history_gap 从阻断改为警告；日度、增量、历史版本回填、其他数据源
> 和本次规则之外的质量问题都不能因这项改动被放宽。警告必须保存来源序列、Provider symbol、频率、缺口数
> 和首个缺口日期。不要补造数据，不要关闭连续性检查，不改 API、网页、数据库或 registry。请从指定基线和
> 候选创建独立 worktree，双轴审查差异，运行完整后端/Web/OpenAPI 门禁；全部通过后推送指定分支，创建
> PR，等 backend/frontend/containers/acceptance 四项 CI 全绿再合并 master，并在合并提交创建指定标签。
> 不部署，最终返回 PR、合并 SHA、标签和证据报告。

## 7. 当前场景一次解决的更优方案提示词

更优方案是先把“本次新规则”与“基线既有 warning”写成同一张明确决策表，并增加持久化层回归断言，
从源头消除规格歧义：

> 在上述发布流程不变的前提下，先为 `ingestion_issue_severity` 建立完整决策表：新增规则只允许
> TRADINGVIEW_WEB + backfill + history_gap + weekly/monthly/quarterly/annual；daily、frequency=None、
> incremental、vintage_backfill、其他 Provider 必须 blocking。明确声明基线既有的 TradingView stale 和
> missing-source warning 是“保留”还是“废除”，不要让集成线程猜测。再增加一个不访问外部服务的同步持久化
> 测试，断言 warning `QualityResult` 的 rule_code、severity、period_start 和 message 完整包含内部 source ID、
> Provider symbol、频率、缺口数及 allowed count；同时断言同批次的其他 blocking issue 仍会 quarantine。
> 完成双轴复审、完整本地门禁和 OpenAPI YAML/JSON 零差异后，再进入 PR、四项 CI、merge 和 tag；不部署。
