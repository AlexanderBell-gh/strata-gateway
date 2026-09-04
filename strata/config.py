from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    STRATA_PORT: int = 8000
    STRATA_HOST: str = "0.0.0.0"
    STRATA_CORS_ORIGINS: str = "*"
    STRATA_DEFAULT_UPSTREAM: str = "https://api.openai.com/v1"
    STRATA_UPSTREAM_API_KEY: str = ""
    STRATA_TIMEOUT: int = 30
    STRATA_MAX_CONCURRENT: int = 100
    STRATA_LOG_LEVEL: str = "INFO"
    STRATA_DB_PATH: str = "./data/strata.db"
    STRATA_MAX_TOKENS_PER_SESSION: int = 50_000

    @model_validator(mode="after")
    def validate_api_key(self) -> "Settings":
        if not self.STRATA_UPSTREAM_API_KEY:
            raise ValueError("STRATA_UPSTREAM_API_KEY is required — set it in env or .env file")
        return self

    model_config = {"env_prefix": "", "env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
