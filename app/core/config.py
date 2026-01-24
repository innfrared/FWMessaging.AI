from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    OPENAI_API_KEY: str | None = None

    OPENAI_MODEL_CLASSIFY: str = "gpt-4o-mini"
    OPENAI_MODEL_REPLY: str = "gpt-4o-mini"

    OPENAI_TEMPERATURE_CLASSIFY: float = 0.0
    OPENAI_TEMPERATURE_REPLY: float = 0.2

    META_VERIFY_TOKEN: str = ""
    META_APP_SECRET: str | None = None
    META_GRAPH_API_VERSION: str = "v20.0"
    META_PAGE_ACCESS_TOKEN: str | None = None
    META_INSTAGRAM_SEND_ENDPOINT: str = "https://graph.facebook.com/v20.0/me/messages"

    BUSINESS_NAME: str = "Your Business"
    BUSINESS_TONE: str = "Friendly, concise, helpful."
    BUSINESS_TIMEZONE: str = "America/Los_Angeles"
    ENV: str = "dev"
    LOG_LEVEL: str = "INFO"
    AUTO_REPLY_ENABLED: bool = False

    CAL_COM_API_KEY: str | None = None
    CAL_COM_CALENDAR_ID: str | None = None
    CAL_COM_BASE_URL: str = "https://api.cal.com/v1"
    BOOKING_BUFFER_MINUTES: int = 15


settings = Settings()
