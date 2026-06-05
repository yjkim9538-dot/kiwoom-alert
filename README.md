# 키움 조건검색 실시간 알림 (kiwoom_alert)

키움증권 **REST/WebSocket Open API** 로 HTS 조건검색(조건식, 예: `데드크로스 알리미`)을
실시간 감시하다가, 종목이 조건에 **편입/이탈** 될 때마다 **텔레그램 단톡방**으로 알림을 보냅니다.
운영 PC 한 대에서만 실행하면, 단톡방에 들어와 있는 **본부원 전원**이 모바일 푸시로 받습니다.

```
키움 WebSocket(조건검색 실시간)  →  이 프로그램(운영 PC 1대)  →  텔레그램 단톡방  →  본부원 전원
```

**두 가지 실행 방법**이 있습니다 (설정 파일은 공유):
- **`main.py`** — 텔레그램 알림만 (가볍게, 백그라운드 상시 운영용)
- **`dashboard.py`** — 텔레그램 알림 **+ 실시간 웹 대시보드** (관심종목·조건식 현황을 브라우저로 시각화)

---

## 1. 준비물

| 항목 | 설명 |
|------|------|
| 키움 REST API 앱키/시크릿키 | https://openapi.kiwoom.com 에서 앱 등록 후 발급 |
| 서버 저장된 조건식 | 영웅문/HTS 조건검색에서 조건식을 **"서버 저장"** 해 두어야 API 로 보입니다 |
| 텔레그램 봇 토큰 | 텔레그램 `@BotFather` 로 봇 생성 시 발급 |
| 텔레그램 단톡방 chat_id | 본부원 단톡방에 봇을 초대하고 얻는 ID |
| Python 3.11+ | https://www.python.org (설치 시 "Add to PATH" 체크) |

---

## 2. 키움 API 키 발급

1. https://openapi.kiwoom.com 접속 → 로그인 → **앱(App) 등록**.
2. 발급된 **앱키(appkey)** 와 **시크릿키(secretkey)** 를 복사해 둡니다.
3. 영웅문/HTS 의 조건검색 화면에서 알림 받을 조건식을 만들고 **반드시 "서버 저장"** 합니다.
   (서버에 저장된 조건식만 API 로 조회·등록할 수 있습니다.)
4. 처음에는 **모의투자(mock)** 환경으로 테스트하는 것을 권장합니다.

---

## 3. 텔레그램 설정

### 3-1. 봇 만들기
1. 텔레그램에서 `@BotFather` 를 검색해 대화 시작.
2. `/newbot` 입력 → 봇 이름과 사용자명 지정 → **봇 토큰**(`123456:ABC-...`)을 받습니다.

### 3-2. 단톡방에 봇 초대
1. 본부원 단톡방(그룹)을 만들고 **방금 만든 봇을 멤버로 초대**합니다.
2. 그룹에서 아무 메시지나 하나 보냅니다(봇이 방을 인식하도록).

### 3-3. chat_id 얻기
브라우저에서 아래 주소를 엽니다(`<봇토큰>` 자리에 본인 토큰):
```
https://api.telegram.org/bot<봇토큰>/getUpdates
```
응답 JSON 에서 `"chat":{"id":-1001234567890, ...}` 의 **id 값**이 단톡방 chat_id 입니다.
(그룹은 보통 `-100` 으로 시작하는 음수입니다.)

> 봇이 그룹 메시지를 못 읽으면 BotFather 에서 `/setprivacy` → **Disable** 로 설정하세요.

---

## 4. 설치 & 설정

```bash
# 저장소를 받은 뒤 이 폴더로 이동
cd kiwoom_alert

# 1) 비밀 키 파일 만들기
#    Windows:  copy .env.example .env
#    mac/Linux: cp .env.example .env
#    → .env 를 열어 키움 앱키/시크릿키, 텔레그램 봇토큰/chat_id 를 채웁니다.

# 2) 동작 설정 파일 만들기
#    Windows:  copy config.example.yaml config.yaml
#    mac/Linux: cp config.example.yaml config.yaml
#    → config.yaml 에서 감시할 조건식 이름과 옵션을 설정합니다.
```

