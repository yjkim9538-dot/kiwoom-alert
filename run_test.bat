@echo off
REM ───────────────────────────────────────────────────────────────
REM  연결 점검 (Windows) — 키/설정이 맞는지 단계별로 확인합니다.
REM  이 파일을 더블클릭하세요. (키는 화면에 노출되지 않습니다)
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

if not exist ".env" (
    echo [오류] .env 파일이 없습니다. .env.example 을 복사해 .env 를 만들고 키를 넣으세요.
    pause
    exit /b 1
)
if not exist "config.yaml" (
    echo [오류] config.yaml 이 없습니다. config.example.yaml 을 복사해 만드세요.
    pause
    exit /b 1
)

python test_connection.py
pause
