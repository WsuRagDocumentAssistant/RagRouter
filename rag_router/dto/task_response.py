"""
TaskResponse DTO

통신부(Gateway)가 클라이언트에게 돌려주는 응답 바디 모양.
"""
from typing import Any, Literal, Optional

from pydantic import BaseModel


class TaskResponse(BaseModel):
    task_type: str
    status: Literal["success", "error", "timeout"]
    result: Optional[dict[str, Any] | list[Any]] = None  # FILE_LIST 등 일부 task_type은 배열 그 자체를 돌려줌
    error_message: Optional[str] = None
