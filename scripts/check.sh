#!/usr/bin/env bash
# Same as `make check`, for machines without make (e.g. Git Bash on Windows).
set -euo pipefail
cd "$(dirname "$0")/.."
PY=backend/.venv/bin/python
[ -x backend/.venv/Scripts/python.exe ] && PY=backend/.venv/Scripts/python.exe
PY="$(cd "$(dirname "$PY")" && pwd)/$(basename "$PY")"
(cd backend && "$PY" -m ruff check app tests scripts && "$PY" -m pytest)
(cd frontend && npm run lint && npm run build)
echo "check: OK"
