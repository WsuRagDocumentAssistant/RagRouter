"""
WebSocket 메시지 DTO

/api/ws 로 오가는 메시지 모양. HTTP 바디(TaskRequest/TaskResponse)에 두 필드만 더한다.
- id: 클라이언트가 붙이는 요청 번호. 응답에 그대로 돌려줘서 한 연결 안에서 여러 요청이
  동시에 오가도 짝을 맞출 수 있게 한다.
- token: 브라우저 WebSocket은 Authorization 헤더를 실을 수 없어서 메시지에 싣는다.
"""
from typing import Any, Literal, Optional

from pydantic import BaseModel

from rag_router.dto.task_request import TaskRequest
from rag_router.dto.task_response import TaskResponse


class WsRequest(TaskRequest):
    id: str
    token: Optional[str] = None


class WsResponse(TaskResponse):
    id: Optional[str] = None


class WsStream(BaseModel):
    """작업이 도는 동안 보내는 중간 메시지. 한 요청에 여러 번 오고, 마지막에 WsResponse 가 온다.

    event 는 work 이 정한 모양 그대로다. 예:
      {"type": "stage", "stage": "draft", "message": "초안 작성 중"}
      {"type": "delta", "provider": "gpt", "text": "생성된 조각"}
    status 가 "stream" 이라 클라이언트는 최종 응답(success/error/timeout)과 구분한다.
    """
    id: str
    task_type: str
    status: Literal["stream"] = "stream"
    event: dict[str, Any]
