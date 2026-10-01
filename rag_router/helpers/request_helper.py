"""
요청 헬퍼(Request Helper)

- RequestHandler: TaskRequest를 Task로 변환해 큐에 적재하고, 결과가 올 때까지 대기하는 책임
- TaskRequest DTO는 dto/task_request.py 로 분리되어 있다.
"""
import uuid
import asyncio
from typing import Any, Callable, Optional

from rag_router.task.task import Task
from rag_router.task.task_result import TaskResult
from rag_router.dto.task_request import TaskRequest
from rag_router.result_dispatcher import ResultDispatcher

Encode = Callable[[Task], Any]


def _same(task: Task) -> Task:
    return task


class RequestHandler:
    """TaskRequest -> Task 변환, 큐 적재, 결과 대기를 담당한다."""

    def __init__(self, task_queue=None, dispatcher: Optional[ResultDispatcher] = None, encode: Optional[Encode] = None):
        self._task_queue = task_queue
        self._dispatcher = dispatcher
        self._encode = encode or _same

    def configure(self, task_queue, dispatcher: ResultDispatcher, encode: Optional[Encode] = None) -> None:
        """
        공유 큐(task_queue)와 결과 대기 장치(dispatcher)를 나중에 주입한다.
        encode는 Task를 task_queue가 받는 모양으로 바꾼다. ValueError를 던지면 큐에 넣지 않고
        그 메시지로 바로 실패 응답한다 (예: 등록되지 않은 task_type).
        """
        self._task_queue = task_queue
        self._dispatcher = dispatcher
        self._encode = encode or _same

    async def submit(
        self, req: TaskRequest, timeout_sec: float, token: Optional[str] = None
    ) -> tuple[str, Optional[TaskResult], bool]:
        """
        TaskRequest를 Task로 변환해 큐에 넣고, 결과가 도착할 때까지 대기한다.
        token은 HTTP Authorization 헤더(또는 WebSocket 메시지)에서 추출되어 별도로 전달된다.

        반환값: (job_id, result 또는 None(타임아웃 시), timed_out 여부)
        """
        job_id = str(uuid.uuid4())
        task = Task(
            job_id=job_id,
            task_type=req.task_type,
            session_id=req.session_id,
            payload=req.payload,
            token=token,
        )

        try:
            item = self._encode(task)
        except ValueError as e:
            return job_id, TaskResult(job_id, False, error=str(e)), False

        future = self._dispatcher.register(job_id)
        self._task_queue.put(item)

        try:
            result = await asyncio.wait_for(future, timeout=timeout_sec)
            return job_id, result, False
        except asyncio.TimeoutError:
            return job_id, None, True
        finally:
            self._dispatcher.unregister(job_id)
