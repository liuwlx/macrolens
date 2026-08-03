# MacroLens Production v1.0.1 — Conditional Acceptance

The authoritative review for this release is [`RUNTIME_REVIEW_REPORT.md`](RUNTIME_REVIEW_REPORT.md).

## Classification

**Production release candidate; conditional acceptance.**

All checks executable in the review sandbox pass: 44 backend/runtime tests, 53.69% measured Python coverage, API process smoke tests, eight provider mock contracts, OpenAPI/repository validation, offline Alembic upgrade/downgrade, TypeScript syntax and SDK typecheck.

A production declaration requires the networked CI acceptance workflow to pass with installed npm dependencies, PostgreSQL/pgvector, Docker images and Playwright. It also requires real secrets, official API keys, metadata review and commercial data licenses. The repository does not claim that those external conditions have already been satisfied.
