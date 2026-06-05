"""실시간 대시보드 웹서버 (aiohttp + SSE).

- GET /            : 대시보드 HTML
- GET /api/state   : 현재 상태 스냅샷(JSON)
- GET /events      : Server-Sent Events 스트림 (상태 변경을 브라우저로 푸시)

키움 리스너와 같은 asyncio 루프에서 돌기 때문에, 이벤트 발생 시 broadcast() 로
연결된 모든 브라우저의 큐에 바로 넣어준다.
"""

import asyncio
import json
import logging
from pathlib import Path

from aiohttp import web

log = logging.getLogger("web")

STATIC_DIR = Path(__file__).resolve().parent / "static"


class WebServer:
    def __init__(self, state, port: int = 8765):
        self.state = state
        self.port = port
        self._clients = set()  # 연결된 SSE 클라이언트의 asyncio.Queue 집합
        self._runner = None

        self.app = web.Application()
        self.app.add_routes([
            web.get("/", self._index),
            web.get("/api/state", self._api_state),
            web.get("/events", self._sse),
        ])

    async def start(self):
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self.port)
        await site.start()
        log.info("대시보드 시작: http://localhost:%d", self.port)

    async def stop(self):
        if self._runner:
            await self._runner.cleanup()

    def broadcast(self, payload: dict):
        """상태 변경을 연결된 모든 브라우저로 푸시한다."""
        data = json.dumps(payload, ensure_ascii=False)
        for queue in list(self._clients):
            try:
                queue.put_nowait(data)
            except asyncio.QueueFull:
                pass  # 느린 클라이언트는 일부 이벤트를 흘려도 다음 스냅샷으로 복구됨

    # ── 라우트 핸들러 ──────────────────────────────────────────────
    async def _index(self, request):
        html = STATIC_DIR / "dashboard.html"
        return web.FileResponse(html)

    async def _api_state(self, request):
        return web.json_response(self.state.snapshot())

    async def _sse(self, request):
        resp = web.StreamResponse(headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        })
        await resp.prepare(request)

        queue = asyncio.Queue(maxsize=1000)
        self._clients.add(queue)
        try:
            # 접속 즉시 현재 스냅샷 1회 전송
            await self._write(resp, json.dumps(self.state.snapshot(), ensure_ascii=False))
            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=20)
                    await self._write(resp, data)
                except asyncio.TimeoutError:
                    await resp.write(b": keep-alive\n\n")  # 연결 유지용 주석
        except (ConnectionResetError, asyncio.CancelledError):
            pass
        finally:
            self._clients.discard(queue)
        return resp

    @staticmethod
    async def _write(resp, data: str):
        await resp.write(f"data: {data}\n\n".encode("utf-8"))
