# Operations Runbook

## Daily checks

- API error rate and P95 latency;
- provider request failures and rate-limit responses;
- latest-period lag for tier-1 indicators;
- failed or repeatedly retried jobs;
- blocking quality results;
- document parser and embedding failures;
- AI runs without validated citations;
- storage and database growth;
- unread critical notifications.

## Incident: important release not updated

1. Confirm the official release occurred and record its actual publication time.
2. Inspect `ingestion.run`, `app.job` and raw-object records.
3. Retry the exact dataset with a new operational idempotency key.
4. Compare parsed row counts and latest periods against the previous successful run.
5. If quality gates fail, keep the previous active batch and investigate the parser or metadata change.
6. Publish only after lineage and values are verified.
7. Record the incident and preventive action.

## Incident: provider schema changed

- preserve the raw payload;
- disable automatic publication for the affected dataset;
- update a provider fixture and parser test;
- create or update source-series mappings;
- backfill into staging;
- validate revisions before activating a batch.

## Incident: incorrect published value

- do not edit or delete the vintage;
- quarantine the source mapping or batch;
- activate the previous publication batch;
- append the corrected vintage with lineage;
- record an audit event and user-facing correction when necessary.

## Incident: AI answer lacks evidence

- mark the run failed or withdrawn;
- retain its request and model metadata for audit;
- verify context license and retrieval filters;
- inspect citation parsing and context truncation;
- rerun only after the evidence contract passes.

## Backup and recovery

- Cloud SQL PITR enabled;
- daily logical catalog/config export;
- object-store versioning enabled;
- monthly restore into an isolated project;
- document the measured RPO and RTO.
