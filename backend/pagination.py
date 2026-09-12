import math


def paginate(items: list, total: int, page: int, page_size: int) -> dict:
    """Builds the standard list-endpoint envelope (TAS pagination standard, PRD §40)."""
    total_pages = math.ceil(total / page_size) if page_size else 0
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }
