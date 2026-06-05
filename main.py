"""키움 조건검색 → 텔레그램 알림 (CLI 전용 진입점).

실시간 편입/이탈 이벤트를 텔레그램 단톡방으로만 보낸다.
웹 대시보드까지 함께 보려면 dashboard.py 를 실행하세요.

실행:  python main.py
종료:  Ctrl + C
"""

import asyncio
import logging
import sys

from config import ConfigError, load_settings
from notifier import make_notifier
from runner import Runner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")


def main():
    try:
        settings = load_settings()
    except ConfigError as exc:
        log.error("설정 오류:\n%s", exc)
        sys.exit(1)

    log.info("환경: %s | 감시 조건: %s",
             settings.environment, settings.conditions or "(전체)")
    notifier = make_notifier(settings)

    def on_event(ev):
        if ev.initial:
            return  # 시작 시점 현재 편입 종목은 알림으로 쏘지 않는다 (스팸 방지)
        if ev.flag not in settings.notify_on:
            return
        notifier.notify_event(ev.condition, ev.code, ev.name, ev.signal, ev.ts)

    def on_status(text):
        if settings.notify_lifecycle:
            notifier.send(text)

    runner = Runner(settings, on_event, on_status)
    try:
        asyncio.run(runner.run_forever())
    except KeyboardInterrupt:
        log.info("종료 요청(Ctrl+C). 안녕히 가세요.")
        if settings.notify_lifecycle:
            notifier.send("🛑 조건검색 알림을 종료했습니다.")


if __name__ == "__main__":
    main()
