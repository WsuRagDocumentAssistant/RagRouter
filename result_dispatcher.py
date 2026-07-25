"""
결과 큐(브로커 건너편, TaskController 쪽에서 채워줌)를 백그라운드 스레드로
감시하다가, 해당 job_id로 대기 중인 asyncio.Future를 완료시켜주는 역할.

[단일 책임]
'결과가 도착했다는 사실을 이벤트루프에 안전하게 전달하는 것'만 책임진다.
HTTP 요청/응답에 대해서는 전혀 알지 못한다 (gateway.py의 책임).
"""
import asyncio
import threading
import logging
import queue as queue_module
from typing import Optional

logger = logging.getLogger("result_dispatcher")


class ResultDispatcher:
    def __init__(self, result_queue):
        self._result_queue = result_queue
        self._pending: dict[str, asyncio.Future] = {}
        self._lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def register(self, job_id: str) -> asyncio.Future:
        future = self._loop.create_future()
        with self._lock:
            self._pending[job_id] = future
        return future

    def unregister(self, job_id: str) -> None:
        with self._lock:
            self._pending.pop(job_id, None)

    def _poll_loop(self) -> None:
        while True:
            try:
                result = self._result_queue.get(timeout=1.0)
            except queue_module.Empty:
                continue
            except Exception:  # noqa: BLE001
                logger.exception("결과 큐 조회 중 오류")
                continue

            with self._lock:
                future = self._pending.get(result.job_id)
            if future is not None and not future.done():
                self._loop.call_soon_threadsafe(self._resolve, future, result)

    @staticmethod
    def _resolve(future: asyncio.Future, result) -> None:
        if not future.done():
            future.set_result(result)
