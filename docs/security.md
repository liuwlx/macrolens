# Security Model

## Secrets

- Never commit `.env`, API keys, database URLs or production credentials.
- Production secrets are stored in Secret Manager and mounted into Cloud Run as environment references.
- Development and CI use separate credentials and databases.
- Rotate the bootstrap administrator password immediately after first deployment.

## Authentication

- Passwords use Argon2id.
- Access tokens are short-lived JWTs in HTTP-only cookies.
- Refresh tokens rotate on every refresh and are compared to a SHA-256 hash in `app.refresh_session`.
- Logout and token rotation revoke server-side sessions.
- Public registration is disabled by default.

## Browser protections

- strict origin checking on state-changing requests;
- CORS allowlist with credentials;
- `X-Content-Type-Options`, frame denial, referrer and permissions policies;
- HSTS in production;
- no model or provider secret is exposed to the browser.

## Authorization

- user data is scoped to the current workspace;
- administrator routes require role checks;
- signed or proxied object access should replace public buckets for private uploads;
- license policy is evaluated separately for display, download, API redistribution, AI context and training.

## Data integrity

- observation vintages are append-only;
- raw files are checksummed and object-versioned;
- migration history is immutable after release;
- audit logs capture successful state-changing requests;
- database PITR and restore exercises are mandatory for production.

## Production controls outside the repository

- WAF and distributed rate limits;
- TLS certificates and managed DNS;
- Cloud SQL private connectivity where required;
- vulnerability and dependency scanning;
- least-privilege IAM and workload identity federation;
- centralized logs, alerts and incident response.
