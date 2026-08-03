# MacroLens Production v1.0.1 — Runtime Review Report

Generated: 2026-08-02 UTC

## Executive result

**Status: conditionally accepted as a production candidate.**

The repository was reviewed and hardened across API readiness, authentication, authorization, data licensing, provider adapters, revision semantics, job leasing, document ingestion, AI citations, frontend deep links, deployment manifests and acceptance automation. All checks that can run in this sandbox pass.

It is not honest to certify every live production integration from this environment: Docker, PostgreSQL 16/pgvector, Terraform and npm package installation are unavailable here. A successful networked CI acceptance run with PostgreSQL, containers, Next.js build and Playwright remains a mandatory go-live gate.

## Executed results

| Check | Result |
|---|---:|
| Backend tests | **44 passed** |
| Measured Python coverage | **53.69%** (gate 35%) |
| Python compileall | Passed |
| Provider contract tests | FRED, BEA, BLS, Census, DOL, EIA, NY Fed and Treasury passed with mock HTTP |
| API process runtime | Uvicorn start/stop passed |
| `/api/v1/live` | 200 |
| `/api/v1/health` | 200 |
| `/api/v1/ready` with unavailable DB | Correct structured 503 |
| `/openapi.json` | 200, **62 paths** |
| `/metrics/` | 200 |
| Worker health server | Real TCP test passed |
| OpenAPI checked-in contract | Current, 62 paths |
| Repository contract | 61 unique source mappings; passed |
| Alembic offline upgrade | Passed, 864 SQL lines |
| Alembic offline downgrade | Passed, 122 SQL lines |
| TypeScript/TSX syntax transpilation | 32 files, 0 diagnostics |
| TypeScript SDK typecheck | Passed |
| JSON parsing | Passed |
| YAML parsing | Passed |
| Git whitespace check | Passed |

## Material defects found and corrected

### Availability and deployment

- Split process liveness from database readiness.
- Added hidden `/live`, retained `/health`, and made `/ready` perform the database check.
- Updated Docker, Compose, Cloud Run, Prometheus, CI and smoke checks to use the correct endpoint.
- Added lightweight HTTP health serving for worker and scheduler processes.
- Added a Cloud Run seed job and required seed execution after migration during deployment.

### Authentication and authorization

- Implemented refresh-token rotation and refresh-family revocation on replay/logout.
- Added origin checks for state-changing cookie requests.
- Added production startup guards for insecure cookies, weak/default secrets and non-HTTPS origins.
- Added ownership checks for projects, notes, saved views, reports and AI runs.
- Restricted administrator resources and public project shares at object level.
- Preserved authenticated deep-link query strings through login redirects.

### Data correctness

- Prevented an older vintage from replacing a newer serving value.
- Made month, quarter and year transforms date-aware so gaps are not silently bridged.
- Added valid daily matching tolerance for annual comparisons.
- Corrected BLS 20-year request windowing, batching and dataset lineage.
- Added EIA pagination, deduplication and robust period parsing.
- Corrected FRED current-vintage handling and Census quarter validation.
- Kept rejected-observation diagnostics after savepoint rollback.

### Licensing

- Enforced display/download/API/AI policy across series, observations, revisions, comparisons, documents, forecasts, market reactions and FOMC probabilities.
- Disabled frontend export or AI actions when source licenses prohibit them.

### Durable jobs

- Made enqueue idempotency atomic with PostgreSQL conflict handling.
- Added stale-running-job recovery, heartbeat, lease ownership and unique worker identities.
- Prevented a worker that lost its lease from marking another worker's job complete.
- Added notification implementations for releases, thresholds, revisions, documents, FOMC changes and digests.
- Propagated worker failures into AI run state.

### Document and AI safety

- Added SSRF protection: HTTPS-only, no URL credentials, DNS/global-IP checks, provider host allowlists and redirect revalidation.
- Added 50 MiB, text-length and page-count limits.
- Added PDF, HTML, XLSX and text parsing, bounded chunk overlap and unchanged-version handling.
- Made OpenAI imports lazy so non-AI services start without the optional client loaded.
- Added context-count, chunk-size and total-context limits plus prompt-injection boundaries.
- Validated AI citation numbers against frozen evidence snapshots.
- Added configurable OpenAI-compatible base URL for deterministic acceptance tests.

### Frontend and contracts

- Added complete alert-rule management rather than a read-only shell.
- Added deep links and query handling for data, calendar, FOMC, documents, AI, compare and workspace pages.
- Corrected data-page state when query parameters change without a full reload.
- Replaced an overbroad global-search label with the function it actually performs.
- Added a six-scenario Playwright suite covering all pages, linked data, CRUD workflows, worker-driven AI, administrator operations and mobile login.
- Added a contract test proving frontend API calls exist in OpenAPI.
- Removed remote Google-font build dependency.

### Migration and testability

- Made the initial Alembic migration static and self-contained rather than importing live ORM metadata.
- Added deterministic acceptance fixtures and a guarded fixture CLI.
- Added a real HTTP mock for OpenAI embeddings/responses.
- Added mock-provider runtime tests for all implemented public adapters.

## Functional acceptance coverage encoded in CI

The acceptance workflow now starts PostgreSQL/pgvector, MinIO, migration, seed, deterministic fixtures, mock OpenAI, API, worker, scheduler and Web, then exercises:

1. all 12 authenticated user/admin pages;
2. indicator detail, observations, revisions and comparison;
3. release calendar, FOMC and document relationships;
4. favorites, saved views, projects, project items, notes, shares, alert rules and notifications;
5. an AI run executed by the real worker against the mock OpenAI API, including citations and report lifecycle;
6. administrative users, jobs, providers, mappings, quality results and ingestion runs;
7. mobile login and safe redirect behavior.

## Remaining mandatory go-live gates

These are environment gates, not claims of completion:

- Run the GitHub Actions backend, frontend, container and acceptance jobs on a normal networked runner.
- Build the Web image and execute strict Next.js typecheck/lint/unit tests with installed npm dependencies.
- Execute Alembic against PostgreSQL 16 with `pgcrypto`, `pg_trgm` and `vector` extensions.
- Run the Playwright suite against the full Docker Compose stack.
- Run `terraform fmt -check` and `terraform validate` with the deployment toolchain.
- Inject real cloud secrets and official API keys; validate provider responses against current official metadata.
- Approve all mappings not marked `READY`, and obtain required commercial licenses.
- Add and commit an npm lockfile from a networked trusted build environment before release tagging. Direct versions are pinned, but transitive dependencies are not reproducibly locked yet.
- Complete backup/restore, PITR and rollback drills in the target cloud account.
- Perform external dependency/SBOM and penetration scans in CI or the deployment platform.

## Final assessment

The reviewed code is materially stronger than the original delivery and passes every executable local gate. It should be treated as a **release candidate**, not as proof that external services, licensed feeds or cloud resources work before they are provisioned. Production traffic should only be enabled after the networked CI acceptance workflow and environment-specific operational gates pass from the exact same commit SHA.
