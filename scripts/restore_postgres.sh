#!/usr/bin/env bash
set -euo pipefail
: "${DATABASE_URL_SYNC:?DATABASE_URL_SYNC is required}"
dump="${1:?dump file required}"
sha256sum --check "$dump.sha256"
pg_restore --clean --if-exists --no-owner --no-acl --dbname "$DATABASE_URL_SYNC" "$dump"
echo "Restored $dump"
