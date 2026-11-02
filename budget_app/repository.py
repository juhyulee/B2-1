from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from .errors import NotFoundError
from .models import Transaction

DEFAULT_CATEGORIES = [
    "식비",
    "교통",
    "주거",
    "급여",
    "공과금",
    "건강",
    "기타",
]


def iter_lines_reverse(path: Path, block_size: int = 8192) -> Iterator[str]:
    """파일을 끝에서부터 블록 단위로 읽어 한 줄씩 반환한다."""
    with path.open("rb") as file:
        file.seek(0, os.SEEK_END)
        position = file.tell()
        buffer = b""
        while position > 0:
            read_size = min(block_size, position)
            position -= read_size
            file.seek(position)
            buffer = file.read(read_size) + buffer
            lines = buffer.split(b"\n")
            buffer = lines[0]
            for line in reversed(lines[1:]):
                if line.strip():
                    yield line.decode("utf-8")
        if buffer.strip():
            yield buffer.decode("utf-8")


class JsonlStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def ensure_exists(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        created = not self.path.exists()
        self.path.touch(exist_ok=True)
        return created

    def append(self, row: dict[str, Any]) -> None:
        self.ensure_exists()
        with self.path.open("a", encoding="utf-8", newline="\n") as file:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
            file.flush()
            os.fsync(file.fileno())

    def append_many(self, rows: Iterator[dict[str, Any]]) -> int:
        self.ensure_exists()
        count = 0
        with self.path.open("a", encoding="utf-8", newline="\n") as file:
            for row in rows:
                file.write(json.dumps(row, ensure_ascii=False) + "\n")
                count += 1
            file.flush()
            os.fsync(file.fileno())
        return count

    def iter_forward(self) -> Iterator[dict[str, Any]]:
        self.ensure_exists()
        with self.path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                if line.strip():
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise OSError(
                            f"{self.path.name} {line_number}번째 줄의 JSON 형식이 잘못되었습니다."
                        ) from exc

    def iter_reverse(self) -> Iterator[dict[str, Any]]:
        self.ensure_exists()
        for line in iter_lines_reverse(self.path):
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise OSError(f"{self.path.name} 파일의 JSON 형식이 잘못되었습니다.") from exc

    def replace_rows(self, rows: list[dict[str, Any]]) -> None:
        self.ensure_exists()
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file:
                for row in rows:
                    file.write(json.dumps(row, ensure_ascii=False) + "\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp_name, self.path)
        except Exception:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise


class TransactionRepository:
    def __init__(self, path: Path) -> None:
        self.store = JsonlStore(path)
        self.store.ensure_exists()

    def next_id(self) -> str:
        maximum = 0
        for transaction in self.iter_all():
            try:
                maximum = max(maximum, int(transaction.id.removeprefix("TX-")))
            except ValueError:
                continue
        return f"TX-{maximum + 1:06d}"

    def add(self, transaction: Transaction) -> None:
        self.store.append(transaction.to_dict())

    def add_many(self, transactions: Iterator[Transaction]) -> int:
        return self.store.append_many(t.to_dict() for t in transactions)

    def add_many_atomic(self, transactions: Iterator[Transaction]) -> int:
        """기존 거래와 신규 배치를 임시 파일에 쓴 뒤 한 번에 교체한다."""
        path = self.store.path
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        count = 0
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as target:
                for transaction in self.iter_all():
                    target.write(
                        json.dumps(transaction.to_dict(), ensure_ascii=False) + "\n"
                    )
                for transaction in transactions:
                    target.write(
                        json.dumps(transaction.to_dict(), ensure_ascii=False) + "\n"
                    )
                    count += 1
                target.flush()
                os.fsync(target.fileno())
            os.replace(temp_name, path)
            return count
        except Exception:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise

    def iter_all(self) -> Iterator[Transaction]:
        for row in self.store.iter_forward():
            yield Transaction.from_dict(row)

    def iter_latest(self) -> Iterator[Transaction]:
        for row in self.store.iter_reverse():
            yield Transaction.from_dict(row)

    def get(self, transaction_id: str) -> Transaction:
        for transaction in self.iter_all():
            if transaction.id == transaction_id:
                return transaction
        raise NotFoundError(f"거래 ID를 찾을 수 없습니다: {transaction_id}")

    def _atomic_transform(
        self,
        transaction_id: str,
        transform: Callable[[Transaction], Transaction | None],
    ) -> None:
        path = self.store.path
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        found = False
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as target:
                for transaction in self.iter_all():
                    if transaction.id == transaction_id:
                        found = True
                        replacement = transform(transaction)
                        if replacement is not None:
                            target.write(
                                json.dumps(replacement.to_dict(), ensure_ascii=False) + "\n"
                            )
                    else:
                        target.write(
                            json.dumps(transaction.to_dict(), ensure_ascii=False) + "\n"
                        )
                target.flush()
                os.fsync(target.fileno())
            if not found:
                raise NotFoundError(f"거래 ID를 찾을 수 없습니다: {transaction_id}")
            os.replace(temp_name, path)
        except Exception:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise

    def update(self, transaction: Transaction) -> None:
        self._atomic_transform(transaction.id, lambda _old: transaction)

    def delete(self, transaction_id: str) -> None:
        self._atomic_transform(transaction_id, lambda _old: None)

    def is_category_used(self, category: str) -> bool:
        return any(t.category == category for t in self.iter_all())


class CategoryStore:
    def __init__(self, path: Path) -> None:
        self.store = JsonlStore(path)
        if self.store.ensure_exists():
            self.store.append_many({"name": name} for name in DEFAULT_CATEGORIES)

    def list(self) -> list[str]:
        return sorted(str(row["name"]) for row in self.store.iter_forward())

    def add(self, name: str) -> None:
        self.store.append({"name": name})

    def remove(self, name: str) -> None:
        self.store.replace_rows(
            [row for row in self.store.iter_forward() if str(row["name"]) != name]
        )


class BudgetStore:
    def __init__(self, path: Path) -> None:
        self.store = JsonlStore(path)
        self.store.ensure_exists()

    def list(self) -> list[tuple[str, int]]:
        return sorted(
            ((str(row["month"]), int(row["amount"])) for row in self.store.iter_forward()),
            reverse=True,
        )

    def get(self, month: str) -> int | None:
        for stored_month, amount in self.list():
            if stored_month == month:
                return amount
        return None

    def set(self, month: str, amount: int) -> None:
        rows = [
            row
            for row in self.store.iter_forward()
            if str(row.get("month")) != month
        ]
        rows.append({"month": month, "amount": amount})
        rows.sort(key=lambda row: str(row["month"]))
        self.store.replace_rows(rows)


class DataStores:
    def __init__(self, data_dir: Path) -> None:
        data_dir.mkdir(parents=True, exist_ok=True)
        self.transactions = TransactionRepository(data_dir / "transactions.jsonl")
        self.categories = CategoryStore(data_dir / "categories.jsonl")
        self.budgets = BudgetStore(data_dir / "budgets.jsonl")
