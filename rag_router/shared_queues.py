"""
공유 큐.

설계상 통신 흐름은 다음과 같다.

    Client → Router → TaskController → TaskExecutor → 결과 큐 → Router

Router가 넣는 큐(task_queue)는 TaskController의 입력 큐이고, Router가 꺼내는
큐(result_queue)는 TaskExecutor의 결과 큐다. 연결 스크립트는 bind()로 두 큐를
직접 꽂아준다 — 그 사이를 이어주는 별도 큐나 중계 스레드를 두지 않는다.

bind()를 부르지 않으면 모듈 레벨 기본 큐를 쓴다(mock_taskcontroller 등 단독 실행용).
기본 큐는 multiprocessing.Queue라 같은 프로세스 안에서는 물론, 리눅스(fork 방식)에서
gateway.run()보다 먼저 start()한 자식 프로세스와도 공유된다.
"""
from multiprocessing import Queue


class SharedQueues:
    _task_queue: Queue = Queue()
    _result_queue: Queue = Queue()

    @classmethod
    def bind(cls, task_queue, result_queue) -> None:
        """TaskController 입력 큐와 TaskExecutor 결과 큐를 꽂는다. gateway.run() 전에 불러야 한다."""
        cls._task_queue, cls._result_queue = task_queue, result_queue

    @classmethod
    def get_queues(cls):
        return cls._task_queue, cls._result_queue
