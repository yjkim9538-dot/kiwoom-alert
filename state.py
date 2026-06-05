"""대시보드 인메모리 상태 — 조건별 현재 편입 종목, 관심종목, 최근 이벤트.

단일 asyncio 이벤트 루프 안에서만 갱신되므로 별도 락이 필요 없다.
"""

from collections import deque
from datetime import datetime

MAX_EVENTS = 200  # 화면에 유지할 최근 이벤트 수


def _fmt_ts(ts: str) -> str:
    digits = "".join(ch for ch in ts if ch.isdigit())
    if len(digits) >= 6:
        return f"{digits[0:2]}:{digits[2:4]}:{digits[4:6]}"
    return datetime.now().strftime("%H:%M:%S")


class DashboardState:
    def __init__(self, watchlist: dict, environment: str = ""):
        # watchlist: {code: name}
        self.watchlist = dict(watchlist)
        self.environment = environment
        # conditions: {조건명: {code: {"name":..., "since":...}}}
        self.conditions = {}
        self.events = deque(maxlen=MAX_EVENTS)

    def set_conditions(self, names):
        """등록된 조건식 목록을 초기화한다(재접속 시 멤버를 비움)."""
        self.conditions = {name: {} for name in names}

    def apply(self, ev) -> dict:
        """이벤트를 상태에 반영하고, 피드에 넣을 이벤트 dict 를 반환(초기 스냅샷은 None)."""
        members = self.conditions.setdefault(ev.condition, {})
        # 관심종목이면 이름이 비어 있어도 watchlist 에 등록된 이름을 보강
        name = ev.name or self.watchlist.get(ev.code, "")
        # 반대로 watchlist 에 이름이 비어 있으면 이벤트에서 받은 이름으로 채운다
        if ev.code in self.watchlist and not self.watchlist[ev.code] and ev.name:
            self.watchlist[ev.code] = ev.name
        if ev.is_insert:
            members[ev.code] = {"name": name, "since": _fmt_ts(ev.ts)}
        else:
            members.pop(ev.code, None)

        if ev.initial:
            return None
        entry = {
            "condition": ev.condition,
            "code": ev.code,
            "name": name,
            "signal": ev.signal,
            "time": _fmt_ts(ev.ts),
            "watch": ev.code in self.watchlist,
        }
        self.events.appendleft(entry)
        return entry

    def _condition_payload(self):
        out = []
        for name, members in self.conditions.items():
            rows = [
                {"code": code, "name": info["name"], "since": info["since"],
                 "watch": code in self.watchlist}
                for code, info in members.items()
            ]
            # 관심종목을 위로 정렬
            rows.sort(key=lambda r: (not r["watch"], r["code"]))
            out.append({"name": name, "count": len(rows), "members": rows})
        return out

    def _watchlist_payload(self):
        out = []
        for code, name in self.watchlist.items():
            in_conditions = [
                cond for cond, members in self.conditions.items() if code in members
            ]
            out.append({"code": code, "name": name, "conditions": in_conditions})
        return out

    def snapshot(self) -> dict:
        return {
            "type": "snapshot",
            "environment": self.environment,
            "conditions": self._condition_payload(),
            "watchlist": self._watchlist_payload(),
            "events": list(self.events),
        }
