"""
스트리밍 큐(TaskExecutor 쪽 work 이 채워줌)를 백그라운드 스레드로 감시하다가,
해당 job_id 를 기다리는 요청의 콜백으로 이벤트를 넘겨주는 역할.

결과 큐(ResultDispatcher)와 따로 둔다. 결과 큐는 작업당 한 번 오는 최종 값이고,
이쪽은 작업이 도는 동안 여러 번 오는 중간 값(생성 중인 답변 조각, 진행 단계)이다.
같은 큐에 섞으면 decode 가 둘을 구분해야 하고, 조각이 많을 때 최종 결과가 그 뒤에 줄을 선다.

    TaskExecutor ── LLM ──▶ 스트리밍 큐 ──▶ Router(여기) ──▶ 클라이언트
                 └────────▶ 결과 큐 ────────▶ Router(ResultDispatcher)

큐에 실려 오는 값은 (job_id, event) 다. event 는 dict 이고 모양은 work 이 정한다 —
이 파일은 내용을 보지 않고 짝(job_id)만 맞춘다. 기다리는 요청이 없으면(HTTP 요청이거나
이미 끝났거나 연결이 끊김) 버린다.
"""
import asyncio
import logging
import queue as queue_module
import threading
from typing import Any, Callable, Optional

logger = logging.getLogger("stream_dispatcher")

OnStream = Callable[[dict[str, Any]], None]


class StreamDispatcher:
    def __init__(self, stream_queue):
        self._stream_queue = stream_queue
        self._listeners: dict[str, OnStream] = {}
        self._lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        threading.Thread(target=self._poll_loop, daemon=True).start()

    def register(self, job_id: str, on_stream: OnStream) -> None:
        """job_id 의 이벤트를 on_stream 으로 받는다. on_stream 은 이벤트루프 스레드에서 불린다."""
        with self._lock:
            self._listeners[job_id] = on_stream

    def unregister(self, job_id: str) -> None:
        with self._lock:
            self._listeners.pop(job_id, None)

    def _poll_loop(self) -> None:
        while True:
            try:
                job_id, event = self._stream_queue.get(timeout=1.0)
            except queue_module.Empty:
                continue
            except Exception:  # noqa: BLE001
                logger.exception("스트리밍 큐 조회 중 오류")
                continue

            with self._lock:
                listener = self._listeners.get(job_id)
            if listener is not None:
                self._loop.call_soon_threadsafe(listener, event)
