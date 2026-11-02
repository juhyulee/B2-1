from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from typing import Any

from .decorators import handle_cli_errors
from .errors import ValidationError
from .models import Transaction
from .service import BudgetService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m budget_app",
        description="JSONL 파일에 안전하게 저장하는 콘솔 가계부",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="데이터 폴더 (기본값: ./data)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("add", help="대화형으로 거래 추가")

    list_parser = subparsers.add_parser("list", help="최신 거래부터 조회")
    list_parser.add_argument("--limit", type=int, help="최대 표시 건수")

    search_parser = subparsers.add_parser("search", help="조건으로 거래 검색")
    search_parser.add_argument("--from", dest="from_date", help="시작일 YYYY-MM-DD")
    search_parser.add_argument("--to", dest="to_date", help="종료일 YYYY-MM-DD")
    search_parser.add_argument("--category", help="카테고리")
    search_parser.add_argument("--type", choices=["income", "expense"], help="거래 유형")
    search_parser.add_argument("--q", help="메모/카테고리 검색어")
    search_parser.add_argument("--tag", help="태그")

    summary_parser = subparsers.add_parser("summary", help="월별 요약")
    summary_parser.add_argument("--month", required=True, help="대상 월 YYYY-MM")
    summary_parser.add_argument("--top", type=int, default=3, help="지출 상위 카테고리 수")

    budget_parser = subparsers.add_parser("budget", help="월 예산 관리")
    budget_subparsers = budget_parser.add_subparsers(
        dest="budget_command", required=True
    )
    budget_set = budget_subparsers.add_parser("set", help="월 예산 설정")
    budget_set.add_argument("--month", required=True, help="대상 월 YYYY-MM")
    budget_set.add_argument("--amount", required=True, help="예산 금액")
    budget_get = budget_subparsers.add_parser("get", help="월 예산 조회")
    budget_get.add_argument("--month", required=True, help="대상 월 YYYY-MM")
    budget_subparsers.add_parser("list", help="전체 예산 조회")

    category_parser = subparsers.add_parser("category", help="카테고리 관리")
    category_subparsers = category_parser.add_subparsers(
        dest="category_command", required=True
    )
    category_add = category_subparsers.add_parser("add", help="카테고리 추가")
    category_add.add_argument("--name", required=True)
    category_subparsers.add_parser("list", help="카테고리 목록")
    category_remove = category_subparsers.add_parser(
        "remove", help="카테고리 삭제"
    )
    category_remove.add_argument("--name", required=True)

    update_parser = subparsers.add_parser("update", help="ID로 거래 수정")
    update_parser.add_argument("--id", required=True, dest="transaction_id")
    update_parser.add_argument("--date", dest="date_value")
    update_parser.add_argument("--type", choices=["income", "expense"], dest="type_value")
    update_parser.add_argument("--category")
    update_parser.add_argument("--amount", dest="amount_value")
    update_parser.add_argument("--memo")
    update_parser.add_argument(
        "--tags", help="쉼표로 구분. 빈 문자열을 주면 태그 전체 삭제"
    )

    delete_parser = subparsers.add_parser("delete", help="ID로 거래 삭제")
    delete_parser.add_argument("--id", required=True, dest="transaction_id")

    import_parser = subparsers.add_parser("import", help="CSV 거래 가져오기")
    import_parser.add_argument("--from", required=True, dest="source", type=Path)

    export_parser = subparsers.add_parser("export", help="CSV 거래 내보내기")
    export_parser.add_argument("--out", required=True, type=Path)
    export_parser.add_argument("--month", help="대상 월 YYYY-MM")
    export_parser.add_argument("--from", dest="from_date", help="시작일 YYYY-MM-DD")
    export_parser.add_argument("--to", dest="to_date", help="종료일 YYYY-MM-DD")

    return parser


def print_transaction(transaction: Transaction) -> None:
    tags = ", ".join(transaction.tags or []) or "-"
    memo = transaction.memo or "-"
    print(
        f"{transaction.id} | {transaction.date} | {transaction.type:<7} | "
        f"{transaction.category} | {transaction.amount:,}원 | {memo} | {tags}"
    )


def print_transactions(transactions: Any) -> None:
    count = 0
    for transaction in transactions:
        print_transaction(transaction)
        count += 1
    if count == 0:
        print("조건에 맞는 거래가 없습니다.")
    else:
        print(f"총 {count}건")


