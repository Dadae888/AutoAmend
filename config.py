from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mistral_api_key: str
    mistral_model: str = "mistral-medium-latest"

    # Optional so the backend can boot (and the LLM relay + quota gate work)
    # before Stripe is set up. Payment endpoints return 503 until these are
    # set — see billing.py.
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_price_id: str | None = None

    database_url: str

    free_quota: int = 3

    cors_origins: str = "*"
    public_app_url: str = "http://127.0.0.1:8000"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
