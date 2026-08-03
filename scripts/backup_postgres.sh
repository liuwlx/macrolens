#!/usr/bin/env bash
set -euo pipefail
: "${DATABASE_URL_SYNC:?DATABASE_URL_SYNC is required}"
out="${1:-macrolens-$(date -u +%Y%m%dT%H%M%SZ).dump}"
pg_dump --format=custom --no-owner --no-acl "$DATABASE_URL_SYNC" > "$out"
sha256sum "$out" > "$out.sha256"
echo "Created $out"
