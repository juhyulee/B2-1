from __future__ import annotations

import csv
import functools
import logging
import sys
import time
from collections.abc import Callable
from typing import Any

from .errors import BudgetAppError

LOGGER = logging.getLogger("budget_app")


def log_command(func: Callable[..., int]) -> Callable[..., int]:
    """명령 시작·완료·실패를 budget_app 로거에 남긴다."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> int:
        LOGGER.info("command_started name=%s", func.__name__)
        try:
            result = func(*args, **kwargs)
        except Exception:
            LOGGER.exception("command_failed name=%s", func.__name__)
            raise
        LOGGER.info("command_finished name=%s exit_code=%s", func.__name__, result)
        return result

    return wrapper


def measure_execution_time(func: Callable[..., int]) -> Callable[..., int]:
    """명령 실행 시간을 밀리초 단위로 budget_app 로거에 남긴다."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> int:
        started_at = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            LOGGER.info(
                "command_timing name=%s elapsed_ms=%.3f",
                func.__name__,
                elapsed_ms,
            )

    return wrapper


def handle_cli_errors(func: Callable[..., int]) -> Callable[..., int]:
    """예상 가능한 오류를 스택 트레이스 없이 사용자 메시지로 바꾼다."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> int:
        try:
            return func(*args, **kwargs)
        except (BudgetAppError, OSError, csv.Error, ValueError) as exc:
            print(f"오류: {exc}", file=sys.stderr)
            return 1
        except (EOFError, KeyboardInterrupt):
            print("\n작업을 취소했습니다.", file=sys.stderr)
            return 130

    return wrapper
