#!/usr/bin/env bash
# ───────────────────────────────────────────────────────────────
#  연결 점검 (mac / Linux) — 키/설정이 맞는지 단계별로 확인합니다.
# ───────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
    echo "[오류] python3 가 설치되어 있지 않습니다." >&2
    exit 1
fi

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    # shellcheck disable=SC1091
    source .venv/bin/activate
    python -m pip install --upgrade pip
    pip install -r requirements.txt
else
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi

[ -f ".env" ] || { echo "[오류] .env 가 없습니다. .env.example 을 복사해 만드세요."; exit 1; }
[ -f "config.yaml" ] || { echo "[오류] config.yaml 이 없습니다. config.example.yaml 을 복사해 만드세요."; exit 1; }

exec python test_connection.py
