# Federal Reserve Board XML ZIP 扩展报告

## 1. 问题与场景

在 G.17 文件 Adapter 样板完成后，继续接入 Federal Reserve Board 的 H.8、G.19 和 H.10 官方 XML ZIP 文件。

## 2. 解决方案

将 `FED_BOARD_FILES` Adapter 扩展为配置驱动的 SDMX XML ZIP 解析：

- 按 `file_url` 分组下载，一份文件可服务多个 Raw Series；
- 按 `series_name` 精确选择官方 Series；
- 按 `series_attributes` 校验 SA、FREQ、DATAREP、FX 等身份；
- 解析 XML `Obs` 的时间和值；
- 支持月度、季度、周度、日度 Period 归一化；
- 支持官方百万美元到平台十亿美元的显式缩放；
- 保留完整 ZIP 原始字节、响应 URL、抓取时间和 Last-Modified；
- 历史首期不一致、Series 不唯一、字段漂移和空数据均 fail-closed。

## 3. 已接入 Series

- G.17：`B50001`，Total index；
- H.8：`B1001NCBA`，季调总商业银行信贷；
- G.19：`DTCTL.M`，季调总消费信贷余额；
- H.10：`JRXWTFB_N.B`，Nominal Broad Dollar Index。

## 4. 真实验证

- H.8：HTTP 200，2,797 条观测，1973-01-03 至 2026-08-05；
- G.19：HTTP 200，1,002 条观测，1943-01 至 2026-06；
- H.10：HTTP 200，5,380 条观测，2006-01-02 至 2026-08-14；
- G.17：HTTP 200，1,290 条观测，1919-01 至 2026-06；
- 全量后端测试：264 passed；
- ruff：通过；
- mypy：通过，71 个源文件无问题。

## 5. 尚未执行

没有执行 seed、数据库同步、回填、Scheduler 重启或服务器部署。H.4.1、CHGDEL、SLOOS 仍需先冻结官方 Series identity 和字段语义。

## 6. 候选信息

- 分支：`codex/ML-20260818-fed-board-g17`；
- 本轮提交：`ee6b733c9b2d2cf1a0d446fc0e2408d428e4560c`。

## 7. 下一步提示词

“基于 `FED_BOARD_FILES` 的 G.17/H.8/G.19/H.10 实现，继续冻结并接入 H.4.1 的总资产/准备金/MBS、CHGDEL 的信用卡逾期率和 SLOOS 的大中型企业 C&I 贷款标准。先从官方 XML ZIP 的 Series attributes 和 Obs 样例生成身份矩阵，再补 fixture、历史边界和真实只读解析；不使用 FRED ID 替代官方 Series，不 seed、不同步、不部署。”

