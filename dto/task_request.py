"""
TaskRequest DTO

클라이언트가 통신부(Gateway)로 보내는 요청 바디 모양.
"""
from typing import Any, Optional

from pydantic import BaseModel


class TaskRequest(BaseModel):
    task_type: str
    session_id: Optional[str] = None
    payload: dict[str, Any]
