# 시스템 통합 가이드 (TaskController 쪽에서 봐야 할 문서)

`rag_router`는 통신부(Gateway)만 구현되어 있습니다. TaskController(별도 저장소)가 이 모듈과
같은 프로세스 안에서 함께 실행되도록 엮는 **연결 스크립트**를 작성할 때, `rag_router`에서
**import(선언)해야 할 것은 아래 4개뿐**입니다.

## 왜 "같은 프로세스"여야 하는가

`rag_router.shared_queues.SharedQueues`는 `queue.Queue()`를 모듈 레벨에 두고 import로
공유하는 방식입니다. 별도 브로커 프로세스가 없기 때문에, **Gateway와 TaskController가
같은 파이썬 프로세스 안에서 함께 떠 있어야만** 큐가 실제로 공유됩니다. 서로 다른 터미널에서
각각 실행하면 프로세스가 분리되어 큐가 공유되지 않고, 요청이 응답을 받지 못한 채 타임아웃됩니다.

## 설치

```bash
pip install -e /path/to/RAG_Router
# 또는
pip install rag-router   # 별도 인덱스/git에 배포했다면
```

## import해야 할 것 4가지

| # | 무엇을 | 어디서 | 용도 |
| - | --- | --- | --- |
| 1 | `SharedQueues` | `rag_router.shared_queues` | `SharedQueues.get_queues()`로 Gateway와 동일한 `task_queue`/`result_queue`를 얻는다 |
| 2 | `Task` | `rag_router.task.task` | `task_queue`에서 꺼내는 요청 객체의 타입 (직접 생성하지 않음, 읽기 전용) |
| 3 | `TaskResult` | `rag_router.task.task_result` | 처리 결과를 담아 `result_queue`에 넣을 때 생성하는 객체 |
| 4 | `gateway` (또는 `app`) | `rag_router.gateway` | 실제 HTTP 서버를 기동 (`gateway.run()`) |

`rag_router.interface.*`(`TaskInterface`, `TaskResultInterface`)는 `Task`/`TaskResult`가
지키는 계약을 정의만 할 뿐이라 직접 import할 필요는 없습니다 — 참고용입니다.

### 1. `SharedQueues.get_queues()`

```python
from rag_router.shared_queues import SharedQueues

task_queue, result_queue = SharedQueues.get_queues()
```

- `task_queue`: Gateway가 요청을 `Task`로 감싸서 넣는 곳. TaskController는 여기서 **꺼내기만** 한다.
- `result_queue`: TaskController가 처리 결과(`TaskResult`)를 넣는 곳. Gateway가 여기서 꺼내 응답한다.
- 둘 다 표준 `queue.Queue()`이므로 `.get(timeout=...)` / `.put(...)`로 다룬다.

### 2. `Task` — 큐에서 꺼내는 요청 객체

```python
from rag_router.task.task import Task
```

TaskController가 직접 생성하지 않는다. `task_queue.get()`으로 꺼낸 객체가 이미 `Task` 인스턴스이며,
아래 속성은 전부 **읽기 전용 프로퍼티**다.

| 속성 | 타입 | 설명 |
| --- | --- | --- |
| `task.job_id` | `str` | Gateway가 요청마다 발급한 고유 ID. **응답에 그대로 되돌려줘야 함** |
| `task.task_type` | `str` | 클라이언트가 보낸 식별자 (예: `"USER_LIST"`) |
| `task.session_id` | `Optional[str]` | 클라이언트가 보낸 세션 ID (없으면 `None`) |
| `task.payload` | `dict[str, Any]` | 요청 데이터. 클라이언트가 생략하면 `{}` |
| `task.token` | `Optional[str]` | `Authorization: Bearer <token>` 헤더에서 추출된 값. 헤더가 없으면 `None`. **role 체크는 여기서 꺼낸 값으로 TaskController가 직접 해야 한다** |

### 3. `TaskResult` — 큐에 넣어야 하는 응답 객체

```python
from rag_router.task.task_result import TaskResult

result = TaskResult(
    job_id=task.job_id,      # 필수: 처리한 Task의 job_id와 반드시 동일해야 함
    success=True,             # bool
    data={"...": "..."},      # 성공 시 payload에 해당하는 dict (실패면 None으로 둬도 됨)
    error=None,                # 실패 시 에러 메시지 문자열
)
result_queue.put(result)
```

**[중요] `job_id`를 틀리거나 누락하면** Gateway는 어떤 요청에 대한 응답인지 매칭하지 못해서,
그 요청은 결국 타임아웃(`Gateway.TIMEOUT_SEC`, 기본 60초)으로 실패한다.

### 4. `gateway` — 실제 서버 기동

```python
from rag_router.gateway import gateway
# 또는: from rag_router.gateway import app  (ASGI app만 필요한 경우)

gateway.run()  # config.json의 server.host/port로 uvicorn을 블로킹 실행
```

`gateway.run()`은 블로킹 호출이다. TaskController의 처리 루프는 **그 전에** 백그라운드 스레드로
먼저 띄워야 한다.

## 연결 스크립트 예시

```python
import threading
from rag_router.gateway import gateway
from your_taskcontroller_package import TaskController  # 실제 TaskController 저장소

def run_task_controller():
    controller = TaskController()
    controller.run()  # 내부에서 SharedQueues.get_queues()로 큐를 얻어 루프를 돈다

threading.Thread(target=run_task_controller, daemon=True).start()
gateway.run()  # 메인 스레드는 여기서 블로킹
```

`rag_router/mock_taskcontroller.py`의 `MockTaskController`가 이 패턴의 실제 동작 예시입니다
(`task_queue.get()` → 처리 → `TaskResult`를 `job_id` 그대로 실어 `result_queue.put()`).

## 체크리스트

- [ ] `SharedQueues.get_queues()`로 얻은 큐를 그대로 쓰는가 (직접 `queue.Queue()`를 새로 만들지 않는가)
- [ ] `TaskResult.job_id`가 처리한 `Task.job_id`와 항상 동일한가
- [ ] `role` 체크가 필요한 task_type(`USER_SET_ROLE`, `FILE_UPLOAD`, `FILE_DELETE`, `FILE_DOWNLOAD`,
      `EXTERNAL_API_*` 등)에서 `task.token`을 검증하고 있는가
- [ ] 연결 스크립트가 TaskController 루프를 백그라운드 스레드로 먼저 띄운 뒤 `gateway.run()`을 호출하는가
