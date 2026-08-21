from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Rosetta is an Ignition frontend -- it talks to the pre-existing,
    # shared MCP gateway that already serves /ignition/mcp for other tools
    # on this host (Claude Code's own "ignition-gw" MCP server config points
    # at the same URL), rather than running a duplicate gateway of its own.
    # See Deployment/Phase10_*.pdf.
    ignition_mcp_url: str = Field(
        default="http://clubuntu.dala-cirius.ts.net:8000/ignition/mcp",
        validation_alias="IGNITION_MCP_URL",
    )
    ignition_mcp_api_key: str = Field(validation_alias="IGNITION_MCP_API_KEY")

    # The shared gateway is multi-tenant -- its own baked-in default Ignition
    # target is a dev instance, not this app's production one. Every
    # mcp__ignition__* call must pass these as explicit gateway_url/api_key
    # overrides (see claude_service.py's system_prompt) rather than relying
    # on the gateway's default.
    ignition_target_gateway_url: str = Field(
        default="http://clubuntu.dala-cirius.ts.net:9011",
        validation_alias="IGNITION_TARGET_GATEWAY_URL",
    )
    ignition_target_api_key: str = Field(validation_alias="IGNITION_TARGET_API_KEY")

    # Second named target ("ignition-dev"), so the model can resolve either
    # alias within a chat turn instead of only ever hitting the fixed prod
    # target above (see claude_service.py's system_prompt).
    ignition_dev_gateway_url: str = Field(
        default="http://katlegog.dala-cirius.ts.net:8088",
        validation_alias="IGNITION_DEV_GATEWAY_URL",
    )
    ignition_dev_api_key: str = Field(validation_alias="IGNITION_DEV_API_KEY")

    # Generic Gateway (ManPage/api) -- mounts /docker-mcp, /git-mcp,
    # /postgres-mcp, /coder-commands-mcp. Unlike the shared Ignition MCP
    # gateway above, this one is not multi-tenant: one key, one reachable
    # URL, no per-call target override needed. Separate from the Ignition
    # settings on purpose -- independent blast radii, see
    # Frontend_Templatize/Two-Gateway-Architecture.pdf in backend/.
    generic_gateway_url: str = Field(validation_alias="GENERIC_GATEWAY_URL")
    generic_gateway_api_key: str = Field(validation_alias="GENERIC_GATEWAY_API_KEY")

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
