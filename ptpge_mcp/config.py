"""Configuration via environment variables, with sensible defaults."""

import os
from dataclasses import dataclass, field


def _parse_credentials(users_env: str) -> list[tuple[str, str]]:
    """Parse a comma-separated list of `username:password` pairs.

    Used for PTPGE_MCP_AUTH_USERS to support multiple Basic Auth credentials.
    Empty strings, malformed pairs, and pairs with empty user/pass are silently
    dropped (we do not want a misformatted env var to lock the server open).

    Example input:
        "frankenstein-prosi:p4ssw0rd1,frankenstein-zipper:p4ssw0rd2"

    Example output:
        [("frankenstein-prosi", "p4ssw0rd1"), ("frankenstein-zipper", "p4ssw0rd2")]
    """
    pairs: list[tuple[str, str]] = []
    if not users_env:
        return pairs
    for entry in users_env.split(","):
        entry = entry.strip()
        if not entry or ":" not in entry:
            continue
        username, _, password = entry.partition(":")
        username = username.strip()
        password = password.strip()
        if username and password:
            pairs.append((username, password))
    return pairs


@dataclass(frozen=True)
class Config:
    """Runtime configuration for the PTPGE MCP server."""

    api_base: str
    api_user: str | None
    api_pass: str | None
    refresh_seconds: int
    log_level: str

    # Stealth Mode HTTP Basic Auth on this MCP server itself.
    #
    # v0.2.5+ supports multiple credentials simultaneously, enabling
    # per-recipient credentials for tracked Stealth Mode access (see
    # external-references/access-log.md and SD-0014 credentials-sharing
    # policy section).
    #
    # Two configuration paths, in order of precedence:
    #
    # 1. PTPGE_MCP_AUTH_USERS — comma-separated list of `user:pass` pairs.
    #    e.g. "frankenstein-prosi:p1,frankenstein-zipper:p2".
    #    Takes precedence when set.
    #
    # 2. PTPGE_MCP_AUTH_USER + PTPGE_MCP_AUTH_PASS — single legacy pair.
    #    Used when PTPGE_MCP_AUTH_USERS is not set, for backwards
    #    compatibility with deployments prior to v0.2.5.
    #
    # If neither path produces any credentials, Basic Auth is disabled
    # entirely and the server runs open (used for public launch).
    credentials: list[tuple[str, str]] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "Config":
        """Build a Config from environment variables.

        All variables are optional; defaults are tuned for production use
        against api.ptpge.org during Stealth Mode.
        """
        # Multi-user mode takes precedence over single-user fallback.
        credentials = _parse_credentials(os.getenv("PTPGE_MCP_AUTH_USERS", ""))

        if not credentials:
            # Backwards-compat: legacy single-user env vars.
            legacy_user = os.getenv("PTPGE_MCP_AUTH_USER", "").strip()
            legacy_pass = os.getenv("PTPGE_MCP_AUTH_PASS", "").strip()
            if legacy_user and legacy_pass:
                credentials = [(legacy_user, legacy_pass)]

        return cls(
            api_base=os.getenv("PTPGE_API_BASE", "https://api.ptpge.org/v1").rstrip("/"),
            api_user=os.getenv("PTPGE_API_USER"),
            api_pass=os.getenv("PTPGE_API_PASS"),
            refresh_seconds=int(os.getenv("PTPGE_REFRESH_SECONDS", "900")),
            log_level=os.getenv("PTPGE_LOG_LEVEL", "INFO"),
            credentials=credentials,
        )
