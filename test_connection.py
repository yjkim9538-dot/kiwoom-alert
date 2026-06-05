"""연결 진단 도구 — 실제 키움/텔레그램 키로 단계별 점검.

실제 알림을 켜기 전에, 내 키와 설정이 제대로 동작하는지 한 단계씩 확인한다.
키는 .env 에서 읽으며 화면/로그에 노출하지 않는다.

실행:  python test_connection.py
"""

import asyncio
import logging
import sys

from config import ConfigError, load_settings
from kiwoom_client import KiwoomConditionClient, issue_access_token
from notifier import TelegramNotifier

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("test")


def _mask(s: str) -> str:
    s = str(s or "")
    return (s[:3] + "…" + s[-2:]) if len(s) > 6 else "***"


async def run_checks(settings) -> bool:
    ok = True

    # 1) 설정 확인
    print("1) 설정 로드 ............ OK")
    print(f"   - 환경        : {settings.environment} ({settings.rest_base})")
    print(f"   - 감시 조건   : {settings.conditions or '(전체)'}")
    print(f"   - 관심종목    : {len(settings.watchlist)}개")
    print(f"   - 앱키        : {_mask(settings.app_key)}")
    print(f"   - 봇토큰      : {_mask(settings.telegram_bot_token)} / chat {settings.telegram_chat_id}")

    # 2) 텔레그램 전송
    print("2) 텔레그램 테스트 전송 .. ", end="", flush=True)
    notifier = TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id)
    if notifier.send("🧪 [테스트] kiwoom_alert 연결 점검 메시지입니다."):
        print("OK (단톡방 메시지 확인하세요)")
    else:
        print("실패 (봇 토큰/chat_id/봇 초대 여부 확인)")
        ok = False

    # 3) 키움 토큰 발급
    print("3) 키움 토큰 발급 ....... ", end="", flush=True)
    try:
        token = issue_access_token(settings.rest_base, settings.app_key, settings.secret_key)
        print(f"OK (token {_mask(token)})")
    except Exception as exc:
        print(f"실패: {exc}")
        return False

    # 4) WebSocket 로그인
    print("4) WebSocket 로그인 ..... ", end="", flush=True)
    client = KiwoomConditionClient(settings.ws_url, token)
    try:
        await asyncio.wait_for(client.connect_and_login(), timeout=15)
        print("OK")
    except Exception as exc:
        print(f"실패: {exc}")
        return False

    # 5) 조건식 목록 조회
    print("5) 조건식 목록 조회 ..... ", end="", flush=True)
    try:
        available = await asyncio.wait_for(client.fetch_condition_list(), timeout=15)
        print(f"OK ({len(available)}개)")
        for name, seq in available.items():
            mark = " ← 감시대상" if (not settings.conditions or name in settings.conditions) else ""
            print(f"     [{seq}] {name}{mark}")
        for want in settings.conditions:
            if want not in available:
                print(f"   ⚠ config 의 '{want}' 가 서버 목록에 없습니다. (이름/서버저장 확인)")
                ok = False
    except Exception as exc:
        print(f"실패: {exc}")
        ok = False

    try:
        await client.ws.close()
    except Exception:
        pass

    return ok


def main():
    try:
        settings = load_settings()
    except ConfigError as exc:
        log.error("설정 오류:\n%s", exc)
        sys.exit(1)

    print("=" * 52)
    print(" kiwoom_alert 연결 진단")
    print("=" * 52)
    ok = asyncio.run(run_checks(settings))
    print("-" * 52)
    if ok:
        print("✅ 모든 점검 통과. main.py / dashboard.py 를 실행하세요.")
    else:
        print("❌ 일부 점검 실패. 위 메시지를 확인해 설정을 고쳐 주세요.")
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
