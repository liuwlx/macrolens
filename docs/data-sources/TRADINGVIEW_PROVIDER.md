# TradingView WebSocket Provider

## V1范围

V1通过页面“数据同步”按钮手动触发 TradingView 最新值同步。Worker 使用轻量 WebSocket 客户端，不运行浏览器进程，不保存原始采集包。

目录注册 535 个美国候选 Symbol，其中当前探测到340项有有效最新值。完整清单和状态见 `database/seed/tradingview_registry.json`。

## 连接协议

```text
wss://data.tradingview.com/socket.io/websocket
  ?from=markets%2Fworld-economy%2Fcountries%2Funited-states%2F
  &date=<动态时间>
  &auth=sessionid
```

连接时设置：

- `Origin: https://cn.tradingview.com`；
- 浏览器形式的 User-Agent；
- 每次连接动态生成 `qs_<uuid>` 会话 ID。

消息使用：

```text
~m~<UTF-8字节长度>~m~<JSON payload>
```

## V1消息顺序

```text
set_data_quality
set_auth_token
set_locale
quote_create_session
quote_set_fields
quote_add_symbols
```

Worker 读取：

- `qsd`：最新值、上期值、观察期、频率、单位、source2；
- `quote_completed`：单个 Symbol 完成；
- 心跳：即时应答；
- `error`、`no_such_symbol`：记录 Symbol 级失败。

## 数据处理

1. 通过 `provider_series_id` 将 `ECONOMICS:US...` 映射到 `source_series`。
2. 解析 TradingView 观察期为统一 `period_start`。
3. 将值转换为 `NormalizedObservation`。
4. 插入新的 `observation_vintage`。
5. 在事务中更新 `observation_latest`。
6. `raw_object_id` 保持为空；V1不保存原始采集包。

## 手动同步接口

```http
POST /api/v1/admin/providers/TRADINGVIEW_WEB/sync
GET  /api/v1/admin/jobs/{job_id}
```

只有管理员可以发起同步。重复点击时，若已有 queued/running 的 TradingView 同步 Job，API 返回已有 Job。

## 错误策略

- 连接失败：整个 Job 失败，不发布不完整结果；
- 单个 Symbol 没有有效值：记录 Symbol 错误，其余成功项继续发布；
- 期间无法解析：该 Symbol 失败；
- 单个观测写入冲突：该发布批次进入隔离状态；
- 页面显示成功数、失败数和可读错误。

## 许可边界

V1只用于受认证保护的内部研究展示。下载、API再分发和AI上下文使用默认关闭；公开页面或商业再分发前必须单独核对 TradingView 条款。

## 非目标

- 自动 Scheduler；
- 历史 Chart Session 回填；
- B/C候选探测；
- 浏览器采集；
- 原始响应存储；
- 官方上游来源替换。
