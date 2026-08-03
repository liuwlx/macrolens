# Production Acceptance Checklist

## Functional

- authentication, refresh rotation and logout;
- home, data, calendar, FOMC, document, AI, compare, workspace, favorites, alerts and reports routes;
- indicator search, history, transforms and revision endpoint;
- release filters, forecast snapshots and market reactions;
- FOMC meetings, votes, projections, dot plots and licensed probabilities;
- document full-text search, versions, chunks, attachments and AI summaries;
- AI asynchronous runs, cancellation, history and validated citations;
- projects, notes, favorites, alerts and notifications;
- administrator ingestion and quality views.

## Data

- raw response stored before parsing;
- idempotent incremental sync;
- append-only vintages;
- first-release and point-in-time queries;
- lineage from observation to source and ingestion run;
- metadata-change quality gate;
- publication batch rollback;
- license restrictions enforced in API and AI context.

## Engineering

- database migration from empty PostgreSQL;
- seed is repeatable;
- Python compile and tests pass;
- TypeScript typecheck, unit tests and Next build pass;
- both containers build;
- browser critical-path test passes in desktop and mobile projects;
- health and metrics endpoints available;
- immutable image and deployment rollback documented.

## Security and operations

- production secrets are not in Git;
- cookies use Secure and correct domain/SameSite;
- public registration disabled;
- edge WAF/rate limit enabled;
- PITR and restore drill complete;
- S3/GCS versioning enabled;
- alert routes reach the on-call owner;
- restricted provider data remains disabled until approved.
