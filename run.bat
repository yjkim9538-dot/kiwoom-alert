@echo off
REM ───────────────────────────────────────────────────────────────
REM  키움 조건검색 알림 실행 (Windows)
REM  이 파일을 더블클릭하면 됩니다. 처음 한 번만 의존성을 설치합니다.
REM ───────────────────────────────────────────────────────────────
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [오류] python 이 설치되어 있지 않습니다. https://www.python.org 에서 설치하세요.
    pause
    exit /b 1
)

if not exist ".venv" (
    echo [설치] 가상환경을 만들고 의존성을 설치합니다...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

echo [실행] 조건검색 알림을 시작합니다. 종료하려면 이 창에서 Ctrl+C 를 누르세요.
python main.py
pause
