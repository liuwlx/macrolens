# 下一步公式边界与 Node 22 门禁结论

## 1. 本轮目标

在 Fed、BEA 和 Census 接入完成后，继续处理剩余阻塞，并验证上一轮 Web test 的 Node 版本问题。

## 2. BEA 派生概念结论

官方 BEA API 的 `NIUnderlyingDetail/U20404/M` 提供了 `PCE services excluding energy`，但该序列仍包含住房，不能直接作为 `Core Services Excluding Housing`。同一数据集只提供长期护理相关组件，例如 nursing homes、home health care 等，没有覆盖完整长期护理服务的单一官方行。

当前数据库虽然存在 `derived_definition` 和 `series_dependency`，但浏览器分析代码明确禁止在没有版本绑定的情况下解释任意 `weight_expression`。因此本轮没有把两个概念伪装成 READY，也没有写入未经批准的公式。

后续公式需要至少明确：

- 组件集合；
- 月度权重来源和 vintage 对齐方法；
- Fisher/Laspeyres/Paasche 或其他指数方法；
- 缺失组件和修订处理；
- `formula_version`、effective period 和依赖关系。

## 3. Node 22 验证

本机已有 Node `v22.14.0`。在当前候选 worktree 中临时切换 PATH 后：

- Web test：11 个测试文件、35 个测试全部通过；
- Web lint：通过，保留 2 个既有 warning；
- Web build：通过。

没有修改系统 PATH、Node 安装或项目依赖文件。

## 4. 当前项目状态

- READY：55/61；
- 阻塞：6 条；
- Census Durable Goods 已完成官方维度接入；
- 两个 BEA 派生概念仍阻塞；
- Michigan、Freddie Mac、S&P、ICE 仍需许可证；
- 尚未执行 seed、数据库同步、部署和远程验收。

## 5. 使用的 Agents、skills、tools 和文档

- Agents：没有后台 Agent 工具，本线程完成核验；
- Skill：沿用 `research` 的一手资料核验要求；
- Tools：`exec_command`（BEA 官方 API、Node 22、Web 门禁）、`apply_patch`（本报告）；
- 文档：`AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`、治理宪法索引、`01-local-development-and-freeze.md`。

## 6. 下一步建议

下一步应进入候选集成和 55 条指标的 live audit；两个 BEA 派生概念等待宏观研究口径与公式审批，不应继续猜测或直接启用。
