"""텔레그램 알림 전송 + (선택) 키움 REST 종목명 조회.

본부원 단톡방에 봇을 초대해 두면, 이 봇이 보내는 메시지가 전원에게 푸시된다.
종목명 조회는 한 번 성공하면 캐시하며, 실패해도 알림은 종목코드로 정상 전송한다.
"""

import logging
from datetime import datetime

import requests

log = logging.getLogger("notifier")

SIGNAL_LABEL = {"I": "편입", "D": "이탈"}
SIGNAL_EMOJI = {"I": "🔔", "D": "📤"}


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str, timeout: int = 10):
        self.api = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self.chat_id = chat_id
        self.timeout = timeout

    def send(self, text: str) -> bool:
        try:
            resp = requests.post(
                self.api,
                json={"chat_id": self.chat_id, "text": text, "disable_web_page_preview": True},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return True
        except Exception as exc:  # 알림 전송 실패가 프로그램을 죽이면 안 된다
            log.error("텔레그램 전송 실패: %s", exc)
            return False

    def notify_event(self, condition_name: str, code: str, name: str, signal: str, ts: str):
        """편입/이탈 이벤트 한 건을 단톡방에 전송한다."""
        emoji = SIGNAL_EMOJI.get(signal, "🔔")
        label = SIGNAL_LABEL.get(signal, signal)
        stock = f"{name}({code})" if name else code
        when = _fmt_time(ts)
        self.send(f"{emoji} [{condition_name}] {stock} {label}{when}")


def _fmt_time(ts: str) -> str:
    """체결시간 HHMMSS → ' (HH:MM:SS)'. 비면 현재시각."""
    digits = "".join(ch for ch in ts if ch.isdigit())
    if len(digits) >= 6:
        return f" ({digits[0:2]}:{digits[2:4]}:{digits[4:6]})"
    return f" ({datetime.now():%H:%M:%S})"


class StockNameResolver:
    """키움 REST 로 종목코드 → 종목명을 조회하고 캐시한다 (선택 기능)."""

    def __init__(self, rest_base: str, app_key: str, token: str, timeout: int = 10):
        self.rest_base = rest_base
        self.app_key = app_key
        self.token = token
        self.timeout = timeout
        self._cache = {}

    def resolve(self, code: str) -> str:
        if not code:
            return ""
        if code in self._cache:
            return self._cache[code]
        name = self._lookup(code)
        self._cache[code] = name  # 실패(빈문자열)도 캐시해 재시도 폭주 방지
        return name

    def _lookup(self, code: str) -> str:
        # 키움 종목정보 조회 TR (ka10099: 종목정보 리스트). 실패해도 빈문자열 반환.
        try:
            resp = requests.post(
                f"{self.rest_base}/api/dostk/stkinfo",
                headers={
                    "authorization": f"Bearer {self.token}",
                    "appkey": self.app_key,
                    "api-id": "ka10099",
                    "Content-Type": "application/json;charset=UTF-8",
                },
                json={"stk_cd": code},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            # 응답 구조가 환경별로 다를 수 있어 흔한 키들을 순서대로 시도
            for key in ("stk_nm", "stk_name", "hts_kor_isnm"):
                if data.get(key):
                    return str(data[key]).strip()
            for row in (data.get("list") or data.get("output") or []):
                if isinstance(row, dict):
                    for key in ("stk_nm", "stk_name", "hts_kor_isnm"):
                        if row.get(key):
                            return str(row[key]).strip()
        except Exception as exc:
            log.debug("종목명 조회 실패(%s): %s", code, exc)
        return ""
