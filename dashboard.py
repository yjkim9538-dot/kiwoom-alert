"""키움 조건검색 → 실시간 웹 대시보드 (+ 텔레그램 알림) 진입점.

한 프로세스에서 키움 WebSocket 리스너와 웹서버를 함께 돌린다.
브라우저로 http://localhost:<포트> 에 접속하면 조건식 상태가 실시간으로 갱신된다.
편입/이탈 시 텔레그램 알림도 그대로 전송된다.

실행:  python dashboard.py
종료:  Ctrl + C
"""

import asyncio
import logging
import sys

from config import ConfigError, load_settings
from notifier import TelegramNotifier
from runner import Runner
from state import DashboardState
from webserver import WebServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("dashboard")


async def amain(settings):
    notifier = TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id)
    state = DashboardState(settings.watchlist, settings.environment)
    server = WebServer(state, settings.dashboard_port)
    await server.start()
    log.info("브라우저에서 http://localhost:%d 를 여세요.", settings.dashboard_port)

    def on_event(ev):
        entry = state.apply(ev)          # 상태 반영 (초기 스냅샷은 entry=None)
        server.broadcast({               # 브라우저로 항상 최신 상태 푸시
            "type": "update",
            "event": entry,              # 피드에 추가할 이벤트(없으면 None)
            "conditions": state._condition_payload(),
            "watchlist": state._watchlist_payload(),
        })
        if ev.initial or ev.flag not in settings.notify_on:
            return
        notifier.notify_event(ev.condition, ev.code, ev.name, ev.signal, ev.ts)

    def on_status(text):
        if settings.notify_lifecycle:
            notifier.send(text)
        server.broadcast({"type": "status", "text": text})

    def on_conditions(selected):
        # 재접속 시 조건 카드를 빈 상태로 초기화하고 브라우저에 반영
        state.set_conditions(selected.keys())
        server.broadcast({
            "type": "update",
            "event": None,
            "conditions": state._condition_payload(),
            "watchlist": state._watchlist_payload(),
        })

    runner = Runner(settings, on_event, on_status, on_conditions)
    try:
        await runner.run_forever()
    finally:
        await server.stop()


def main():
    try:
        settings = load_settings()
    except ConfigError as exc:
        log.error("설정 오류:\n%s", exc)
        sys.exit(1)

    log.info("환경: %s | 감시 조건: %s | 관심종목: %d개",
             settings.environment, settings.conditions or "(전체)", len(settings.watchlist))
    try:
        asyncio.run(amain(settings))
    except KeyboardInterrupt:
        log.info("종료 요청(Ctrl+C). 안녕히 가세요.")


if __name__ == "__main__":
    main()
