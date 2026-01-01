from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    llm_provider: str = "mock"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"

    store_provider: str = "memory"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

