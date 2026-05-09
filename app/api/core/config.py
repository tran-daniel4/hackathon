from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    supabase_url: str = ""

    # Comma-separated origins, e.g. ALLOWED_ORIGINS=http://localhost:3000,https://yourapp.com
    allowed_origins: str = "http://localhost:3000"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()  # type: ignore[call-arg]  # fields are populated from env vars at runtime
