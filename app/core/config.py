from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    OPENAI_API_KEY: str | None = None

    OPENAI_MODEL_GENERATE: str = "gpt-4o-mini"
    OPENAI_MODEL_EVALUATE: str = "gpt-4o-mini"

    OPENAI_TEMPERATURE_GENERATE: float = 0.3
    OPENAI_TEMPERATURE_EVALUATE: float = 0.0


settings = Settings()

