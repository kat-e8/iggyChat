from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gateway_url: str = "http://127.0.0.1:8000"
    gateway_api_key: str

    host: str = Field(default="127.0.0.1", validation_alias="CHAT_BRIDGE_HOST")
    port: int = Field(default=8001, validation_alias="CHAT_BRIDGE_PORT")

    claude_model: str | None = Field(default=None, validation_alias="CLAUDE_MODEL")

    # Cumulative spend tracking (usage_store.py) -- persisted on the
    # chat-bridge-data volume (see docker-compose.yml) so it survives
    # container recreation on every deploy, not just one process's lifetime.
    usage_db_path: Path = Field(
        default=Path("chat_bridge_usage.db"), validation_alias="CHAT_BRIDGE_USAGE_DB_PATH"
    )
    # Both None (disabled) by default -- these are real-money caps and the
    # right number depends on the user's own budget, not a guess made here.
    max_daily_budget_usd: float | None = Field(
        default=None, validation_alias="CHAT_BRIDGE_MAX_DAILY_BUDGET_USD"
    )
    max_session_budget_usd: float | None = Field(
        default=None, validation_alias="CHAT_BRIDGE_MAX_SESSION_BUDGET_USD"
    )

    @field_validator("max_daily_budget_usd", "max_session_budget_usd", mode="before")
    @classmethod
    def _blank_env_means_unset(cls, v: object) -> object:
        # `KEY=` in an env_file sets the process env var to an empty string,
        # not "absent" -- without this, pydantic tries (and fails) to parse
        # "" as a float instead of falling back to the None default. Broke
        # chat-bridge on first deploy: crashed at startup with a
        # ValidationError, every documented "leave blank to disable" .env
        # value triggered it.
        return None if v == "" else v

    # Permanent user accounts (user_store.py) -- separate file from
    # usage.db, same persistent volume. See Deployment/Phase8_*.pdf.
    users_db_path: Path = Field(
        default=Path("chat_bridge_users.db"), validation_alias="CHAT_BRIDGE_USERS_DB_PATH"
    )

    jwt_secret: str
    jwt_expire_minutes: int = Field(default=1440, validation_alias="JWT_EXPIRE_MINUTES")
    # Off by default for local http dev; set true once served over https.
    cookie_secure: bool = Field(default=False, validation_alias="COOKIE_SECURE")

    # Unset in local dev -- `ng serve`'s proxy serves the frontend and only
    # forwards /api to this process. Set in the deployed image (see
    # Dockerfile) so this process is the single public entry point: it then
    # serves the built Angular app itself and falls back to its index.html
    # for client-side routes, alongside the existing /api/* and /health.
    frontend_dist: Path | None = Field(default=None, validation_alias="FRONTEND_DIST_PATH")


settings = Settings()
