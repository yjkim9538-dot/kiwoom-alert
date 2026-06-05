"""조건검색 이벤트 공통 모델.

텔레그램 알림(main.py)과 웹 대시보드(dashboard.py)가 같은 이벤트를 공유한다.
"""

from dataclasses import dataclass


@dataclass
class ConditionEvent:
    condition: str   # 조건식 이름
    seq: str         # 조건식 일련번호
    code: str        # 종목코드 (6자리)
    name: str        # 종목명 (조회 실패 시 "")
    signal: str      # "I"(편입) / "D"(이탈)
    ts: str          # 체결시간 HHMMSS (초기 스냅샷은 "")
    initial: bool = False  # 등록 직후 현재 편입 종목 스냅샷이면 True

    @property
    def is_insert(self) -> bool:
        return self.signal == "I"

    @property
    def flag(self) -> str:
        """config 의 notify_on 값과 맞추기 위한 'insert'/'delete'."""
        return "insert" if self.signal == "I" else "delete"
