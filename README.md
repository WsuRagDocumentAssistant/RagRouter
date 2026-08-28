# rag-router — 통신부 (Gateway)

RAG 시스템 전체 아키텍처 중 **통신부(Communication Layer)** 만 구현되어 있는 pip 설치 가능한 패키지입니다.
클라이언트의 요청을 받아 `task_type` 식별자로 구분한 뒤, TaskController에게 작업을 넘기고 결과를 돌려줍니다.

- Python 3.11
- FastAPI + uvicorn
- 단일 API 엔드포인트, JSON body 안의 `task_type` 필드로 작업 구분

## 요청 흐름

```
Client
  │  POST /api/task  { task_type, session_id, payload }
  ▼
Gateway (rag_router/gateway.py, FastAPI)
  │  RequestHandler.submit() → Task 생성 → task_queue.put(task)
  ▼
task_queue  ─────────────────────────────────┐
                                              │  (SharedQueues로 공유되는 큐)
                                              ▼
                                        TaskController
                                     (다른 저장소에서 개발 예정,
                                      지금은 mock_taskcontroller.py로 대체)
                                              │
                                              │  처리 후 TaskResult 생성
                                              ▼
result_queue ◄────────────────────────────────┘
  │
  ▼
ResultDispatcher (백그라운드 스레드)
  │  result_queue를 감시하다 job_id로 asyncio.Future를 resolve
  ▼
ResponseHandler.build() → TaskResponse
  │
  ▼
Client ← HTTP 응답
```

Gateway는 `task_type`의 의미를 전혀 모릅니다. 그저 식별자로 보고 실어 나를 뿐이며,
실제 분기/처리 로직은 TaskController(별도 저장소)의 책임입니다.

각 요청은 서버가 발급한 고유 `job_id`로 관리됩니다. 요청마다 자기만의 `asyncio.Future`가
`job_id`를 키로 매핑 테이블에 등록되고, 결과가 도착하면 그 `job_id`에 해당하는 Future만
정확히 깨어나기 때문에 여러 사용자가 동시에 호출해도 응답이 서로 섞이지 않습니다.

## 패키지 구조

```
RAG_Router/
├── pyproject.toml                 # 패키지 메타데이터 (pip install 가능하게 함)
├── requirements.txt               # 로컬 개발용 (venv에 그대로 pip install -r)
├── README.md
│
└── rag_router/                    # 배포되는 패키지 본체
    ├── __init__.py
    ├── gateway.py                 # 진입점. FastAPI 앱, 라우팅, 시작 시 큐 연결, main()
    ├── mock_taskcontroller.py     # [테스트 전용] TaskController를 흉내내는 echo 목업
    ├── shared_queues.py           # 같은 프로세스 안에서 공유되는 task_queue/result_queue
    ├── result_dispatcher.py       # result_queue를 감시해 job_id로 응답을 매칭하는 백그라운드 디스패처
    ├── config.json                # 구조적 기본값 (server.host/port/log_level)
    │
    ├── dto/                       # 통신부의 HTTP 요청/응답 바디 (pydantic)
    │   ├── task_request.py        #   TaskRequest
    │   └── task_response.py       #   TaskResponse
    │
    ├── task/                      # 큐에 실제로 오가는 내부 데이터 모델
    │   ├── task.py                #   Task (TaskInterface 구현체)
    │   └── task_result.py         #   TaskResult (TaskResultInterface 구현체)
    │
    ├── interface/                 # task/ 구현체가 반드시 지켜야 하는 추상 인터페이스
    │   ├── task_interface.py      #   TaskInterface
    │   └── task_result_interface.py  # TaskResultInterface
    │
    └── helpers/
        ├── config_helper.py       # ConfigHelper — config.json 로딩
        ├── log_helper.py          # LogHelper — 로깅 설정 (KST 타임존 포맷)
        ├── request_helper.py      # RequestHandler — TaskRequest → Task 변환, 큐 적재, 결과 대기
        └── response_helper.py     # ResponseHandler — TaskResult → TaskResponse 변환
```

모든 모듈이 `rag_router` 패키지 안에 있어서, 설치 후에도 `dto`/`task`/`interface`/`helpers` 같은
이름이 전역 네임스페이스를 오염시키지 않습니다 (항상 `rag_router.xxx`로 import됨).

## 설치 및 실행

