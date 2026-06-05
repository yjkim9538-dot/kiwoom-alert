#!/usr/bin/env bash
# ───────────────────────────────────────────────────────────────
#  키움 조건검색 실시간 대시보드 실행 (mac / Linux / 서버)
#  실행 후 브라우저로 http://localhost:8765 접속.
# ───────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
    echo "[오류] python3 가 설치되어 있지 않습니다." >&2
    exit 1
fi

if [ ! -d ".venv" ]; then
    echo "[설치] 가상환경을 만들고 의존성을 설치합니다..."
    python3 -m venv .venv
    # shellcheck disable=SC1091
    source .venv/bin/activate
    python -m pip install --upgrade pip
    pip install -r requirements.txt
else
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi

echo "[실행] 대시보드를 시작합니다. 브라우저에서 http://localhost:8765 를 여세요."
exec python dashboard.py
