from __future__ import annotations

import csv
import functools
import sys
from collections.abc import Callable
from typing import Any

from .errors import BudgetAppError


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
