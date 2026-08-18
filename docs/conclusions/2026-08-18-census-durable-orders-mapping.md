# Census Durable Goods 官方维度映射结论

## 1. 问题与场景

本轮处理 `US.DURABLE.ORDERS`，目标是将 Census Economic Indicators Time Series 的 `ADVM3` 多维矩阵固定为可执行的生产映射。该指标不能只填写一个 Series ID，必须同时固定数据类型、时间槽、季调状态、项目、行业类别、地理层级和错误标记。

官方一手资料：

- [ADVM3 数据集说明](https://api.census.gov/data/timeseries/eits/advm3.html)
- [ADVM3 变量字典](https://api.census.gov/data/timeseries/eits/advm3/variables.html)
- [ADVM3 API 示例](https://api.census.gov/data/timeseries/eits/advm3/examples.html)
- [Census 2025 年 1 月 Durable Goods 发布稿](https://www.census.gov/manufacturing/m3/historical_data/pressreleases/adv/2025/jan25adv.pdf)

## 2. 官方身份核验

API 返回的 `ADVM3` 变量包括 `data_type_code`、`time_slot_id`、`seasonally_adj`、`program_code`、`category_code`、`geo_level_code`、`error_data` 和 `cell_value`；地理查询使用 `for=us:*`。本轮固定为：

| 维度 | 固定值 | 含义 |
|---|---|---|
| `data_type_code` | `NO` | New Orders |
| `time_slot_id` | `0` | 官方默认时间槽 |
| `seasonally_adj` | `yes` | Seasonally Adjusted |
| `program_code` | `M3ADV` | Advance M3 |
| `category_code` | `MDM` | Durable Goods 总类 |
| `geo_level_code` | `US` | 美国总量 |
| `error_data` | `no` | 非误差数据 |
| `for` | `us:*` | 全国地理范围 |

官方 2025-01 响应中，以上完整身份匹配唯一一行，`cell_value=291195`；该值以百万美元计，和注册表平台单位一致。该值高于 2025 年 1 月初始发布稿中的 286.0 billion，属于官方后续修订，不能覆盖旧 vintage。Census 发布稿说明该调查数据按季节调整、未按价格调整，且新订单是制造商耐用品新订单。

## 3. 历史完整性核验

使用官方 API 查询 `time=from 1992 to 2025`，按完整维度过滤后得到：

- 407 条月度观测；
- 首期：1992-02-01；
- 末期：2025-12-01；
- 重复月份：0。

使用 MacroLens `CensusEITSAdapter` 真实只读回填查询后得到：

- probe：HTTP 200、business success、identity match、production ready；
- backfill：413 条观测；
- 首期：1992-02-01；
- 末期：2026-06-01；
- 首值：114535；末值：334772；
- 原始响应包：11,554,901 bytes。

本轮将主时间字段固定为 Census API 标准返回的 `time`。此前尝试使用 `time_slot_date` 会造成 headers/time identity 失败；这属于字段契约问题，不是维度值错误。

## 4. 修改内容

- `database/seed/source_registry.json`
  - `US.DURABLE.ORDERS` 改为 `READY`；
  - `provider_series_id=MDM`；
  - 固定 `path=timeseries/eits/advm3`、`value_field=cell_value`、`time_field=time`；
  - 写入完整 `required_variables`、`dimensions`、`probe_period=2025-01`、`start_year=1992`、`expected_first_period=1992-02-01`。
- `DATA_COLLECTION_MODULE_REVIEW.json`
  - Census `enabled_series=2`、`blocked_series=0`；
  - 全项目 READY：54 → 55；阻塞：7 → 6。
- 测试补充 durable-orders 注册表和维度断言。

## 5. 当前剩余阻塞

剩余 6 条：

- BEA：核心服务剔除住房、长期护理服务；
- Census：无剩余阻塞；
- 许可证/法务：Michigan 预期、Freddie Mac 房贷、S&P 500、ICE 高收益债利差。

## 6. 验证与边界

- 官方 API 只读维度/历史审计通过。
- MacroLens Adapter probe/fetch 真实只读验证通过。
- 后端全量测试：268 passed；`ruff check backend` 和 `mypy backend/src` 通过。
- Web lint/build 通过；Web test 仍受当前 Node 20.11.1 与依赖 CommonJS/ESM 冲突影响，项目要求 Node 22+。
- 尚未执行数据库 seed、同步、回填写入、部署或远程验收。
- API Key 仅从主工作区环境配置读取，没有写入注册表、代码、报告或命令输出。

## 7. 使用的 Agents、skills、tools 和文档

- Agents：当前会话没有后台 Agent 工具，由本线程完成；未伪造后台研究结果。
- Skill：`research`，使用 Census 官方数据集说明、变量字典、API 示例和官方发布稿。
- Tools：`exec_command`（官方 API、Adapter 只读验证、测试）、`apply_patch`（注册表、测试和报告修改）、官方网页检索（核对一手发布语义）。
- 文档：`AGENTS.md`、`.codex/organization.toml`、`docs/organization/README.md`、治理宪法索引和 `01-local-development-and-freeze.md`。

## 8. 后续建议

下一步可进入 BEA 两个剩余概念的派生公式设计；Census Durable Goods 已具备进入 live audit 和后续 seed 的条件，但仍需先集成候选提交并获得数据库写入授权。
