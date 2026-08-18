# MacroLens 剩余任务一次性收口报告

## 1. 收口目标

本轮按“所有可本地完成的任务全部完成；外部阻塞可复现、可交接、不伪造完成”的原则，处理 MacroLens 当前剩余任务。

## 2. 已完成

### 数据映射

- Federal Reserve Board：G.17、H.8、G.19、H.10、H.4.1、CHGDEL、SLOOS，共 8 条 READY。
- BEA：22 条 READY，已完成官方 SeriesCode/LineNumber/LineDescription/单位/历史首期审计。
- Census：MARTS 零售销售和 ADVM3 Durable Goods，共 2 条 READY；Durable Goods 维度和历史回填已真实验证。
- 其余 BLS、FRED、NY Fed、Treasury、EIA：保持已验证 READY。

当前注册表：

- 总指标：61；
- READY：55；
- `enabled_blocked_count`：0；
- 全部阻塞：6 条。

### 工程门禁

- 后端全量测试：268 passed；
- `ruff check backend`：通过；
- `mypy backend/src`：通过；
- Node 22.14.0 下 Web test：11 个文件、35 个测试通过；
- Web lint：通过，2 个既有 warning；
- Web build：通过；
- 结构化 readiness：已生成 [final-readiness.json](./2026-08-18-final-readiness.json)。

## 3. 仍然阻塞且不能伪造完成的任务

### BEA 派生概念

1. `US.PCE.NONHOUSING`：官方有 `PCE services excluding energy`，但仍包含住房；不能直接冒充核心服务剔除住房。
2. `US.PCE.LONGTERM.CARE`：官方只有 nursing homes、home health care 等组件，没有完整长期护理单行序列。

两项需要宏观研究确认组件、权重、指数公式、vintage 对齐、版本号和有效期；当前运行时也禁止解释没有版本绑定的任意 `weight_expression`，所以保持 `NEEDS_METADATA_MAPPING`。

### 许可证/法务

- Michigan 1Y inflation expectations；
- Freddie Mac PMMS；
- S&P 500；
- ICE BofA 高收益债利差。

这些不是代码缺陷，必须取得数据许可并录入许可策略后才能接入。

### 远程 live audit、seed、同步和部署

本地 `.env` 的 `postgres:5432` 端点确实无法解析；随后通过项目现有 SSH 链路连接到服务器 `ubuntu@111.229.152.122`，发现健康数据库属于独立验收 Compose 项目 `macrolens-acceptance-20260814`。对旧验收库的只读 live audit 已执行：BEA/Census 通过，BLS 因 2025-10 官方缺值失败，EIA 因官方响应/密钥触发压缩解码错误失败，FRED/NY Fed/Treasury 因旧库没有 verified primary 跳过。旧库尚未包含当前候选的 55 条新映射。

因此本轮没有：

- 启动本地 Docker 或 Mock 数据库；
- 执行数据库 seed；
- 写入 observation/vintage；
- 执行生产同步或回填；
- 部署服务器或远程验收。

## 4. 候选提交

当前候选分支：`codex/ML-20260818-fed-board-g17`

关键提交：

- `207e3a2`：Fed G.17 Adapter；
- `ee6b733`：Fed XML 扩展；
- `e1cec18`：Fed H.4.1/CHGDEL/SLOOS 等官方 XML 映射；
- `314a0ba`：BEA 21 个官方元数据映射；
- `0a98cd3`：Census Durable Goods 维度映射；
- `f992d6f`：公式边界和 Node 22 验证；
- `e1fba18`：live audit 数据库阻塞记录。
- `ee51a93`：最终 readiness 和剩余任务收口证据。

主工作区仍有用户既有脏改动，因此没有自动合并候选分支。

## 5. 最终解除条件

要从当前 55/61 进入完整生产验收，只需按以下顺序补外部条件：

1. 审查并集成当前候选提交；
2. 在独立验收 Compose 项目执行授权 migration/seed；
3. 对新 55 条映射重新建立 verified primary 并运行 incremental/backfill live audit；
4. 处理 BLS 官方缺值和 EIA 响应/密钥问题；
5. 取得 4 类商业/法务许可；
6. 审批两个 BEA 派生公式；
7. 获得数据库同步、部署和远程验收授权，按阶段 02/03 宪法收口。

## 6. 使用的 Agents、skills、tools 和文档

- Agents：当前会话没有后台 Agent 工具；由主线程执行并保留阻塞证据。
- Skills：`research`，用于 BEA/Census 官方一手资料核验。
- Tools：`exec_command`、`apply_patch`；官方 BEA/Census/Fed API 和 Node 22 本地运行时。
- 文档：`AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`、治理宪法索引、`01-local-development-and-freeze.md`。
