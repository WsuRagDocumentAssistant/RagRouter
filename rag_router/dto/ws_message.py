"""
WebSocket 메시지 DTO

/api/ws 로 오가는 메시지 모양. HTTP 바디(TaskRequest/TaskResponse)에 두 필드만 더한다.
- id: 클라이언트가 붙이는 요청 번호. 응답에 그대로 돌려줘서 한 연결 안에서 여러 요청이
  동시에 오가도 짝을 맞출 수 있게 한다.
- token: 브라우저 WebSocket은 Authorization 헤더를 실을 수 없어서 메시지에 싣는다.
"""
from typing import Optional

from rag_router.dto.task_request import TaskRequest
from rag_router.dto.task_response import TaskResponse


class WsRequest(TaskRequest):
    id: str
    token: Optional[str] = None


class WsResponse(TaskResponse):
    id: Optional[str] = None
