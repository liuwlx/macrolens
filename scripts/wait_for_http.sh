#!/usr/bin/env bash
set -euo pipefail
url="${1:?URL required}"
timeout="${2:-120}"
started=$(date +%s)
until curl --fail --silent --show-error "$url" >/dev/null; do
  if (( $(date +%s) - started >= timeout )); then
    echo "Timed out waiting for $url" >&2
    exit 1
  fi
  sleep 2
done
echo "Ready: $url"
