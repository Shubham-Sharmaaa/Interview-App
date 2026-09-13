"""
Typed, validated access to environment variables.

Using pydantic-settings here instead of scattering os.environ.get(...) calls
means: (1) the app fails fast and loudly at startup if a required var is
missing, instead of failing confusingly on the first request that needs it,
and (2) every other module imports `settings` and gets IDE autocomplete +
type checking on config values, the same benefit Pydantic gives request bodies.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongodb_uri: str
    mongodb_db_name: str = "interview_app"
    mongodb_test_db_name: str = "interview_app_test"

    jwt_secret: str
    jwt_expire_minutes: int = 120

    gemini_api_key: str
    gemini_model: str = "gemini-2.5-flash"

    frontend_origin: str = "http://localhost:5173"


settings = Settings()
