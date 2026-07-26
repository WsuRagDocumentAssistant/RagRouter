"""
[테스트 전용 목업입니다. 실제 배포 대상이 아닙니다]

TaskController/TaskExecutor는 다른 저장소(모듈)로 분리되어 개발될 예정이므로,
통신부가 독립적으로 잘 동작하는지 확인하기 위한 최소 시뮬레이터.

task_queue에서 Task를 꺼내 그대로 echo 형태로 result_queue에 넣어준다.
실제 TaskController는 이 자리에서 task_type을 보고 분기 후 실제 로직을 실행하면 된다.

[중요] 이 목업은 gateway.py와 같은 프로세스 안에서 실행되어야
shared_queues.SharedQueues가 실제로 같은 큐 객체를 공유한다.
"""
import queue as queue_module

from rag_router.task.task_result import TaskResult
from rag_router.shared_queues import SharedQueues


class MockTaskController:
    def __init__(self):
        self._task_queue = None
        self._result_queue = None

    def connect(self) -> None:
        self._task_queue, self._result_queue = SharedQueues.get_queues()

    def run(self) -> None:
        self.connect()
        print("[mock_taskcontroller] 대기 중...")
        while True:
            task = self._receive_task()
            if task is None:
                continue
            print(f"[mock_taskcontroller] 수신: job_id={task.job_id}, task_type={task.task_type}")
            self._result_queue.put(self._build_echo_result(task))

    def _receive_task(self):
        try:
            return self._task_queue.get(timeout=1.0)
        except queue_module.Empty:
            return None

    @staticmethod
    def _build_echo_result(task) -> TaskResult:
        return TaskResult(
            job_id=task.job_id,
            success=True,
            data={"echo": task.payload, "handled_by": "mock_taskcontroller"},
        )


if __name__ == "__main__":
    MockTaskController().run()
