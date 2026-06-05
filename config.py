"""설정 로더 — .env(비밀 키)와 config.yaml(동작 설정)을 읽고 검증한다.

.env       : 키움 앱키/시크릿키, 텔레그램 봇토큰/채팅방ID (절대 커밋 금지)
config.yaml: 접속환경, 감시 조건식 목록, 알림 옵션 (개인 설정)

둘 다 example 파일을 복사해서 만든다. 누락 시 사람이 읽기 쉬운 에러를 던진다.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# 환경별 키움 도메인
ENDPOINTS = {
    "real": {
        "rest": "https://api.kiwoom.com",
        "ws": "wss://api.kiwoom.com:10000/api/dostk/websocket",
    },
    "mock": {
        "rest": "https://mockapi.kiwoom.com",
        "ws": "wss://mockapi.kiwoom.com:10000/api/dostk/websocket",
    },
}


class ConfigError(Exception):
    """설정이 잘못됐을 때 사용자에게 보여줄 에러."""


@dataclass
class Settings:
    # 비밀 키 (.env)
    app_key: str
    secret_key: str
    telegram_bot_token: str
    telegram_chat_id: str
    # 동작 설정 (config.yaml)
    environment: str = "mock"
    conditions: list = field(default_factory=list)
    notify_on: list = field(default_factory=lambda: ["insert", "delete"])
    resolve_stock_name: bool = True
    notify_lifecycle: bool = True
    watchlist: dict = field(default_factory=dict)  # {종목코드: 종목명}
    dashboard_port: int = 8765

    @property
    def rest_base(self) -> str:
        return ENDPOINTS[self.environment]["rest"]

    @property
    def ws_url(self) -> str:
        return ENDPOINTS[self.environment]["ws"]


def _require_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    placeholder = value.startswith("여기에")
    if not value or placeholder:
        raise ConfigError(
            f"환경변수 {name} 가 비어 있습니다. kiwoom_alert/.env 파일에 실제 값을 넣어 주세요.\n"
            f"  (.env.example 을 복사해서 .env 를 만들고 값을 채우면 됩니다.)"
        )
    return value


def load_settings(env_path: Path = None, config_path: Path = None) -> Settings:
    """`.env` 와 `config.yaml` 을 읽어 Settings 로 합친다."""
    env_path = env_path or (BASE_DIR / ".env")
    config_path = config_path or (BASE_DIR / "config.yaml")

    if not env_path.exists():
        raise ConfigError(
            f".env 파일이 없습니다: {env_path}\n"
            f"  .env.example 을 복사해서 .env 를 만들고 키를 채워 주세요."
        )
    load_dotenv(env_path, override=True)

    if not config_path.exists():
        raise ConfigError(
            f"config.yaml 파일이 없습니다: {config_path}\n"
            f"  config.example.yaml 을 복사해서 config.yaml 을 만들어 주세요."
        )
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    environment = str(raw.get("environment", "mock")).strip().lower()
    if environment not in ENDPOINTS:
        raise ConfigError(
            f"environment 값이 잘못됐습니다: {environment!r} (real 또는 mock 이어야 함)"
        )

    notify_on = [str(s).strip().lower() for s in (raw.get("notify_on") or ["insert", "delete"])]
    invalid = [s for s in notify_on if s not in ("insert", "delete")]
    if invalid or not notify_on:
        raise ConfigError(
            f"notify_on 값이 잘못됐습니다: {raw.get('notify_on')!r} (insert/delete 만 가능)"
        )

    conditions = [str(c).strip() for c in (raw.get("conditions") or []) if str(c).strip()]
    watchlist = _parse_watchlist(raw.get("watchlist") or [])

    dashboard_port = raw.get("dashboard_port", 8765)
    try:
        dashboard_port = int(dashboard_port)
    except (TypeError, ValueError):
        raise ConfigError(f"dashboard_port 값이 잘못됐습니다: {dashboard_port!r} (숫자여야 함)")

    return Settings(
        app_key=_require_env("KIWOOM_APP_KEY"),
        secret_key=_require_env("KIWOOM_SECRET_KEY"),
        telegram_bot_token=_require_env("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=_require_env("TELEGRAM_CHAT_ID"),
        environment=environment,
        conditions=conditions,
        notify_on=notify_on,
        resolve_stock_name=bool(raw.get("resolve_stock_name", True)),
        notify_lifecycle=bool(raw.get("notify_lifecycle", True)),
        watchlist=watchlist,
        dashboard_port=dashboard_port,
    )


def _parse_watchlist(items) -> dict:
    """관심종목 목록을 {종목코드: 종목명} 으로 파싱.

    허용 형식:
      - "005930 삼성전자"   (코드 + 공백 + 이름)
      - "005930"            (코드만 — 이름은 실시간 조회로 채워짐)
      - {code: "005930", name: "삼성전자"}
    """
    result = {}
    for item in items:
        if isinstance(item, dict):
            code = str(item.get("code", "")).strip()
            name = str(item.get("name", "")).strip()
        else:
            parts = str(item).strip().split(None, 1)
            if not parts:
                continue
            code = parts[0].strip()
            name = parts[1].strip() if len(parts) > 1 else ""
        if code:
            result[code] = name
    return result
