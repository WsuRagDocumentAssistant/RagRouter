"""
LogHelper

로깅 설정 헬퍼.
"""
import logging
import sys
from datetime import datetime, timezone, timedelta

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

KST = timezone(timedelta(hours=9))


class KSTFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=KST)
        return dt.strftime(datefmt or DATE_FORMAT)


class LogHelper:
    @staticmethod
    def setup_logging(level: str = "INFO") -> None:
        """gateway.py 모듈 최상위에서 1회만 호출"""
        numeric_level = getattr(logging, level.upper(), logging.INFO)

        formatter = KSTFormatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)

        root = logging.getLogger()
        root.setLevel(numeric_level)
        root.handlers.clear()
        root.addHandler(handler)

        for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
            uv_logger = logging.getLogger(name)
            uv_logger.handlers.clear()
            uv_logger.addHandler(handler)
            uv_logger.setLevel(numeric_level)
            uv_logger.propagate = False