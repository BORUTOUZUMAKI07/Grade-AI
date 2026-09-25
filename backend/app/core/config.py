import os
from pydantic_settings import BaseSettings, SettingsConfigDict

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEV_SECRET = "dev-only-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    PROJECT_NAME: str = "GradeAI Classification Core"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    BASE_DIR: str = _BASE
    MODEL_PATH: str = os.path.join(_BASE, "model_store", "decision_tree_model.json")
    # Explicit origins only: a wildcard combined with credentials lets any site call the API as the user.
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    DATABASE_URL: str = f"sqlite:///{os.path.join(_BASE, 'gradeai.db')}"
    SECRET_KEY: str = DEV_SECRET
    ACCESS_TOKEN_MINUTES: int = 15
    REFRESH_TOKEN_DAYS: int = 7
    ADMIN_EMAIL: str = ""


settings = Settings()
