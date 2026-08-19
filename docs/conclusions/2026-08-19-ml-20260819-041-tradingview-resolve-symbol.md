# ML-20260819-041｜TradingView USUR 历史同步修复

## 1. 问题与场景

`TradingViewAdapter.fetch(mode="backfill")` 通过 chart session 请求
`ECONOMICS:USUR` 历史数据时，发出的 `resolve_symbol` 第三个参数是裸 JSON。
真实协议要求该参数是以 `=` 开头的 JSON symbol descriptor；裸 JSON 会导致服务端返回
`symbol_error invalid symbol` 和 `series_error`，从而中断历史同步。

任务边界限定为 TradingView Provider 与其 FakeSocket 测试，不修改 API、Schema、数据库、
前端或其他 Provider，也不保存 WebSocket 原始帧。

## 2. 分析过程

1. 在独立 worktree 中从 `origin/master` 的
   `e57b2f681cd7523ba94afa54103e2f43a3b89e38` 开始，避免主工作区的既有未提交内容。
2. 确认公开测试 seam 是 `TradingViewAdapter.fetch(..., mode="backfill")`，FakeSocket 会捕获
   Adapter 实际发送到 WebSocket 边界的完整 TradingView 帧。
3. 在既有回填测试中解码 `resolve_symbol` 帧，断言第三参数以 `=` 开头，并去掉前缀后解析
   JSON，确认 `symbol == "ECONOMICS:USUR"`。
4. 红灯显示实际第三参数为
   `{"symbol":"ECONOMICS:USUR","adjustment":"splits","session":"regular"}`，准确复现缺少
   `=` 的协议错误。
5. 检查替代假设：参数位置并未错，目标 descriptor 正处于第三参数；帧编码器也没有吞掉
   前缀，因为修复前输入本身就没有前缀。根因是 descriptor 构造时漏加协议标记。

事实：FakeSocket 捕获到的第三参数不以 `=` 开头。结论：在 JSON descriptor 构造处增加
协议前缀即可修复。未进行真实 TradingView 联网验收；服务端恢复历史数据属于基于既有真实
协议探针与本地协议回归测试的预期结果。

## 3. 解决流程

1. 先写协议回归断言并运行单测，得到红灯。
2. 将 `symbol_payload` 改为 `"=" + json.dumps(...)`，不改变 descriptor 的 JSON 内容。
3. 重跑同一回归测试得到绿灯。
4. 运行整个 `backend/tests/test_tradingview_provider.py`。
5. 对两个修改文件运行 Ruff，并执行 `git diff --check` 与调试标记检查。
6. 审查最终差异，确认没有 API/schema、持久化和范围外变更。

## 4. Agents、skills、tools 与文档

- Agents：当前 Codex 研发执行 Agent；未创建子 Agent 或用户可见子线程。
- Skills：`diagnosing-bugs` 用于建立可复现的红/绿反馈环和根因假设；`tdd` 用于在公开
  seam 先写失败断言、再做最小实现。
- Tools：PowerShell、Git、`pytest`、Ruff、`rg`、Codex `apply_patch`、计划更新工具。
- 已读项目文档：`AGENTS.md`、`.codex/organization.toml`、
  `docs/organization/README.md`、`CONTEXT.md`、
  `docs/architecture/tradingview-first-system-architecture.md`、
  `docs/architecture/tradingview-worker-implementation-map.md`。
- 已读开发链路宪法：`docs/governance/development-constitutions/README.md` 和
  `01-local-development-and-freeze.md`。本任务仅执行阶段 01；完成证据是独立 worktree、
  目标测试与 Ruff 通过、差异冻结并形成候选提交。未进入 PR、发布或部署阶段。
- 已读 skill 文档：`diagnosing-bugs/SKILL.md`、`tdd/SKILL.md`、`tdd/tests.md`、
  `tdd/mocking.md`。

## 5. 值得沉淀的经验

- TradingView chart session 的 symbol descriptor 不是普通 JSON 字符串；`=` 是协议语义的一部分，
  必须在外层帧编码前添加。
- WebSocket Provider 的协议回归应在公开 Adapter seam 捕获并解码出站帧，同时验证结构和业务
  symbol；只检查消息中包含 `resolve_symbol` 不足以发现格式错误。
- 红灯必须来自目标断言。最初系统 `pytest` 使用 Python 3.11 且无法导入项目包，该错误只是测试
  环境问题；切换为 Python 3.12 并显式使用 backend `src` 路径后，才得到有效红灯。
- 对单一协议缺陷，构造点的一行修复比新增抽象更稳妥；当前只有一个 descriptor 构造点，没有
  足够证据支持额外 helper。

## 6. 更好的初始提示词

> MacroLens 的 TradingView USUR 历史同步收到 `invalid symbol`。请在独立 worktree 中按 TDD
> 修复：通过现有 `TradingViewAdapter.fetch(mode="backfill")` FakeSocket 测试捕获并解码
> `resolve_symbol` 出站帧，先证明第三参数缺少 TradingView 要求的 `=` 前缀，再做最小修复。
> 断言去掉 `=` 后的 JSON 中 symbol 是 `ECONOMICS:USUR`；不得真实联网、保存原始帧、修改
> API/schema 或触碰其他 Provider。运行该回归测试、整个 TradingView Provider 测试文件和
> 修改文件的 Ruff，生成结论报告并提交，交付红/绿证据和 commit SHA。

## 7. 更优方案反思与一次解决提示词

当前方案已经是本场景的更优实现：缺陷位于单一 descriptor 构造点，公开 Adapter seam 已能完整
观察协议行为；新增内部 helper 或更大范围重构会增加接口面积而没有额外收益。可进一步优化的是
任务执行指令，明确 Python 3.12 与测试导入路径，避免把环境失败误判为业务红灯。

> 从最新 `origin/master` 创建独立 worktree。使用 Python 3.12，在现有
> `test_fetch_backfill_persists_chart_history_without_raw_payload` 中通过 FakeSocket 解码
> `resolve_symbol` 帧，断言 `p[2]` 以 `=` 开头且 `json.loads(p[2][1:])["symbol"]` 等于
> `ECONOMICS:USUR`。先运行该测试并保留缺少前缀的失败证据；然后只在 descriptor 构造处补
> `=`，重跑该测试、整个 `backend/tests/test_tradingview_provider.py` 和两份修改文件的 Ruff。
> 不联网、不保存帧、不改 API/schema。审查 diff、写结论报告并提交一个清晰 commit。

## 8. 验收证据

- 红灯：
  `py -3.12 -m pytest --override-ini=pythonpath=src backend/tests/test_tradingview_provider.py::test_fetch_backfill_persists_chart_history_without_raw_payload -q`
  → `1 failed`，失败点为 `assert symbol_descriptor.startswith("=")`。
- 绿灯：同一命令 → `1 passed in 0.43s`。
- 文件回归：
  `py -3.12 -m pytest --override-ini=pythonpath=src backend/tests/test_tradingview_provider.py -q`
  → `15 passed in 0.39s`。
- 静态检查：
  `py -3.12 -m ruff check backend/src/macrolens_worker/providers/tradingview.py backend/tests/test_tradingview_provider.py`
  → `All checks passed!`。
- 本地未启动或修改 Docker 容器，未使用远程服务端点。
