from __future__ import annotations

import csv
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

from .errors import NotFoundError, ValidationError
from .models import (
    MonthlySummary,
    Transaction,
    normalize_tags,
    normalize_type,
    parse_date,
    parse_positive_amount,
    validate_month,
)
from .repository import DataStores

CSV_FIELDS = ["date", "type", "category", "amount", "memo", "tags"]


class BudgetService:
    def __init__(self, data_dir: Path) -> None:
        self.stores = DataStores(data_dir)

    def _validate_category(self, category: str) -> str:
        normalized = category.strip()
        if normalized not in self.stores.categories.list():
            raise ValidationError(
                f"등록되지 않은 카테고리입니다: {normalized}. "
                "'category list'로 목록을 확인하세요."
            )
        return normalized

    def add_transaction(
        self,
        *,
        date_value: str,
        type_value: str,
        category: str,
        amount_value: str | int,
        memo: str = "",
        tags: str | list[str] | None = None,
    ) -> Transaction:
        transaction = Transaction(
            id=self.stores.transactions.next_id(),
            type=normalize_type(type_value),
            date=parse_date(date_value).isoformat(),
            amount=parse_positive_amount(amount_value),
            category=self._validate_category(category),
            memo=memo.strip(),
            tags=normalize_tags(tags),
        )
        self.stores.transactions.add(transaction)
        return transaction

    def list_transactions(self, limit: int | None = None) -> Iterator[Transaction]:
        if limit is not None and limit <= 0:
            raise ValidationError("--limit은 0보다 커야 합니다.")
        count = 0
        for transaction in self.stores.transactions.iter_latest():
            if limit is not None and count >= limit:
                break
            yield transaction
            count += 1

    def search(
        self,
        *,
        from_date: str | None = None,
        to_date: str | None = None,
        category: str | None = None,
        type_value: str | None = None,
        query: str | None = None,
        tag: str | None = None,
    ) -> Iterator[Transaction]:
        start = parse_date(from_date).isoformat() if from_date else None
        end = parse_date(to_date).isoformat() if to_date else None
        if start and end and start > end:
            raise ValidationError("--from 날짜는 --to 날짜보다 늦을 수 없습니다.")
        normalized_type = normalize_type(type_value) if type_value else None
        lowered_query = query.lower() if query else None

        for transaction in self.stores.transactions.iter_latest():
            if start and transaction.date < start:
                continue
            if end and transaction.date > end:
                continue
            if category and transaction.category != category:
                continue
            if normalized_type and transaction.type != normalized_type:
                continue
            if lowered_query and lowered_query not in (
                f"{transaction.memo} {transaction.category}".lower()
            ):
                continue
            if tag and tag not in (transaction.tags or []):
                continue
            yield transaction

    def update_transaction(
        self,
        transaction_id: str,
        *,
        date_value: str | None = None,
        type_value: str | None = None,
        category: str | None = None,
        amount_value: str | int | None = None,
        memo: str | None = None,
        tags: str | list[str] | None = None,
        tags_supplied: bool = False,
    ) -> Transaction:
        old = self.stores.transactions.get(transaction_id)
        updated = Transaction(
            id=old.id,
            type=normalize_type(type_value) if type_value else old.type,
            date=parse_date(date_value).isoformat() if date_value else old.date,
            amount=(
                parse_positive_amount(amount_value)
                if amount_value is not None
                else old.amount
            ),
            category=(
                self._validate_category(category)
                if category is not None
                else old.category
            ),
            memo=memo.strip() if memo is not None else old.memo,
            tags=normalize_tags(tags) if tags_supplied else old.tags,
        )
        self.stores.transactions.update(updated)
        return updated

    def delete_transaction(self, transaction_id: str) -> None:
        self.stores.transactions.delete(transaction_id)

    def monthly_summary(self, month: str, top: int) -> MonthlySummary:
        validate_month(month)
        if top <= 0:
            raise ValidationError("--top은 0보다 커야 합니다.")
        income = 0
        expense = 0
        categories: Counter[str] = Counter()
        for transaction in self.stores.transactions.iter_all():
            if not transaction.date.startswith(month):
                continue
            if transaction.type == "income":
                income += transaction.amount
            else:
                expense += transaction.amount
                categories[transaction.category] += transaction.amount
        return MonthlySummary(
            month=month,
            income=income,
            expense=expense,
            balance=income - expense,
            budget=self.stores.budgets.get(month),
            category_expenses=categories.most_common(top),
        )

    def set_budget(self, month: str, amount_value: str | int) -> int:
        validate_month(month)
        amount = parse_positive_amount(amount_value)
        self.stores.budgets.set(month, amount)
        return amount

    def get_budget(self, month: str) -> int | None:
        validate_month(month)
        return self.stores.budgets.get(month)

    def list_budgets(self) -> list[tuple[str, int]]:
        return self.stores.budgets.list()

    def add_category(self, name: str) -> None:
        normalized = name.strip()
        if not normalized:
            raise ValidationError("카테고리 이름은 비워 둘 수 없습니다.")
        if normalized in self.stores.categories.list():
            raise ValidationError(f"이미 존재하는 카테고리입니다: {normalized}")
        self.stores.categories.add(normalized)

    def list_categories(self) -> list[str]:
        return self.stores.categories.list()

    def remove_category(self, name: str) -> None:
        normalized = name.strip()
        if normalized not in self.stores.categories.list():
            raise NotFoundError(f"카테고리를 찾을 수 없습니다: {normalized}")
        if self.stores.transactions.is_category_used(normalized):
            raise ValidationError(
                f"거래에서 사용 중인 카테고리는 삭제할 수 없습니다: {normalized}"
            )
        self.stores.categories.remove(normalized)

    def import_csv(
        self, source: Path, *, atomic: bool = False
    ) -> tuple[int, int, bool]:
        if not source.exists():
            raise ValidationError(f"CSV 파일을 찾을 수 없습니다: {source}")
        valid: list[Transaction] = []
        failed = 0
        next_number = int(
            self.stores.transactions.next_id().removeprefix("TX-")
        )
        with source.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            if not reader.fieldnames or any(
                field not in reader.fieldnames for field in CSV_FIELDS
            ):
                raise ValidationError(
                    "CSV 헤더가 올바르지 않습니다. 필요한 열: "
                    + ", ".join(CSV_FIELDS)
                )
            categories = set(self.stores.categories.list())
            for row in reader:
                try:
                    category = (row.get("category") or "").strip()
                    if category not in categories:
                        raise ValidationError(
                            f"등록되지 않은 카테고리입니다: {category}"
                        )
                    valid.append(
                        Transaction(
                            id=f"TX-{next_number:06d}",
                            date=(row.get("date") or "").strip(),
                            type=(row.get("type") or "").strip(),
                            category=category,
                            amount=parse_positive_amount(row.get("amount") or ""),
                            memo=(row.get("memo") or "").strip(),
                            tags=normalize_tags(
                                (row.get("tags") or "").replace("|", ",")
                            ),
                        )
                    )
                    next_number += 1
                except (ValidationError, KeyError, TypeError, ValueError):
                    failed += 1
        if atomic and failed:
            return 0, failed, True
        if atomic:
            imported = self.stores.transactions.add_many_atomic(iter(valid))
        else:
            imported = self.stores.transactions.add_many(iter(valid))
        return imported, failed, False

    def export_csv(
        self,
        output: Path,
        *,
        month: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> int:
        if month:
            validate_month(month)
            start = f"{month}-01"
            if month.endswith("-12"):
                end = f"{int(month[:4]) + 1}-01-01"
            else:
                year, month_number = map(int, month.split("-"))
                end = f"{year:04d}-{month_number + 1:02d}-01"
            transactions = (
                transaction
                for transaction in self.stores.transactions.iter_latest()
                if start <= transaction.date < end
            )
        else:
            transactions = self.search(from_date=from_date, to_date=to_date)

        output.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with output.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for transaction in transactions:
                writer.writerow(
                    {
                        "date": transaction.date,
                        "type": transaction.type,
                        "category": transaction.category,
                        "amount": transaction.amount,
                        "memo": transaction.memo,
                        "tags": "|".join(transaction.tags or []),
                    }
                )
                count += 1
        return count
