"""Gateway-level settings — bind address and the API key guarding /docker and /ignition.

Prefixed with GATEWAY_ in the environment / .env file.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # extra="ignore": this .env is shared with ignition_mcp.config.Settings
    # (IGNITION_MCP_* keys), and pydantic-settings treats any unrecognized
    # key in a dotenv file as a hard error regardless of prefix.
    model_config = SettingsConfigDict(env_file=".env", env_prefix="GATEWAY_", extra="ignore")

    api_key: str = Field(
        description=(
            "Required key clients must send (as 'X-API-Key') to reach /docker or /ignition. "
            "No default — /docker exposes container creation and /ignition exposes writes to "
            "live industrial systems, so the gateway refuses to start rather than default open. "
            "Set GATEWAY_API_KEY."
        ),
    )
    host: str = Field(default="127.0.0.1", description="Host to bind the gateway to")
    port: int = Field(default=8000, description="Port to bind the gateway to")


settings = Settings()
