import json
import os
import sys
from typing import Any, Literal

LogLevel = Literal["debug", "info", "warn", "error", "silent"]

ORDER: dict[str, int] = {"debug": 10, "info": 20, "warn": 30, "error": 40, "silent": 100}


# Read straight from the environment rather than from HarnessConfig, so logging
# works before (and while) the config is loaded.
def _emit(level: LogLevel, message: str, fields: dict[str, Any]) -> None:
    configured = os.environ.get("LOG_LEVEL", "").strip().lower()
    threshold = ORDER[configured] if configured in ORDER else ORDER["info"]
    if ORDER[level] < threshold:
        return
    sys.stderr.write(json.dumps({"level": level, "message": message, **fields}) + "\n")


class Log:
    """
    One JSON object per line on stderr, so diagnostics never mix into the report
    on stdout. `LOG_LEVEL` sets the threshold and defaults to `info`.

    Fields are for identifiers, counts and error messages. Scenario messages,
    candidate responses and rubrics are customer conversations: nothing here
    redacts them, and CI retains whatever a run prints.
    """

    def debug(self, message: str, **fields: Any) -> None:
        _emit("debug", message, fields)

    def info(self, message: str, **fields: Any) -> None:
        _emit("info", message, fields)

    def warn(self, message: str, **fields: Any) -> None:
        _emit("warn", message, fields)

    def error(self, message: str, **fields: Any) -> None:
        _emit("error", message, fields)


log = Log()
