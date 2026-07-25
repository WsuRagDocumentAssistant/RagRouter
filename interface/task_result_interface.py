"""
TaskResultInterface

TaskController/TaskExecutor -> 통신부 로 돌아오는 결과 단위가 반드시 가져야
하는 필드를 정의하는 인터페이스.

[중요] TaskController 쪽 구현체는 반드시 요청받은 Task.job_id와 동일한 값을
job_id에 넣어서 결과 큐에 넣어야 한다. 통신부는 이 job_id로만 어떤 요청에
대한 응답인지 매칭한다.
"""
from abc import ABC, abstractmethod
from typing import Any, Optional


class TaskResultInterface(ABC):
    @property
    @abstractmethod
    def job_id(self) -> str: ...

    @property
    @abstractmethod
    def success(self) -> bool: ...

    @property
    @abstractmethod
    def data(self) -> Optional[dict[str, Any]]: ...

    @property
    @abstractmethod
    def error(self) -> Optional[str]: ...