로컬 개발(가상환경에 바로 설치):

```bash
pip install -r requirements.txt
```

패키지로 설치(콘솔 스크립트/다른 프로젝트에서 import):

```bash
pip install -e .
```

실행 방법 (아래 셋 다 동일하게 동작):

```bash
rag-router
```

```bash
python -m rag_router.gateway
```

```bash
uvicorn rag_router.gateway:app --host 0.0.0.0 --port 8000
```

모두 `rag_router/config.json`의 `server.host` / `server.port` / `server.log_level`을 기본값으로 사용합니다.

### API

**POST `/api/task`**

```json
{
  "task_type": "USER_QUERY",
  "session_id": "optional-session-id",
  "payload": { "query": "..." }
}
```

`payload`는 생략하면 `{}`로 처리됩니다 (`USER_LIST`처럼 payload가 필요 없는 task_type용).

인증이 필요한 요청은 `Authorization: Bearer <token>` 헤더로 토큰을 실어 보냅니다. Gateway는 이 헤더를
파싱해서 `Task.token`으로 TaskController에 전달합니다 — body의 `payload`에는 토큰을 넣지 않습니다.

응답:

```json
{
  "task_type": "USER_QUERY",
  "status": "success",
  "result": { "...": "..." },
  "error_message": null
}
```

`status`는 `success` / `error` / `timeout` 중 하나이며, 타임아웃은 `Gateway.TIMEOUT_SEC`(기본 60초)으로 제어됩니다.

### CORS

`config.json`의 `cors.allowed_origins`에 등록된 origin만 브라우저에서 호출할 수 있습니다
(기본값: Vite 개발 서버 `http://localhost:5173` / `http://127.0.0.1:5173`). 다른 origin(운영 도메인,
Cloudflare 터널 등)에서 붙여야 하면 이 목록에 추가해야 합니다.

## 설정 우선순위

값 하나당 아래 순서로 결정됩니다: **환경변수(.env) > config.json > 코드 기본값**

- `config.json`: 비밀값이 아닌 구조적 기본값 (지금은 `server` 섹션만 존재). git에 커밋됨.
- `.env`: 비밀값/환경별로 달라지는 값 (API 키, DB 비밀번호, 실제 운영 서버 IP 등). git에 커밋하지 않음.

현재는 `.env` 파일이 없어서 전부 `config.json` 값을 그대로 사용합니다.

## ⚠️ 현재 구조의 제약: 같은 프로세스여야 함

`shared_queues.py`는 `queue.Queue()`를 모듈 레벨에 두고 import로 공유하는 방식입니다.
이 방식은 **Gateway와 TaskController가 같은 파이썬 프로세스 안에서 함께 떠 있을 때만** 동작합니다.
서로 다른 터미널에서 각각 실행하면 프로세스가 분리되어 큐가 공유되지 않고, 요청이 응답을
받지 못한 채 타임아웃됩니다.

TaskController는 별도 저장소(레포)에서 개발될 예정이며, 나중에 Gateway와 TaskController를
같은 프로세스 안에서 함께 import해서 띄우는 **연결 스크립트**가 추가될 예정입니다.
그 전까지 두 모듈을 동시에 검증하려면, 하나의 파이썬 스크립트 안에서 `rag_router.gateway`의
`Gateway`와 `rag_router.mock_taskcontroller`의 `MockTaskController`를 함께 띄워야 합니다
(`MockTaskController().run()`을 백그라운드 스레드로 실행).

## 공개 배포 전 체크리스트

공개 PyPI에 올릴 계획이라면:

- [ ] `pyproject.toml`의 패키지명(`rag-router`)이 PyPI에서 사용 가능한지 확인
- [ ] `rag_router/config.json`에 민감한 값(내부 IP, 실제 자격증명 등)이 없는지 재확인
- [ ] 버전 정책 결정 (지금은 `0.1.0` 고정)

## TODO

- [ ] 실제 TaskController 저장소와 Gateway를 함께 띄우는 연결 스크립트
- [ ] `mock_taskcontroller.py` → 실제 TaskController로 교체 — 그 안에서 `task.token`을 검증하고
      `role` 기반 권한 체크(관리자 전용 API 등)를 하는 건 TaskController의 책임
- [ ] `.env`를 이용한 비밀값(LLM API 키, DB 비밀번호 등) 관리
