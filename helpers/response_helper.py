"""
응답 헬퍼(Response Helper)

- ResponseHandler: TaskResult(또는 타임아웃 상태)를 TaskResponse로 변환하는 책임
- TaskResponse DTO는 dto/task_response.py 로 분리되어 있다.
"""
from typing import Optional

from task.task_result import TaskResult
from dto.task_response import TaskResponse


class ResponseHandler:
    """result/timed_out 상태를 보고 TaskResponse를 만드는 책임."""

    def __init__(self, timeout_message_template: str = "{timeout_sec}초 내에 결과가 준비되지 않았습니다."):
        self._timeout_message_template = timeout_message_template

    def build(
        self,
        task_type: str,
        result: Optional[TaskResult],
        timed_out: bool,
        timeout_sec: float,
    ) -> TaskResponse:
        if timed_out:
            return TaskResponse(
                task_type=task_type,
                status="timeout",
                error_message=self._timeout_message_template.format(timeout_sec=timeout_sec),
            )
        if result.success:
            return TaskResponse(task_type=task_type, status="success", result=result.data)
        return TaskResponse(task_type=task_type, status="error", error_message=result.error)
