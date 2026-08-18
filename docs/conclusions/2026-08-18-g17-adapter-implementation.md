# Federal Reserve Board G.17 Adapter 实施报告

## 1. 问题与场景

MacroLens 需要接入 Federal Reserve Board 官方发布文件。第一步选择 G.17 `ip_sa.txt` 的工业生产总指数作为通用文件 Adapter 样板，避免把每个指标写成独立接口。

## 2. 解决方案

新增 `FED_BOARD_FILES` Provider Adapter，当前支持 G.17 `B50001: Total index`：

- 官方文件 URL、格式、SeriesCode、LineDescription 和历史边界全部由 registry 配置；
- 官方原始文件字节直接保存到 `ProviderFetchResult.raw_bytes`；
- 解析年度行和 12 个月值为月度 Observation；
- 历史年份强制 12 个月；
- 当前最后一年可通过显式 `allow_partial_latest_year` 配置接收已发布月份；
- 校验 SeriesCode、LineDescription、首期、日期、数值和重复期；
- 读取并保存 HTTP `Last-Modified`；
- 已加入同步 Adapter 注册、数据 readiness 校验、CI live audit 和模块审查清单。

## 3. 验证结果

- G.17 官方文件真实请求：HTTP 200；
- 响应大小：约 2.74 MB；
- 解析观测：1,290 条；
- 历史范围：1919-01 至 2026-06；
- 目标 Series：B50001 Total index；
- 目标测试：5 passed；
- 相关测试：59 passed；
- 全量后端测试：262 passed；
- ruff：通过；
- mypy：通过，71 个源文件无问题。

## 4. 未执行事项

本次没有执行数据库迁移、seed、生产同步、回填、Scheduler 重启或服务器部署。G.17 当前是代码和 registry 候选，进入运行库前仍需集成、镜像和远程 Docker 验收。

## 5. 下一步

复用该文件框架扩展 H.4.1、H.8、G.19、H.10、CHGDEL、SLOOS；每个发布文件必须补充自己的字段身份、样例文件、历史边界和离线回放测试。

## 6. 使用的 Agents、skills、tools 与文档

- Agents：主线程。
- Skills：未使用额外 skill。
- Tools：独立 Git worktree、Python 3.12、HTTPX、curl、pytest、ruff、mypy、`apply_patch`。
- 文档：`AGENTS.md`、开发宪法索引、研究数据平台计划、Federal Reserve Board G.17 官方文件。

## 7. 经验沉淀与更好提示词

文件型官方数据源应采用“通用采集框架 + Dataset 配置 + Dataset 专属解析器”的结构。当前年度部分月份不是文件损坏，必须通过显式配置处理，不能全局放松历史完整性。

更好的下一步提示词：

“基于已通过的 G.17 文件 Adapter，扩展 Federal Reserve Board H.4.1、H.8、G.19、H.10、CHGDEL、SLOOS。先为每个 release 冻结官方文件、字段、维度、单位、历史边界和最新年度部分期规则，再写 fixture 和离线回放测试；禁止使用 FRED ID 代替 Board 字段，禁止 seed、同步和部署。”

