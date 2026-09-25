from typing import Generic, TypeVar

T = TypeVar('T')

class BaseRepository(Generic[T]):
    def fetch_all(self) -> T:
        raise NotImplementedError