`config.yaml` 핵심 항목:
```yaml
environment: mock          # mock(모의) 으로 먼저 테스트 → 이후 real(실전)
conditions:
  - 데드크로스 알리미       # 감시할 조건식 이름 (HTS 에 서버 저장된 이름과 정확히 일치)
notify_on: [insert, delete] # 편입/이탈 중 알림 받을 신호
```
> `conditions` 를 비우면 서버에 저장된 **모든** 조건식을 감시합니다.

---

## 5. 먼저 연결 점검 (`test_connection.py`)

본격 실행 전에 키/설정이 맞는지 한 단계씩 확인합니다. (키는 화면에 노출되지 않습니다.)
```bash
python test_connection.py
```
순서대로 ① 설정 로드 ② 텔레그램 테스트 메시지 ③ 키움 토큰 발급 ④ WebSocket 로그인
⑤ 조건식 목록을 점검하고, 서버에 저장된 조건식 목록과 `config.yaml` 매칭 결과를 보여줍니다.
모두 통과하면 아래 실행으로 넘어가세요.

---

## 6. 실행 — 텔레그램 알림만 (`main.py`)

- **Windows**: `run.bat` 더블클릭 (처음 1회 자동으로 의존성 설치)
- **mac/Linux/서버**: `bash run.sh`
- 수동 실행:
  ```bash
  pip install -r requirements.txt
  python main.py
  ```

정상이면 단톡방에 `✅ 조건검색 알림 시작 ...` 메시지가 오고, 이후 조건 편입/이탈 시
`🔔 [데드크로스 알리미] 삼성전자(005930) 편입 (09:31:05)` 형태로 알림이 옵니다.
종료는 실행 창에서 **Ctrl + C**.

> ⏰ 실시간 조건검색은 **장 운영 시간(평일 09:00~15:30)** 에 이벤트가 발생합니다.
> 장 마감 후에는 시작 메시지만 오고 편입/이탈 알림은 오지 않는 게 정상입니다.

---

## 7. 실행 — 실시간 웹 대시보드 (`dashboard.py`)

조건식 현황과 관심종목을 **브라우저에서 실시간으로** 보고 싶을 때 사용합니다.
(텔레그램 알림도 함께 전송됩니다.)

- **Windows**: `run_dashboard.bat` 더블클릭 → 브라우저가 자동으로 열립니다.
- **mac/Linux/서버**: `bash run_dashboard.sh`
- 수동 실행: `python dashboard.py`

실행 후 브라우저에서 **http://localhost:8765** 접속(포트는 `config.yaml` 의 `dashboard_port`).

### 관심종목 설정
`config.yaml` 에서 지정합니다. 대시보드에서 ★ 로 강조되고, 각 종목이 현재 어떤
조건식에 편입돼 있는지 별도 패널로 보여줍니다.
```yaml
watchlist:
  - "005930 삼성전자"     # "코드 이름"
  - "000660"             # 코드만 적어도 됨(이름은 실시간 조회로 채워짐)
dashboard_port: 8765
```

### 화면 구성
| 영역 | 내용 |
|------|------|
| **조건식별 편입 종목** | 조건식마다 카드로, 현재 편입된 종목 목록과 편입 시각을 실시간 표시 |
| **관심종목 현황** | 지정한 관심종목이 지금 어떤 조건식에 들어가 있는지 칩으로 표시 |
| **실시간 이벤트** | 편입(초록)/이탈(빨강) 이벤트가 발생 즉시 위에서부터 쌓이는 타임라인 |

화면은 새로고침 없이 자동 갱신됩니다(서버가 브라우저로 푸시; SSE).
같은 네트워크의 다른 PC에서 보려면 `http://<운영PC_IP>:8765` 로 접속하세요(방화벽 허용 필요).

> 대시보드는 **사내/로컬 열람용**입니다. 외부에 공개하려면 인증·HTTPS를 별도로 두세요.

---

## 8. 24시간 상시 운영 (선택)

### Windows
작업 스케줄러에서 "로그온 시 `run.bat` 실행" 으로 등록하거나, PC 를 켜둔 채 실행해 둡니다.

