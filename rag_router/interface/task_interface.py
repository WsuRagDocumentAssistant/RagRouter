"""
TaskInterface

통신부(Communication) -> TaskController/TaskExecutor 로 넘어가는 요청 단위가
반드시 가져야 하는 필드를 정의하는 인터페이스.
"""
from abc import ABC, abstractmethod
from typing import Any, Optional


class TaskInterface(ABC):
    @property
    @abstractmethod
    def job_id(self) -> str: ...

    @property
    @abstractmethod
    def task_type(self) -> str: ...

    @property
    @abstractmethod
    def session_id(self) -> Optional[str]: ...

    @property
    @abstractmethod
    def payload(self) -> dict[str, Any]: ...
