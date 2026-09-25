from math import ceil

from fastapi import Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session


class PageParams:
    def __init__(self, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
        self.page = page
        self.page_size = page_size


def paginate(db: Session, stmt, params: PageParams, scalars: bool = True):
    """Return (rows, total) for one page of `stmt`."""
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    paged = stmt.limit(params.page_size).offset((params.page - 1) * params.page_size)
    rows = list(db.scalars(paged)) if scalars else list(db.execute(paged).all())
    return rows, total


def make_page(items: list, total: int, params: PageParams) -> dict:
    return {"items": items, "total": total, "page": params.page, "page_size": params.page_size,
            "pages": max(1, ceil(total / params.page_size))}
