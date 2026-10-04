from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="/opt/presentation-intelligence/.env",
        env_file_encoding="utf-8",
    )

    database_url: str
    redis_url: str = "redis://localhost:6379"
    secret_key: str
    upload_dir: str = "/opt/presentation-intelligence/uploads"
    models_dir: str = "/opt/presentation-intelligence/models"
    max_video_size_mb: int = 500
    max_video_duration_minutes: int = 30
    max_concurrent_jobs: int = 1
    whisper_model: str = "small"
    video_sample_fps: int = 2
    anthropic_api_key: str = ""
    access_token_expire_minutes: int = 60


settings = Settings()
