"""
공유 큐.

통신부(gateway.py)와 TaskController는 각자 다른 저장소(모듈)로 분리되어
있지만, 최종적으로는 둘을 import해서 엮어주는 "연결" 스크립트 하나가
같은 파이썬 프로세스 안에서 함께 띄우는 구조로 확정되었다.

같은 프로세스 안에서는 이 모듈을 import하는 모든 곳이 동일한
task_queue/result_queue 객체를 얻게 되므로, 별도의 브로커 프로세스
(구 broker.py) 없이도 큐 공유가 가능하다.
"""
import queue


class SharedQueues:
    _task_queue: "queue.Queue" = queue.Queue()
    _result_queue: "queue.Queue" = queue.Queue()

    @classmethod
    def get_queues(cls):
        return cls._task_queue, cls._result_queue
