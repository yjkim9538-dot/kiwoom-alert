"""키움 REST/WebSocket 조건검색 클라이언트.

흐름:
  1) REST 로 접속 토큰 발급 (oauth2/token)
  2) WebSocket 접속 → LOGIN
  3) CNSRLST 로 서버 저장 조건식 목록 조회
  4) CNSRREQ(search_type="1") 로 조건식을 실시간 등록
  5) REAL 메시지로 편입(I)/이탈(D) 이벤트 수신 → 콜백 호출
  + 서버 PING 은 그대로 echo, 연결 끊기면 지수 백오프로 자동 재접속.

참고: 키움 공식 가이드(openapi.kiwoom.com)의 "실시간 조건검색" 명세 기준.
실시간 필드 코드(편입/이탈 843 등)는 상수로 분리해 두었으니, 키움 명세가
바뀌면 아래 REAL_FIELD_* 만 수정하면 된다.
"""

import asyncio
import json
import logging

import requests
import websockets

log = logging.getLogger("kiwoom")

# REAL(실시간) 메시지 안의 values 필드 코드
REAL_FIELD_CODE = "9001"    # 종목코드
REAL_FIELD_SEQ = "841"      # 조건식 일련번호
REAL_FIELD_SIGNAL = "843"   # 편입/이탈 구분 ("I"=편입, "D"=이탈)
REAL_FIELD_TIME = "20"      # 체결시간 (HHMMSS)

SIGNAL_INSERT = "I"
SIGNAL_DELETE = "D"


def _extract_code(item) -> str:
    """CNSRREQ 초기 응답 항목에서 종목코드를 뽑아낸다 (응답 형식 방어적 처리)."""
    if isinstance(item, dict):
        for key in (REAL_FIELD_CODE, "jmcode", "9001", "종목코드", "stk_cd"):
            value = item.get(key)
            if value:
                return str(value).strip().lstrip("A")
    elif isinstance(item, (list, tuple)) and item:
        return str(item[0]).strip().lstrip("A")
    return ""


def _extract_seq_name(row):
    """CNSRLST 응답의 한 항목에서 (seq, 조건명)을 뽑는다.

    응답 형식이 [[seq, name], ...] 일 수도, [{"seq":..,"name":..}, ...] 일 수도 있어
    둘 다 방어적으로 처리한다.
    """
    if isinstance(row, dict):
        seq = row.get("seq") or row.get("cnsr_seq") or row.get("idx") or ""
        name = (row.get("name") or row.get("cnsr_nm")
                or row.get("cndt_nm") or row.get("condition_name") or "")
        return str(seq).strip(), str(name).strip()
    if isinstance(row, (list, tuple)) and len(row) >= 2:
        return str(row[0]).strip(), str(row[1]).strip()
    return "", ""


def issue_access_token(rest_base: str, app_key: str, secret_key: str, timeout: int = 15) -> str:
    """oauth2/token 으로 접속 토큰을 발급받는다."""
    url = f"{rest_base}/oauth2/token"
    payload = {
        "grant_type": "client_credentials",
        "appkey": app_key,
        "secretkey": secret_key,
    }
    resp = requests.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    # 키움 응답: {"token":"...","token_type":"bearer","expires_dt":"...","return_code":0,...}
    if str(data.get("return_code", "0")) not in ("0", "None"):
        raise RuntimeError(f"토큰 발급 실패: {data.get('return_msg')} ({data})")
    token = data.get("token") or data.get("access_token")
    if not token:
        raise RuntimeError(f"토큰 발급 실패(토큰 없음): {data}")
    return token


