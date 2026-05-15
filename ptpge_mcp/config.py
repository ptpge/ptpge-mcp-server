"""Configuration via environment variables, with sensible defaults."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Runtime configuration for the PTPGE MCP server."""

    api_base: str
    api_user: str | None
    api_pass: str | None
    refresh_seconds: int
    log_level: str

    # Stealth Mode HTTP Basic Auth on this MCP server itself.
    # Both must be set to enable; empty strings disable auth (default).
    auth_user: str = ""
    auth_pass: str = ""

    @classmethod
    def from_env(cls) -> "Config":
        """Build a Config from environment variables.

        All variables are optional; defaults are tuned for production use
        against api.ptpge.org during Stealth Mode.
        """
        return cls(
            api_base=os.getenv("PTPGE_API_BASE", "https://api.ptpge.org/v1").rstrip("/"),
            api_user=os.getenv("PTPGE_API_USER"),
            api_pass=os.getenv("PTPGE_API_PASS"),
            refresh_seconds=int(os.getenv("PTPGE_REFRESH_SECONDS", "900")),
            log_level=os.getenv("PTPGE_LOG_LEVEL", "INFO"),
            auth_user=os.getenv("PTPGE_MCP_AUTH_USER", ""),
            auth_pass=os.getenv("PTPGE_MCP_AUTH_PASS", ""),
        )
