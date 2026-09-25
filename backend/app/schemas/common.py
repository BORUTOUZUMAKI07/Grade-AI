from datetime import datetime, timezone
from typing import Annotated, Generic, TypeVar

from pydantic import AfterValidator, BaseModel

T = TypeVar("T")


def _as_utc(v: datetime) -> datetime:
    # SQLite hands back naive datetimes; everything is stored as UTC.
    return v if v.tzinfo else v.replace(tzinfo=timezone.utc)


UtcDatetime = Annotated[datetime, AfterValidator(_as_utc)]


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int
