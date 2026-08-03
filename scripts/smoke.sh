#!/usr/bin/env bash
set -euo pipefail
api="${API_URL:-http://localhost:8000/api/v1}"
web="${WEB_URL:-http://localhost:3000}"
curl --fail --silent --show-error "$api/ready" | python -m json.tool
curl --fail --silent --show-error "$web/login" >/dev/null
echo "MacroLens smoke test passed"
