from functools import lru_cache
from app.core.config import settings
from app.repositories.model_repository import FileSystemModelRepository
from app.services.inference_service import StudentInferenceService

@lru_cache(maxsize=1)
def get_model_repository() -> FileSystemModelRepository:
    return FileSystemModelRepository(model_file_path=settings.MODEL_PATH)

def get_inference_service() -> StudentInferenceService:
    repository = get_model_repository()
    return StudentInferenceService(repository=repository)
