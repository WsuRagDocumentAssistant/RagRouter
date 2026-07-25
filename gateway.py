"""
통신부(Gateway)

1. 요청이 들어오면, RequestHandler로 Task를 만들어 task_queue에 넣고 결과를 기다린다.
2. 결과(또는 타임아웃)가 정해지면, ResponseHandler로 TaskResponse를 만들어 응답한다.

.env 로딩, config.json 로딩, 로깅 설정은 여기(모듈 최상위)에서 1회만 수행한다.
- config.json: 구조적 기본값 (host/port/log_level 등)
- .env(os.environ): 비밀값/환경별 값. 있으면 config.json보다 우선한다.
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

import uvicorn
from fastapi import FastAPI

from dto.task_request import TaskRequest
from dto.task_response import TaskResponse
from helpers.config_helper import ConfigHelper
from helpers.log_helper import LogHelper
from helpers.request_helper import RequestHandler
from helpers.response_helper import ResponseHandler
from result_dispatcher import ResultDispatcher
from shared_queues import SharedQueues

config = ConfigHelper().load()

LogHelper.setup_logging(os.environ.get("LOG_LEVEL") or config.get("server", "log_level", default="INFO"))
logger = logging.getLogger("gateway")


class Gateway:
    TIMEOUT_SEC = 60.0  # 전체 task_type 공통 타임아웃

    def __init__(self):
        self.host = os.environ.get("HOST") or config.get("server", "host", default="0.0.0.0")
        self.port = int(os.environ.get("PORT") or config.get("server", "port", default=8000))

        self.request_handler = RequestHandler()
        self.response_handler = ResponseHandler()
        self.app = FastAPI(title="통신부 (Gateway)", lifespan=self._lifespan)
        self._register_routes()

    def run(self) -> None:
        """python gateway.py로 직접 실행할 때 사용. config.json의 server.host/port를 따른다."""
        uvicorn.run(self.app, host=self.host, port=self.port)

    @asynccontextmanager
    async def _lifespan(self, app: FastAPI):
        await self.on_startup()
        yield

    def _register_routes(self) -> None:
        self.app.add_api_route("/api/task", self.receive, methods=["POST"], response_model=TaskResponse)

    async def on_startup(self) -> None:
        # TaskController와 같은 프로세스 안에서 공유되는 큐를 가져온다.
        task_queue, result_queue = SharedQueues.get_queues()

        dispatcher = ResultDispatcher(result_queue)
        dispatcher.start(asyncio.get_event_loop())

        self.request_handler.configure(task_queue, dispatcher)
        logger.info("공유 큐 연결 완료")

    async def receive(self, req: TaskRequest) -> TaskResponse:
        job_id, result, timed_out = await self.request_handler.submit(req, self.TIMEOUT_SEC)
        response = self.response_handler.build(req.task_type, result, timed_out, self.TIMEOUT_SEC)

        if response.status == "success":
            logger.info("job_id=%s task_type=%s status=%s", job_id, req.task_type, response.status)
        else:
            logger.warning(
                "job_id=%s task_type=%s status=%s error=%s",
                job_id, req.task_type, response.status, response.error_message,
            )
        return response


gateway = Gateway()
app = gateway.app  # uvicorn gateway:app 이 참조하는 이름. 모듈 최상위에 있어야 하는 FastAPI 요구사항.

if __name__ == "__main__":
    gateway.run()
