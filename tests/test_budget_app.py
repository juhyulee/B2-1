from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from budget_app.decorators import log_command, measure_execution_time
from budget_app.errors import ValidationError
from budget_app.service import BudgetService


class BudgetServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.data_dir = Path(self.temporary.name) / "data"
        self.service = BudgetService(self.data_dir)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_add_list_search_and_summary(self) -> None:
        first = self.service.add_transaction(
            date_value="2026-11-01",
            type_value="expense",
            category="식비",
            amount_value="12000",
            memo="점심",
            tags="회사,점심",
        )
        second = self.service.add_transaction(
            date_value="2026-11-05",
            type_value="income",
            category="급여",
            amount_value="3000000",
            memo="급여",
        )

        self.assertEqual([second.id, first.id], [t.id for t in self.service.list_transactions()])
        self.assertEqual([first.id], [t.id for t in self.service.search(tag="점심")])

        self.service.set_budget("2026-11", 10000)
        summary = self.service.monthly_summary("2026-11", 3)
        self.assertEqual(3000000, summary.income)
        self.assertEqual(12000, summary.expense)
        self.assertEqual(2988000, summary.balance)
        self.assertEqual(10000, summary.budget)
        self.assertEqual([("식비", 12000)], summary.category_expenses)

    def test_update_delete_and_category_protection(self) -> None:
        transaction = self.service.add_transaction(
            date_value="2026-11-01",
            type_value="expense",
            category="식비",
            amount_value=1000,
        )
        updated = self.service.update_transaction(
            transaction.id,
            amount_value=2500,
            memo="수정됨",
        )
        self.assertEqual(2500, updated.amount)
        self.assertEqual("수정됨", updated.memo)

        with self.assertRaises(ValidationError):
            self.service.remove_category("식비")

        self.service.delete_transaction(transaction.id)
        self.assertEqual([], list(self.service.list_transactions()))
        self.service.remove_category("식비")
        self.assertNotIn("식비", self.service.list_categories())

    def test_import_export_counts_and_schema(self) -> None:
        source = Path(self.temporary.name) / "source.csv"
        with source.open("w", encoding="utf-8", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["date", "type", "category", "amount", "memo", "tags"])
            writer.writerow(["2026-11-01", "expense", "식비", "9000", "점심", "점심|회사"])
            writer.writerow(["bad-date", "expense", "식비", "1000", "실패", ""])

        imported, failed = self.service.import_csv(source)
        self.assertEqual((1, 1), (imported, failed))

        output = Path(self.temporary.name) / "output.csv"
        exported = self.service.export_csv(output, month="2026-11")
        self.assertEqual(1, exported)
        with output.open("r", encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))
        self.assertEqual("점심|회사", rows[0]["tags"])
        self.assertEqual("9000", rows[0]["amount"])

    def test_logging_and_timing_decorators(self) -> None:
        @log_command
        @measure_execution_time
        def sample_command() -> int:
            return 0

        with self.assertLogs("budget_app", level="INFO") as captured:
            self.assertEqual(0, sample_command())

        messages = "\n".join(captured.output)
        self.assertIn("command_started", messages)
        self.assertIn("command_finished", messages)
        self.assertIn("command_timing", messages)

    def test_invalid_values_do_not_create_transaction(self) -> None:
        with self.assertRaises(ValidationError):
            self.service.add_transaction(
                date_value="2026-02-30",
                type_value="expense",
                category="식비",
                amount_value=1000,
            )
        with self.assertRaises(ValidationError):
            self.service.add_transaction(
                date_value="2026-11-01",
                type_value="expense",
                category="없는분류",
                amount_value=1000,
            )
        self.assertEqual([], list(self.service.list_transactions()))


if __name__ == "__main__":
    unittest.main()
