# MacroLens Production

MacroLens 是一个面向宏观研究员的美国宏观数据平台。项目采用模块化单体架构：Next.js Web、FastAPI API、PostgreSQL 数据库，以及独立的数据/文档/AI Worker。

## 核心能力

- 指标目录、指标树、时间序列、历史修订与数据血缘
- BEA、BLS、FRED、Treasury、NY Fed、EIA、Census 等 Provider Adapter
- 发布日历、实际值/预期/前值/修订/惊喜值
- FOMC 会议、声明、纪要、SEP 和点阵图
- 文档采集、版本、全文检索、切块与向量检索
- AI 宏观研究、来源引用、分析历史和报告导出
- 对比分析、研究项目、收藏、提醒和通知
- Docker、Alembic、CI、Cloud Run/Vercel 部署样例


## Windows: local API/Web with the remote database

The helper below runs the API and Web app locally while reaching the existing PostgreSQL container on `111.229.152.122` through an SSH tunnel. PostgreSQL remains private: only `127.0.0.1:15432` is opened locally. The server login is fixed to `ubuntu`.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/remote-dev.ps1 Provision
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/remote-dev.ps1 Start
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/remote-dev.ps1 Status
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/remote-dev.ps1 Stop
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/remote-dev.ps1 Deprovision
```

`Provision` requires a trusted SSH host key, passwordless `sudo docker`, Python 3.12, and Node.js 22 (set `MACROLENS_NODE22` to an absolute `node.exe` path if discovery cannot find it). It creates the dedicated least-privilege database role and the ignored, ACL-protected `.env.remote`. `Start` creates/uses the project `.venv`, checks the remote `alembic_version` against the local head, and does not run migrations, seeds, workers, or schedulers. A known design-QA preview on ports 3000/4010 is replaced only after remote validation succeeds; unknown listeners are never stopped.

After `Start`, use `http://localhost:3000` for Web and `http://localhost:8000/docs` for the API. Run `Deprovision` only when the local-development database role should be removed.

## Production v1.0.2 ingestion-reviewed scope

This repository is the production implementation rather than the earlier single-file prototype. It includes:

- 11 user-facing product areas: home, data, calendar, FOMC, documents, AI, comparison, workspace, favorites, alerts and reports;
- administrator operations for users, provider mappings, document ingestion, jobs, quality gates, raw objects and publication rollback;
- 61 canonical source-registry entries with verified, review-required and license-gated states;
- 46 SQLAlchemy tables, 62 OpenAPI paths, a TypeScript SDK, durable PostgreSQL jobs and append-only observation vintages;
- production configuration guards that reject default credentials, insecure cookies and non-HTTPS origins.

The code does not silently substitute simulated production data. Series that still require official metadata review or commercial licensing remain disabled until an administrator verifies the mapping or records the license.


## 数据采集完整性门禁

生产同步不会“有多少发多少”。每个启用的官方序列必须同时通过：映射身份、返回覆盖率、非空值、最小历史长度、规则频率缺口、最新期时效、分页总数和重复冲突检查。任一启用序列失败时，整个 Provider 发布批次进入 `quarantined`，旧批次继续对外服务。

结构审计（不检查密钥）：

```bash
PYTHONPATH=backend/src python -m macrolens_worker.main audit-data --structural \
  --output DATA_INGESTION_READINESS.json
```

运行审计（检查官方 API 密钥和 DOL 端点）：

```bash
PYTHONPATH=backend/src python -m macrolens_worker.main audit-data \
  --output DATA_INGESTION_RUNTIME_READINESS.json
```

使用 `--require-all` 可把尚未核验或未授权的指标也作为失败条件。默认只要求所有 `READY` 指标完全可执行，故不会让未授权市场数据偷偷混入生产。完整说明见 `docs/data-ingestion-review.md`。

## 当前采集覆盖与审计节奏

- 注册表 61 条指标中，31 条启用映射已通过结构审计；30 条因官方身份、维度或授权未解决而保持禁用。
- 周度执行不发布的增量 live audit；月度执行全历史 backfill audit；需要历史时点回测时手工执行 FRED vintage backfill。
- FOMC 当前保证会议日历和官方材料链接完整采集；结构化 SEP、点阵图、投票明细尚未实现，不会伪装成实时完整数据。
- 任何缺页、重复冲突、身份漂移、历史边界错误或质量门禁失败都会 quarantine 整个 Provider 批次。

模块级结论见 `docs/data-ingestion-review.md`，机器可读矩阵见 `DATA_COLLECTION_MODULE_REVIEW.json`。

## 本地启动

```bash
cp .env.example .env
# 至少修改 POSTGRES_PASSWORD、JWT_SECRET 和管理员密码
docker compose up --build
```

打开：

- Web: http://localhost:3000
- API: http://localhost:8000/docs
- MinIO Console: http://localhost:9001
- Mailpit: http://localhost:8025

首次启动完成后初始化目录与管理员：

```bash
docker compose run --rm api python -m macrolens_api.cli seed
```

触发数据同步：

```bash
docker compose run --rm api python -m macrolens_api.cli enqueue-sync --provider FRED
```

## 生产部署

- Web：Vercel
- API：Cloud Run Service
- Worker：Cloud Run Service 或 Cloud Run Job
- PostgreSQL：Cloud SQL / Neon / Supabase
- 对象存储：S3 / Cloudflare R2

生产环境必须：

1. 使用托管 PostgreSQL 和对象存储；
2. 在 Secret Manager 保存密钥；
3. `COOKIE_SECURE=true`；
4. 关闭 `NEXT_PUBLIC_DEMO_MODE`；
5. 配置官方 API Key 和 OpenAI API Key；
6. 在边缘网关配置 WAF、速率限制和 TLS；
7. 为数据库开启 PITR、只读副本与定期恢复演练。

## 数据原则

- `data.observation_vintage` 只追加，不覆盖历史值；
- 每条观测值保留 Provider、Dataset、Source Series、Run 和 Raw Object；
- 商业数据由 `source.license_policy` 控制网页展示、下载、API 与 AI 使用；
- AI 结论必须保存数据截止时间、上下文快照和引用。

## 测试

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e 'backend[dev]'
pytest backend/tests

npm install
npm --workspace apps/web run test
npm --workspace packages/sdk-typescript run typecheck
npm --workspace packages/sdk-typescript run build
npm --workspace apps/web run build
```

详细架构见 `docs/architecture.md`。运行时复核结果与上线门禁见 `RUNTIME_REVIEW_REPORT.md`。
