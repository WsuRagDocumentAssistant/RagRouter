"""
통신부(Gateway)

1. 요청이 들어오면, RequestHandler로 Task를 만들어 task_queue에 넣고 결과를 기다린다.
2. 결과(또는 타임아웃)가 정해지면, ResponseHandler로 TaskResponse를 만들어 응답한다.

통로는 두 가지이고 처리는 같다.
- WebSocket /api/ws : 기본 통로. 연결 하나로 여러 요청을 동시에 보내고, 응답은 끝나는 순서대로 온다.
  작업이 도는 동안 중간 메시지(WsStream: 생성 중인 답변 조각, 진행 단계)도 같은 id로 보낸다.
- HTTP POST /api/task : 기존 클라이언트·디버깅(curl)용으로 남겨둔다.

.env 로딩, config.json 로딩, 로깅 설정은 여기(모듈 최상위)에서 1회만 수행한다.
- config.json: 구조적 기본값 (host/port/log_level 등)
- .env(os.environ): 비밀값/환경별 값. 있으면 config.json보다 우선한다.
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

import uvicorn
from fastapi import FastAPI, Header, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from rag_router.dto.task_request import TaskRequest
from rag_router.dto.task_response import TaskResponse
from rag_router.dto.ws_message import WsRequest, WsResponse, WsStream
from rag_router.helpers.config_helper import ConfigHelper
from rag_router.helpers.log_helper import LogHelper
from rag_router.helpers.request_helper import Encode, RequestHandler
from rag_router.helpers.response_helper import ResponseHandler
from rag_router.result_dispatcher import Decode, ResultDispatcher
from rag_router.shared_queues import SharedQueues
from rag_router.stream_dispatcher import StreamDispatcher

config = ConfigHelper().load()

LogHelper.setup_logging(os.environ.get("LOG_LEVEL") or config.get("server", "log_level", default="INFO"))
logger = logging.getLogger("gateway")


def _bearer(authorization: Optional[str]) -> Optional[str]:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[len("bearer "):].strip()
    return None


class Gateway:
    TIMEOUT_SEC = 60.0  # 전체 task_type 공통 타임아웃

    def __init__(self):
        self.host = os.environ.get("HOST") or config.get("server", "host", default="0.0.0.0")
        self.port = int(os.environ.get("PORT") or config.get("server", "port", default=8000))
        # 파일 업로드가 base64로 메시지 하나에 실려 오므로 uvicorn 기본값(16MB)보다 크게 둔다.
        self.ws_max_size = int(config.get("server", "ws_max_size", default=16 * 1024 * 1024))

        self._encode: Optional[Encode] = None
        self._decode: Optional[Decode] = None
        self._stream_queue = None

        self.request_handler = RequestHandler()
        self.response_handler = ResponseHandler()
        self.app = FastAPI(title="통신부 (Gateway)", lifespan=self._lifespan)
        self._register_cors()
        self._register_routes()

    def _register_cors(self) -> None:
        allowed_origins = config.get("cors", "allowed_origins", default=["https://rag.wsu.ac.kr"])
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def connect(
        self, task_queue, result_queue, *, encode: Optional[Encode] = None, decode: Optional[Decode] = None,
        stream_queue=None,
    ) -> None:
        """
        TaskController 입력 큐와 TaskExecutor 결과 큐를 직접 연결한다. run() 전에 불러야 한다.
        - encode: Task -> task_queue에 넣을 값. ValueError면 큐에 넣지 않고 바로 실패 응답
        - decode: result_queue에서 꺼낸 값 -> TaskResult. None이면 버린다
        - stream_queue: TaskExecutor가 작업 중에 (job_id, event)를 넣는 큐. 주면 WebSocket
          요청에 그 이벤트를 WsStream으로 흘려보낸다. 없으면 최종 응답만 보낸다
        """
        SharedQueues.bind(task_queue, result_queue)
        self._encode, self._decode = encode, decode
        self._stream_queue = stream_queue

    def run(self) -> None:
        """rag-router 콘솔 스크립트/직접 실행에서 사용. config.json의 server.host/port를 따른다."""
        uvicorn.run(self.app, host=self.host, port=self.port, ws_max_size=self.ws_max_size)

    @asynccontextmanager
    async def _lifespan(self, app: FastAPI):
        await self.on_startup()
        yield

    def _register_routes(self) -> None:
        self.app.add_api_route("/api/task", self.receive, methods=["POST"], response_model=TaskResponse)
        self.app.add_api_websocket_route("/api/ws", self.stream)

    async def on_startup(self) -> None:
        task_queue, result_queue = SharedQueues.get_queues()

        loop = asyncio.get_running_loop()
        dispatcher = ResultDispatcher(result_queue, self._decode)
        dispatcher.start(loop)

        streams = None
        if self._stream_queue is not None:
            streams = StreamDispatcher(self._stream_queue)
            streams.start(loop)

        self.request_handler.configure(task_queue, dispatcher, self._encode, streams)
        logger.info("큐 연결 완료 (스트리밍 %s)", "사용" if streams else "안 씀")

    async def _process(self, req: TaskRequest, token: Optional[str], on_stream=None) -> TaskResponse:
        job_id, result, timed_out = await self.request_handler.submit(
            req, self.TIMEOUT_SEC, token=token, on_stream=on_stream
        )
        response = self.response_handler.build(req.task_type, result, timed_out, self.TIMEOUT_SEC)

        if response.status == "success":
            logger.info("job_id=%s task_type=%s status=%s", job_id, req.task_type, response.status)
        else:
            logger.warning(
                "job_id=%s task_type=%s status=%s error=%s",
                job_id, req.task_type, response.status, response.error_message,
            )
        return response

    async def receive(self, req: TaskRequest, authorization: Optional[str] = Header(None)) -> TaskResponse:
        return await self._process(req, _bearer(authorization))

    async def stream(self, ws: WebSocket) -> None:
        """
        메시지 하나가 요청 하나다. 요청마다 작업을 따로 띄워서, 오래 걸리는 질의가 뒤의 요청을
        막지 않는다. 연결이 끊기면 아직 기다리던 요청은 취소한다(결과는 dispatcher가 버린다).
        """
        await ws.accept()
        send_lock = asyncio.Lock()   # 여러 작업이 동시에 보내도 프레임이 섞이지 않게
        running: set[asyncio.Task] = set()

        async def send(response: WsResponse) -> None:
            async with send_lock:
                await ws.send_text(response.model_dump_json())

        async def reply(req: WsRequest) -> None:
            # 중간 이벤트는 이벤트루프 스레드에서 불린다. 보내기는 async라 작업으로 띄우고,
            # send_lock이 먼저 온 순서대로 내보낸다. 최종 응답 뒤에 늦게 도착한 조각은
            # 클라이언트가 버린다(이미 끝난 요청).
            async def push(event: dict) -> None:
                try:
                    await send(WsStream(id=req.id, task_type=req.task_type, event=event))
                except Exception:  # noqa: BLE001 — 연결이 끊겼으면 조각은 버린다. 최종 응답 쪽이 정리한다
                    pass

            def on_stream(event: dict) -> None:
                job = asyncio.create_task(push(event))
                running.add(job)
                job.add_done_callback(running.discard)

            response = await self._process(req, req.token, on_stream)
            await send(WsResponse(id=req.id, **response.model_dump()))

        try:
            while True:
                text = await ws.receive_text()
                try:
                    req = WsRequest.model_validate_json(text)
                except ValidationError as e:
                    await send(WsResponse(task_type="", status="error", error_message=f"잘못된 요청 형식입니다: {e.errors()[0]['msg']}"))
                    continue
                job = asyncio.create_task(reply(req))
                running.add(job)
                job.add_done_callback(running.discard)
        except WebSocketDisconnect:
            pass
        finally:
            for job in running:
                job.cancel()


gateway = Gateway()
app = gateway.app  # uvicorn rag_router.gateway:app 이 참조하는 이름. 모듈 최상위에 있어야 하는 FastAPI 요구사항.


def main() -> None:
    """pyproject.toml의 [project.scripts] rag-router 엔트리 포인트."""
    gateway.run()


if __name__ == "__main__":
    main()
