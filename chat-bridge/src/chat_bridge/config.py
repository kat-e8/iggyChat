from pathlib import Path

from pydantic import BaseModel, Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class IgnitionTarget(BaseModel):
    gateway_url: str
    api_key: str


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

    # The Ignition gateways a chat can be pointed at, by name -- e.g.
    # {"stage": {"gateway_url": "http://ignition:8088", "api_key": "..."}},
    # given as JSON in IGNITION_TARGETS. The MCP gateway is multi-tenant: every
    # mcp__ignition__* call passes one of these as explicit gateway_url/api_key
    # overrides (see claude_service.py's _system_prompt), so the list lives
    # here in config rather than in code, and adding a gateway is a config
    # change, not a release.
    ignition_targets: dict[str, IgnitionTarget] = Field(validation_alias="IGNITION_TARGETS")

    # Which of ignition_targets a conversation starts on. A user can move a
    # conversation to another named target from a prompt ("use dev from now
    # on"); this is only where it starts.
    ignition_default_target: str = Field(validation_alias="IGNITION_DEFAULT_TARGET")

    # Canary Gateway (Canary Labs Historian MCP, from the canary-gateway
    # project) -- a single unauthenticated MCP endpoint, unlike the Ignition
    # gateway above: no X-API-Key at all, trusting network reachability alone
    # as its only access control. Its own scope, never combined with Ignition
    # (see claude_service.py's SCOPES).
    canary_gateway_url: str = Field(
        default="http://clubuntu.dala-cirius.ts.net:7200/canary/mcp",
        validation_alias="CANARY_GATEWAY_URL",
    )

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

    @field_validator("ignition_default_target")
    @classmethod
    def _default_target_is_listed(cls, v: str, info: ValidationInfo) -> str:
        # Fail at startup, not on the first chat turn: a default the prompt
        # can't resolve would leave the model with no gateway to call. A
        # field validator, not a model one, so the error echoes only this
        # value -- a model-level error prints every setting, API keys and
        # JWT secret included, into the container log.
        targets = info.data.get("ignition_targets", {})
        if v not in targets:
            raise ValueError(
                f"IGNITION_DEFAULT_TARGET={v!r} is not one of IGNITION_TARGETS "
                f"({', '.join(sorted(targets))})"
            )
        return v

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