class KiwoomConditionClient:
    """조건검색 실시간 등록 + 이벤트 수신을 담당하는 WebSocket 클라이언트."""

    def __init__(self, ws_url: str, token: str):
        self.ws_url = ws_url
        self.token = token
        self.ws = None
        self._condition_list = {}  # {조건명: seq}

    async def _send(self, message: dict):
        await self.ws.send(json.dumps(message))

    async def _recv(self) -> dict:
        raw = await self.ws.recv()
        return json.loads(raw)

    async def connect_and_login(self):
        """WebSocket 접속 후 LOGIN. 실패하면 예외를 던진다."""
        self.ws = await websockets.connect(self.ws_url, ping_interval=None, max_size=None)
        await self._send({"trnm": "LOGIN", "token": self.token})
        while True:
            msg = await self._recv()
            trnm = msg.get("trnm")
            if trnm == "LOGIN":
                if str(msg.get("return_code")) != "0":
                    raise RuntimeError(f"LOGIN 실패: {msg.get('return_msg')} ({msg})")
                log.info("WebSocket 로그인 성공")
                return
            if trnm == "PING":
                await self._send(msg)  # PING 은 받은 그대로 echo

    async def fetch_condition_list(self) -> dict:
        """CNSRLST 로 서버 저장 조건식 목록을 받아 {조건명: seq} 로 반환."""
        await self._send({"trnm": "CNSRLST"})
        while True:
            msg = await self._recv()
            trnm = msg.get("trnm")
            if trnm == "PING":
                await self._send(msg)
                continue
            if trnm == "CNSRLST":
                if str(msg.get("return_code", "0")) not in ("0", "None"):
                    raise RuntimeError(f"조건식 목록조회 실패: {msg.get('return_msg')} ({msg})")
                result = {}
                for row in msg.get("data") or []:
                    seq, name = _extract_seq_name(row)
                    if name:
                        result[name] = seq
                self._condition_list = result
                log.info("조건식 목록 %d개 조회: %s", len(result), list(result.keys()))
                return result

    async def register_realtime(self, seq: str):
        """CNSRREQ(search_type=1) 로 조건식 seq 를 실시간 등록한다."""
        await self._send({
            "trnm": "CNSRREQ",
            "seq": str(seq),
            "search_type": "1",   # 0: 단발 / 1: 조건검색 + 실시간
            "stex_tp": "K",       # K: KRX
            "cont_yn": "N",
            "next_key": "",
        })
        log.info("조건식 실시간 등록 요청: seq=%s", seq)

    async def listen(self, on_event, seq_to_name: dict):
        """메시지를 수신해 편입/이탈 이벤트마다 on_event 콜백 호출.

        on_event(seq, name, code, signal, time, initial) 형태로 호출한다.
        - signal 은 "I"(편입) / "D"(이탈)
        - initial=True 는 조건검색 등록 직후 받은 "현재 편입 종목" 스냅샷이라는 뜻.
          (알림은 보통 스킵하고, 대시보드 초기 상태 채우기에만 사용)

        on_event 가 코루틴을 반환하면 await 한다. 종목명 조회처럼 시간이 걸리는
        작업을 콜백이 비동기로 처리해도 이벤트 루프(웹서버 등)가 멈추지 않는다.
        """
        async def dispatch(*args):
            res = on_event(*args)
            if asyncio.iscoroutine(res):
                await res

        while True:
            msg = await self._recv()
            trnm = msg.get("trnm")

            if trnm == "PING":
                await self._send(msg)
                continue

            if trnm == "CNSRREQ":
                # 실시간 등록 직후 응답: 현재 조건에 편입돼 있는 종목 목록(초기 스냅샷).
                if str(msg.get("return_code", "0")) != "0":
                    log.warning("CNSRREQ 응답 오류: %s", msg.get("return_msg"))
                    continue
                seq = str(msg.get("seq", "")).strip()
                name = seq_to_name.get(seq, f"조건#{seq}")
                for item in msg.get("data") or []:
                    code = _extract_code(item)
                    if code:
                        await dispatch(seq, name, code, SIGNAL_INSERT, "", True)
                continue

            if trnm != "REAL":
                continue

            for item in msg.get("data") or []:
                # 보통 {"type":"02","values":{...}} 이지만, 일부 응답은 필드가
                # 항목 최상위에 바로 올 수 있어 둘 다 대응한다.
                values = item.get("values") or item
                seq = str(values.get(REAL_FIELD_SEQ, "")).strip()
                code = str(values.get(REAL_FIELD_CODE, "")).strip().lstrip("A")
                signal = str(values.get(REAL_FIELD_SIGNAL, "")).strip().upper()
                ts = str(values.get(REAL_FIELD_TIME, "")).strip()
                if not code or signal not in (SIGNAL_INSERT, SIGNAL_DELETE):
                    continue
                name = seq_to_name.get(seq, f"조건#{seq}")
                await dispatch(seq, name, code, signal, ts, False)
