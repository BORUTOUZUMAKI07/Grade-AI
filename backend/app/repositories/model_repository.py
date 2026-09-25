import json
import os
from app.repositories.base import BaseRepository
from app.core.exceptions import ModelWeightsNotFoundError

class FileSystemModelRepository(BaseRepository[dict]):
    def __init__(self, model_file_path: str):
        self._file_path = model_file_path

    def fetch_all(self) -> dict:
        if not os.path.exists(self._file_path):
            raise ModelWeightsNotFoundError()
        with open(self._file_path, "r") as f:
            return json.load(f)
