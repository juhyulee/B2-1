from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from .errors import ValidationError

VALID_TYPES = {"income", "expense"}


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"날짜는 YYYY-MM-DD 형식이어야 합니다: {value}") from exc


def validate_month(value: str) -> str:
    try:
        parsed = date.fromisoformat(f"{value}-01")
    except ValueError as exc:
        raise ValidationError(f"월은 YYYY-MM 형식이어야 합니다: {value}") from exc
    if parsed.strftime("%Y-%m") != value:
        raise ValidationError(f"월은 YYYY-MM 형식이어야 합니다: {value}")
    return value


def parse_positive_amount(value: str | int) -> int:
    try:
        amount = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("금액은 0보다 큰 정수여야 합니다.") from exc
    if amount <= 0:
        raise ValidationError("금액은 0보다 큰 정수여야 합니다.")
    return amount


def normalize_type(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in VALID_TYPES:
        raise ValidationError("유형은 income 또는 expense여야 합니다.")
    return normalized


def normalize_tags(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    raw = value if isinstance(value, list) else value.split(",")
    result: list[str] = []
    for tag in raw:
        normalized = str(tag).strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


@dataclass(frozen=True)
class Transaction:
    id: str
    type: str
    date: str
    amount: int
    category: str
    memo: str = ""
    tags: list[str] | None = None

    def __post_init__(self) -> None:
        parse_date(self.date)
        object.__setattr__(self, "type", normalize_type(self.type))
        object.__setattr__(self, "amount", parse_positive_amount(self.amount))
        if not self.category.strip():
            raise ValidationError("카테고리는 비워 둘 수 없습니다.")
        object.__setattr__(self, "category", self.category.strip())
        object.__setattr__(self, "tags", normalize_tags(self.tags))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Transaction":
        return cls(
            id=str(data["id"]),
            type=str(data["type"]),
            date=str(data["date"]),
            amount=int(data["amount"]),
            category=str(data["category"]),
            memo=str(data.get("memo", "")),
            tags=normalize_tags(data.get("tags")),
        )


@dataclass(frozen=True)
class MonthlySummary:
    month: str
    income: int
    expense: int
    balance: int
    budget: int | None
    category_expenses: list[tuple[str, int]]
