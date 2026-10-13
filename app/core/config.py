from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables / the .env file."""

    app_name: str = "Employee API"
    database_url: str  # required: app refuses to start without it
    secret_key: str    # required: never hard-code this

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
