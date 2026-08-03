#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements-dev.txt
npm install --no-audit --no-fund
[ -f .env ] || cp .env.example .env
printf '\nMacroLens development environment is ready. Run: docker compose up --build\n'
