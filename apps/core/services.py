"""核心通用业务服务。"""


class PaginationService:
    DEFAULT_LIMIT = 20
    MIN_PAGE = 1
    MIN_LIMIT = 1
    MAX_LIMIT = 100

    @staticmethod
    def normalize_page(page: int) -> int:
        try:
            normalized = int(page)
        except (TypeError, ValueError):
            return PaginationService.MIN_PAGE
        return max(PaginationService.MIN_PAGE, normalized)

    @staticmethod
    def normalize_limit(limit: int, *, default: int | None = None, max_limit: int | None = None) -> int:
        fallback = PaginationService.DEFAULT_LIMIT if default is None else int(default)
        upper_bound = PaginationService.MAX_LIMIT if max_limit is None else int(max_limit)
        try:
            normalized = int(limit)
        except (TypeError, ValueError):
            return fallback
        return max(PaginationService.MIN_LIMIT, min(normalized, upper_bound))

    @staticmethod
    def normalize(page: int, limit: int, *, default_limit: int | None = None, max_limit: int | None = None) -> tuple[int, int]:
        return (
            PaginationService.normalize_page(page),
            PaginationService.normalize_limit(limit, default=default_limit, max_limit=max_limit),
        )
