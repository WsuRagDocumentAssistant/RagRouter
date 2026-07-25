"""
Task 구현체

interface/task_interface.py 의 TaskInterface를 상속받아 실제 큐에 오가는
요청 데이터 모양을 구현한다.
"""
from typing import Any, Optional

from interface.task_interface import TaskInterface


class Task(TaskInterface):
    """통신부 -> TaskController 로 넘어가는 요청 단위"""

    __slots__ = ("_job_id", "_task_type", "_session_id", "_payload")

    def __init__(self, job_id: str, task_type: str, session_id: Optional[str], payload: dict[str, Any]):
        self._job_id = job_id
        self._task_type = task_type
        self._session_id = session_id
        self._payload = payload

    @property
    def job_id(self) -> str:
        return self._job_id

    @property
    def task_type(self) -> str:
        return self._task_type

    @property
    def session_id(self) -> Optional[str]:
        return self._session_id

    @property
    def payload(self) -> dict[str, Any]:
        return self._payload
