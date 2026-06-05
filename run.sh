#!/usr/bin/env bash
# ───────────────────────────────────────────────────────────────
#  키움 조건검색 알림 실행 (mac / Linux / 서버)
#  처음 한 번만 가상환경을 만들고 의존성을 설치합니다.
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

echo "[실행] 조건검색 알림을 시작합니다. 종료하려면 Ctrl+C 를 누르세요."
exec python main.py