### Linux 서버 (systemd 예시)
`/etc/systemd/system/kiwoom-alert.service`:
```ini
[Unit]
Description=Kiwoom Condition Alert
After=network-online.target

[Service]
WorkingDirectory=/home/youruser/kiwoom_alert
# 텔레그램만: main.py / 대시보드까지: dashboard.py
ExecStart=/home/youruser/kiwoom_alert/.venv/bin/python dashboard.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable --now kiwoom-alert
journalctl -u kiwoom-alert -f   # 로그 보기
```

---

## 9. 보안 주의 ⚠️

- `.env` 와 `config.yaml` 에는 **키와 개인 설정이 들어가므로 깃허브에 올라가지 않습니다**
  (`.gitignore` 로 제외). 커밋되는 건 `*.example.*` 뿐입니다.
- 키움 앱키/시크릿키, 봇 토큰이 유출되면 즉시 키움/`@BotFather` 에서 재발급하세요.
- **키는 운영 PC 의 `.env` 파일에만** 두세요. 채팅·메신저·이메일·캡처 등에 붙여넣지 마세요.
  (브로커리지 키는 계좌 접근 권한이 있는 민감 정보입니다.)
- 운영 PC 는 **한 대만** 실행하세요(여러 대면 중복 알림이 갑니다).
- 대시보드 포트(기본 8765)는 **사내망에만** 열어 두세요. 외부 공개 시 인증/HTTPS 필요.

---

## 10. 파일 구조

| 파일 | 역할 |
|------|------|
| `main.py` | 진입점(텔레그램 전용): 접속 → 조건 등록 → 이벤트 루프 |
| `dashboard.py` | 진입점(대시보드+텔레그램): 리스너 + 웹서버를 한 프로세스로 |
| `test_connection.py` | 연결 진단: 토큰/로그인/조건목록/텔레그램 단계별 점검 |
| `runner.py` | 공통 엔진: 토큰 발급/접속/조건 등록/이벤트 루프(자동 재접속) |
| `kiwoom_client.py` | 키움 토큰 발급 + WebSocket(LOGIN/PING/CNSRLST/CNSRREQ/REAL) |
| `notifier.py` | 텔레그램 전송 + (선택) 종목명 조회 |
| `state.py` | 대시보드 인메모리 상태(조건별 편입 종목·관심종목·이벤트) |
| `webserver.py` | aiohttp 웹서버 + SSE 실시간 푸시 |
| `static/dashboard.html` | 대시보드 화면(자체 완결형, 외부 의존성 없음) |
| `events.py` | 공통 이벤트 모델 |
| `config.py` | `.env` + `config.yaml` 로드/검증 |
| `config.example.yaml` / `.env.example` | 설정 템플릿 (복사해서 사용) |
| `run.bat`·`run.sh` / `run_dashboard.bat`·`run_dashboard.sh` | 실행 스크립트 |

---

## 11. 문제 해결

| 증상 | 확인 |
|------|------|
| `설정 오류: .env 파일이 없습니다` | `.env.example` 을 복사해 `.env` 를 만들었는지 |
| `LOGIN 실패` | 앱키/시크릿키, `environment`(real/mock) 가 맞는지 |
| `조건식 '...' 를 서버에서 찾지 못했습니다` | HTS 에서 **서버 저장** 했는지, 이름이 정확히 일치하는지 |
| 텔레그램이 안 옴 | 봇을 그룹에 초대했는지, `chat_id` 가 맞는지, 봇 privacy Disable 여부 |
| 알림이 안 오는데 장중임 | 실제로 조건 편입이 발생해야 알림이 옵니다(조건이 까다로우면 드뭄) |
| 대시보드가 안 열림 | `python dashboard.py` 가 실행 중인지, 포트(8765)가 방화벽에 막혔는지 |
| 대시보드가 "연결 끊김" | 키움 접속 전/재접속 중일 수 있음. 상단 표시가 "실시간 연결됨" 되면 정상 |

> 키움 실시간 메시지의 필드 코드(편입/이탈 `843` 등)는 `kiwoom_client.py` 상단 상수로
> 분리되어 있습니다. 키움 명세가 바뀌면 그 부분만 수정하면 됩니다.
