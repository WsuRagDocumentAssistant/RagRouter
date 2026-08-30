"""
TaskResult 구현체

interface/task_result_interface.py 의 TaskResultInterface를 상속받아 실제
큐에 오가는 결과 데이터 모양을 구현한다.
"""
from typing import Any, Optional

from rag_router.interface.task_result_interface import TaskResultInterface


class TaskResult(TaskResultInterface):
    """TaskController/TaskExecutor -> 통신부 로 돌아오는 결과 단위"""

    __slots__ = ("_job_id", "_success", "_data", "_error")

    def __init__(
        self,
        job_id: str,
        success: bool,
        data: Optional[dict[str, Any] | list[Any]] = None,
        error: Optional[str] = None,
    ):
        self._job_id = job_id
        self._success = success
        self._data = data
        self._error = error

    @property
    def job_id(self) -> str:
        return self._job_id

    @property
    def success(self) -> bool:
        return self._success

    @property
    def data(self) -> Optional[dict[str, Any] | list[Any]]:
        return self._data

    @property
    def error(self) -> Optional[str]:
        return self._error
