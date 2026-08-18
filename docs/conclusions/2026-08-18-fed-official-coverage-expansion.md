# Federal Reserve 官方 XML 覆盖扩展结论

## 1. 问题与场景

在已经接入 Federal Reserve Board G.17、H.8、G.19、H.10 的基础上，继续处理“能在公开官方数据范围内解决”的映射。目标是把已有的 FRED 生产映射切换到 Federal Reserve Board 原始发布文件，同时保留原始文件、Series 身份、Period 和 vintage 追踪能力。

本轮处理对象：

- H.4.1 总资产；
- H.4.1 美联储持有的 Agency MBS；
- CHGDEL 信用卡贷款逾期率；
- SLOOS 大中型企业 C&I 贷款标准净收紧比例。

准备金余额没有强行切换：H.4.1 候选 Series 与 FRED `WRESBAL` 在历史值上存在差异，当前证据不足以证明两者是同一统计口径。

## 2. 分析过程

1. 检查现有 `FED_BOARD_FILES` Adapter、注册表和数据 readiness 规则，确认 XML ZIP 已支持精确 Series 名称、属性断言、频率归一化、首期边界和原始字节保留。
2. 只读下载官方 XML ZIP 并检查 Series attributes 与 Obs：
   - H.4.1 总资产：`RESPPA_N.WW`；
   - H.4.1 Agency MBS held outright：`RESPPALGASMO_N.WW`；
   - CHGDEL：`STFBQDCC%STFBAILCC_XEOP_MA.Q`；
   - SLOOS：`SUBLPDCILS_N.Q`。
3. 将 CHGDEL 和 SLOOS 的官方 XML 数值与原 FRED 映射的公开 CSV 做逐期首尾核对；两者首期和最新值一致。
4. 对 H.4.1 准备金候选 Series 做同样核对，发现值不一致，因此保留 FRED 映射并记录为待确认事项，而不是猜测。
5. 通过 fixture 测试锁定三类 XML 身份和周度/季度 Period 归一化规则，再执行真实只读解析。

## 3. 解决流程

- 在 `database/seed/source_registry.json` 将 4 个指标的 `recommended_source` 和 `provider_series_id` 改为 Federal Reserve Board 原始 Series，并写入官方文件 URL、格式、Series attributes、历史首期和数据集身份。
- 在 `DATA_COLLECTION_MODULE_REVIEW.json` 更新 Provider 覆盖统计：Fed Board 8 条，FRED 4 条。
- 在 `backend/tests/test_fed_board.py` 增加 H.4.1、CHGDEL、SLOOS 的 XML identity fixture。
- 在 `backend/tests/test_registry_and_schema.py` 增加来源和 Series 身份断言。
- 保持 `FED_BOARD_FILES` 的 fail-closed 行为：Series 不唯一、属性漂移、空 Obs 或历史首期不符时拒绝发布。

## 4. 使用的 Agents、skills、tools 和文档

- Agents：本轮未创建或调用额外 Agent；由当前项目主线程在独立候选 worktree 中完成。
- Skills：沿用本工作流已读取的 `codebase-design`、`tdd`；本轮按 Provider 边界和 fixture-first 校验执行。
- Tools：`exec_command`（只读官方文件、运行测试和静态检查）、`apply_patch`（修改代码/注册表/文档）、官方网页检索（核对 H.4.1 公开语义）。
- 已读取文档：根目录 `AGENTS.md`、`docs/organization/README.md`、`.codex/organization.toml`、`docs/governance/development-constitutions/README.md`、`docs/governance/development-constitutions/01-local-development-and-freeze.md`。

## 5. 可沉淀的经验和模式

- 对同一官方机构，优先以 Dataset/Release 文件为批量入口，再由注册表配置 Raw Series 身份；不要为每条 Series 创建独立 Adapter。
- Series 名称不够时，必须同时固定 release-specific attributes；例如 `LOANTYPE`、`MEASURE`、`PANEL`、`SIZE` 等字段决定经济语义。
- FRED 可作为对照验证和历史发现入口，但不能用 FRED ID 代替官方生产真源。
- 发现值差异时应暂停切换并记录口径待确认，不应通过缩放、取整或覆盖 vintage 让结果“看起来一致”。
- “切换来源”不等于“新增指标”：本轮 READY 指标仍为 33 条，Provider 分布变化为 Fed Board 8、FRED 4。

## 6. 更好的初始提示词

请在 MacroLens 的独立 Git worktree 中，基于现有 `FED_BOARD_FILES` Adapter，检查并接入 Federal Reserve Board 的 H.4.1 总资产/MBS、CHGDEL 信用卡逾期率和 SLOOS 大中型企业 C&I 贷款标准。先只读下载官方 XML ZIP，输出每个候选指标的 Series name、全部关键 attributes、首期、最新期、Obs 数量，并与现有 FRED 映射做逐期身份/数值核对；只有证据一致的才修改注册表。补充 fixture、历史边界、属性漂移和空数据测试，运行后端全量门禁。准备金若存在口径差异必须保留原映射并列为阻塞。不要 seed、不要同步数据库、不要部署、不要推送或合并。

## 7. 当前方案的更优版本

更优做法是先实现一个通用的“官方 Release identity audit”命令：读取注册表中所有待切换的 FRED/官方候选对，自动下载双方数据，输出 identity matrix、首期/末期、频率转换、单位缩放、最大绝对差和差异原因；只有 audit 状态为 `approved` 的映射才能生成注册表补丁。这样可以把本轮人工检查沉淀为可重复的审批证据，并扩展到 H.4.1 其他资产、SLOOS 其他贷款类别和 CHGDEL 其他规模分组。

## 8. 验证和未完成项

真实只读解析结果：

| 指标 | 官方 Series | HTTP | Obs | 首期 | 最新期 |
|---|---|---:|---:|---|---|
| 总资产 | `RESPPA_N.WW` | 200 | 1,235 | 2002-12-18 | 2026-08-12 |
| Agency MBS | `RESPPALGASMO_N.WW` | 200 | 1,235 | 2002-12-18 | 2026-08-12 |
| 信用卡逾期率 | `STFBQDCC%STFBAILCC_XEOP_MA.Q` | 200 | 141 | 1991-01-01 | 2026-01-01 |
| SLOOS C&I 标准 | `SUBLPDCILS_N.Q` | 200 | 146 | 1990-04-01 | 2026-07-01 |

通过：Python 3.12 后端测试 `267 passed, 5 warnings`；`ruff check backend`；`mypy backend/src`；Web lint（2 个既有 warning）；Web build。

未通过/未完成：Web test 在当前 Node `v20.11.1` 下因依赖 CommonJS/ESM 加载冲突失败，项目要求 Node `>=22`；准备金 Series 仍待 H.4.1 与 FRED 口径确认；尚未执行数据库 seed、远程同步、部署和服务器验收。

候选分支：`codex/ML-20260818-fed-board-g17`。
