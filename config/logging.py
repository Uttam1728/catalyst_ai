import inspect
from datetime import datetime

import logging
import structlog
from pytz import timezone
from structlog import contextvars
from structlog.stdlib import BoundLogger
from structlog_sentry import SentryProcessor

from utils.constants import UTC_TIME_ZONE


def get_current_time(time_zone: str = UTC_TIME_ZONE):
    return datetime.now(timezone(time_zone))


def add_timestamp(_, __, event_dict):
    """Add current datetime to log event."""
    event_dict["timestamp"] = get_current_time().isoformat()
    return event_dict


def get_logger(*args, **kwargs) -> BoundLogger:
    """Create structlog logger for logging."""
    structlog.configure(
        processors=[
            add_timestamp,
            contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            SentryProcessor(level=logging.ERROR),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ],
        cache_logger_on_first_use=True,
    )
    return structlog.get_logger(**kwargs)


def get_call_stack():
    stack = inspect.stack()
    call_stack = []
    for frame_info in stack[1:5]:  # Skip the current frame
        call_stack.append({
            "function": frame_info.function,
            "file": frame_info.filename,
            "line": frame_info.lineno
        })
    return call_stack


logger = get_logger()
