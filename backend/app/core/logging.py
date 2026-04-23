import logging
import sys

from pythonjsonlogger import json as jsonlogger


_CONTEXT_FIELDS = ("contractor_id", "session_id", "event_type")


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for field in _CONTEXT_FIELDS:
            if not hasattr(record, field):
                setattr(record, field, None)
        return True


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s "
            "%(contractor_id)s %(session_id)s %(event_type)s",
            rename_fields={"asctime": "ts", "levelname": "level", "name": "logger"},
        )
    )
    handler.addFilter(ContextFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