def handle_add(service: BudgetService) -> None:
    today = date.today().isoformat()
    print("거래 정보를 입력하세요. 유형은 income 또는 expense입니다.")
    date_value = input(f"날짜 [{today}]: ").strip() or today
    type_value = input("유형 (income/expense): ").strip()
    category = input("카테고리: ").strip()
    amount_value = input("금액: ").strip()
    memo = input("메모 (선택): ").strip()
    tags = input("태그 (쉼표 구분, 선택): ").strip()
    transaction = service.add_transaction(
        date_value=date_value,
        type_value=type_value,
        category=category,
        amount_value=amount_value,
        memo=memo,
        tags=tags,
    )
    print(f"거래를 추가했습니다. ID: {transaction.id}")


def dispatch(args: argparse.Namespace) -> int:
    service = BudgetService(args.data_dir)

    if args.command == "add":
        handle_add(service)
    elif args.command == "list":
        print_transactions(service.list_transactions(args.limit))
    elif args.command == "search":
        print_transactions(
            service.search(
                from_date=args.from_date,
                to_date=args.to_date,
                category=args.category,
                type_value=args.type,
                query=args.q,
                tag=args.tag,
            )
        )
    elif args.command == "summary":
        summary = service.monthly_summary(args.month, args.top)
        print(f"[{summary.month} 요약]")
        if summary.income == 0 and summary.expense == 0:
            print("이 달에 등록된 거래가 없습니다.")
        print(f"수입: {summary.income:,}원")
        print(f"지출: {summary.expense:,}원")
        print(f"잔액: {summary.balance:,}원")
        if summary.category_expenses:
            print("지출 상위 카테고리:")
            for index, (category, amount) in enumerate(
                summary.category_expenses, start=1
            ):
                print(f"  {index}. {category}: {amount:,}원")
        if summary.budget is None:
            print("예산: 설정되지 않음")
        else:
            usage = summary.expense / summary.budget * 100
            print(f"예산: {summary.budget:,}원 (사용률 {usage:.1f}%)")
            if summary.expense > summary.budget:
                print(
                    f"경고: 예산을 {summary.expense - summary.budget:,}원 초과했습니다."
                )
    elif args.command == "budget":
        if args.budget_command == "set":
            amount = service.set_budget(args.month, args.amount)
            print(f"{args.month} 예산을 {amount:,}원으로 설정했습니다.")
        elif args.budget_command == "get":
            amount = service.get_budget(args.month)
            if amount is None:
                print(f"{args.month}에 설정된 예산이 없습니다.")
            else:
                print(f"{args.month}: {amount:,}원")
        else:
            budgets = service.list_budgets()
            if not budgets:
                print("설정된 예산이 없습니다.")
            for month, amount in budgets:
                print(f"{month}: {amount:,}원")
    elif args.command == "category":
        if args.category_command == "add":
            service.add_category(args.name)
            print(f"카테고리를 추가했습니다: {args.name.strip()}")
        elif args.category_command == "list":
            for category in service.list_categories():
                print(category)
        else:
            service.remove_category(args.name)
            print(f"카테고리를 삭제했습니다: {args.name.strip()}")
    elif args.command == "update":
        supplied = [
            args.date_value,
            args.type_value,
            args.category,
            args.amount_value,
            args.memo,
            args.tags,
        ]
        if all(value is None for value in supplied):
            raise ValidationError("수정할 옵션을 하나 이상 지정하세요.")
        updated = service.update_transaction(
            args.transaction_id,
            date_value=args.date_value,
            type_value=args.type_value,
            category=args.category,
            amount_value=args.amount_value,
            memo=args.memo,
            tags=args.tags,
            tags_supplied=args.tags is not None,
        )
        print("거래를 수정했습니다.")
        print_transaction(updated)
    elif args.command == "delete":
        service.delete_transaction(args.transaction_id)
        print(f"거래를 삭제했습니다: {args.transaction_id}")
    elif args.command == "import":
        imported, failed = service.import_csv(args.source)
        print(f"가져오기 완료: 성공 {imported}건, 실패 {failed}건")
    elif args.command == "export":
        if args.month and (args.from_date or args.to_date):
            raise ValidationError(
                "--month와 --from/--to는 함께 사용할 수 없습니다."
            )
        if not args.month and not (args.from_date and args.to_date):
            raise ValidationError(
                "--month 또는 --from과 --to를 함께 지정하세요."
            )
        count = service.export_csv(
            args.out,
            month=args.month,
            from_date=args.from_date,
            to_date=args.to_date,
        )
        print(f"내보내기 완료: {count}건 -> {args.out}")
    return 0


@handle_cli_errors
def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return dispatch(args)
