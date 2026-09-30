"""
공유 큐.

통신부(gateway.py)와 TaskController는 각자 다른 저장소(모듈)로 분리되어
있지만, 최종적으로는 둘을 import해서 엮어주는 "연결" 스크립트 하나가
함께 띄우는 구조로 확정되었다.

multiprocessing.Queue를 사용하므로, 같은 프로세스 안에서는 물론이고
연결 스크립트가 multiprocessing.Process로 띄운 자식 프로세스와도 큐가 공유된다.
단, 리눅스(fork 방식)에서만 모듈 레벨 큐가 자식에게 그대로 상속되며,
자식 프로세스는 gateway.run()보다 먼저 start()해야 한다.
"""
from multiprocessing import Queue


class SharedQueues:
    _task_queue: Queue = Queue()
    _result_queue: Queue = Queue()

    @classmethod
    def get_queues(cls):
        return cls._task_queue, cls._result_queue
