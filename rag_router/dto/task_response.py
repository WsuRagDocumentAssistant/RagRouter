"""
TaskResponse DTO

통신부(Gateway)가 클라이언트에게 돌려주는 응답 바디 모양.
"""
from typing import Any, Literal, Optional

from pydantic import BaseModel


class TaskResponse(BaseModel):
    task_type: str
    status: Literal["success", "error", "timeout"]
    result: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
