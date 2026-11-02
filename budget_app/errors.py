class BudgetAppError(Exception):
    """사용자에게 안내할 수 있는 가계부 오류."""


class ValidationError(BudgetAppError):
    """입력값 검증 오류."""


class NotFoundError(BudgetAppError):
    """요청한 데이터가 없을 때의 오류."""
