import logging
from typing import NewType, Optional

from src.utils.stack import current_function_name


LogLevel = NewType("LogLevel", int)


def parse_log_level(level: str) -> LogLevel:
    return logging._nameToLevel[level.upper()]


def get_function_logger(
    parent_logger: Optional[logging.Logger] = None,
) -> logging.Logger:
    parent_logger = parent_logger or logging.getLogger()
    function_name = current_function_name(depth=2)
    return parent_logger.getChild(function_name)
