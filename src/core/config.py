from functools import lru_cache
from typing import List
 
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
 
 
class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )
 
    # Application
    APP_NAME: str = "PetServices"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
 
    # Database
    DATABASE_URL: str
 
    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
 
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = Field(default_factory=list)
 
    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        if isinstance(v, list):
            return v
        return []
 
 
@lru_cache
def get_settings() -> Settings:
    return Settings()
 
 
settings = get_settings()
