"""
설정 헬퍼(Config Helper)

config.json(비밀값이 아닌 구조적 기본값)을 읽어 들이는 역할만 담당한다.
비밀값/환경별로 달라지는 값은 .env(os.environ)에서 따로 읽어서, 필요한 곳에서
config.json 값보다 우선시키면 된다.
"""
import json
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


class ConfigHelper:
    def __init__(self, config_path: Path = CONFIG_PATH):
        self._config_path = config_path
        self._config: dict[str, Any] = {}

    def load(self) -> "ConfigHelper":
        with open(self._config_path, "r", encoding="utf-8") as f:
            self._config = json.load(f)
        return self

    def get(self, *keys: str, default: Any = None) -> Any:
        """
        중첩 키를 순서대로 따라가며 값을 찾는다.
        예: get("server", "port", default=8000)
        """
        value = self._config
        for key in keys:
            if not isinstance(value, dict) or key not in value:
                return default
            value = value[key]
        return value
