"""키움 조건검색 접속/등록/이벤트 루프 — 텔레그램·대시보드가 공유하는 핵심 엔진.

Runner 에 이벤트 핸들러(on_event)와 상태 핸들러(on_status)를 주입하면,
토큰 발급 → 접속/로그인 → 조건식 등록 → 이벤트 수신을 담당하고
연결이 끊기면 지수 백오프로 자동 재접속한다.
"""

import asyncio
import logging

import websockets

from events import ConditionEvent
from kiwoom_client import KiwoomConditionClient, issue_access_token
from notifier import StockNameResolver

log = logging.getLogger("runner")

RECONNECT_MAX_DELAY = 60  # 자동 재접속 백오프 상한(초)


def select_conditions(available: dict, wanted: list) -> dict:
    """config 의 조건식 이름을 서버 목록의 seq 로 매칭. 빈 목록이면 전체 감시."""
    if not wanted:
        log.info("감시 대상 미지정 → 서버 저장 조건식 전체를 감시합니다.")
        return dict(available)
    selected = {}
    for name in wanted:
        if name in available:
            selected[name] = available[name]
        else:
            log.warning("조건식 '%s' 를 서버에서 찾지 못했습니다. (서버 저장 여부/이름 확인)", name)
    if not selected:
        log.error("매칭된 조건식이 없습니다. 사용 가능한 조건식: %s", list(available.keys()))
    return selected


class Runner:
    def __init__(self, settings, on_event, on_status=None, on_conditions=None):
        """
        on_event(ConditionEvent): 편입/이탈(및 초기 스냅샷) 이벤트마다 호출.
        on_status(str): 시작/종료 등 상태 메시지(선택).
        on_conditions(dict): 등록된 {조건명: seq} 가 확정되면 호출(선택).
        """
        self.settings = settings
        self.on_event = on_event
        self.on_status = on_status
        self.on_conditions = on_conditions
        self.conditions = {}  # 현재 등록된 {조건명: seq} (대시보드가 참조)

    def _status(self, text: str):
        log.info(text.replace("\n", " "))
        if self.on_status:
            self.on_status(text)

    async def run_forever(self):
        delay = 2
        while True:
            try:
                await self._session()
                delay = 2  # 정상 반환 시 백오프 초기화
            except (websockets.ConnectionClosed, OSError, asyncio.TimeoutError) as exc:
                log.warning("연결 끊김(%s). %d초 후 재접속합니다.", type(exc).__name__, delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, RECONNECT_MAX_DELAY)
            except RuntimeError as exc:
                # 설정/조건식 문제 등 재시도해도 의미 없는 오류는 종료한다.
                log.error("%s", exc)
                self._status(f"⛔ 조건검색 종료: {exc}")
                return

    async def _session(self):
        s = self.settings
        token = issue_access_token(s.rest_base, s.app_key, s.secret_key)
        resolver = (
            StockNameResolver(s.rest_base, s.app_key, token)
            if s.resolve_stock_name else None
        )

        client = KiwoomConditionClient(s.ws_url, token)
        await client.connect_and_login()

        available = await client.fetch_condition_list()
        selected = select_conditions(available, s.conditions)
        if not selected:
            raise RuntimeError("등록할 조건식이 없습니다. config.yaml 의 conditions 를 확인하세요.")

        # 키움 제한: 실시간 조건검색은 최대 10개 조건식까지만 등록 가능.
        if len(selected) > 10:
            log.warning("조건식이 %d개입니다. 키움은 실시간 조건검색을 최대 10개까지만 "
                        "허용하므로 앞 10개만 등록합니다.", len(selected))
            selected = dict(list(selected.items())[:10])

        self.conditions = selected
        if self.on_conditions:
            self.on_conditions(selected)
        seq_to_name = {seq: name for name, seq in selected.items()}
        for seq in selected.values():
            await client.register_realtime(seq)
            await asyncio.sleep(0.3)  # 조건검색 요청 속도 제한(초당 5건) 여유
        self._status("✅ 조건검색 시작\n감시 조건: " + ", ".join(selected.keys()))

        loop = asyncio.get_running_loop()

        async def raw(seq, cond, code, signal, ts, initial=False):
            # 종목명 조회는 동기 HTTP 라서 이벤트 루프에서 직접 부르면 루프가 멈춘다
            # (접속 직후 편입 종목이 많으면 웹서버가 응답 못 함). 스레드로 떠넘긴다.
            if resolver:
                name = await loop.run_in_executor(None, resolver.resolve, code)
            else:
                name = ""
            self.on_event(ConditionEvent(cond, seq, code, name, signal, ts, initial))

        await client.listen(raw, seq_to_name)
