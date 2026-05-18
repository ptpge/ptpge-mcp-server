"""Configuration via environment variables, with sensible defaults."""

import os
import re
from dataclasses import dataclass, field


def _parse_credentials(users_env: str) -> list[tuple[str, str]]:
    """Parse a comma-separated list of `username:password` pairs.

    Used for PTPGE_MCP_AUTH_USERS to support multiple Basic Auth credentials
    in a single env var. Empty strings, malformed pairs, and pairs with
    empty user/pass are silently dropped (we do not want a misformatted env
    var to lock the server open).

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


# Per-recipient env var pattern under the existing PTPGE_MCP_* namespace.
# Each recipient gets a pair like:
#     PTPGE_MCP_ZIPPER_AUTH_USER + PTPGE_MCP_ZIPPER_AUTH_PASS
# The regex requires a non-empty NAME segment between MCP and AUTH, so
# the legacy single-user pair (PTPGE_MCP_AUTH_USER + PTPGE_MCP_AUTH_PASS)
# does NOT match this pattern and is handled by a separate fallback.
_AUTH_USER_PATTERN = re.compile(r"^PTPGE_MCP_([A-Z0-9]+)_AUTH_USER$")
_AUTH_PASS_PATTERN = re.compile(r"^PTPGE_MCP_([A-Z0-9]+)_AUTH_PASS$")


def _collect_per_recipient_credentials(env: dict[str, str] | None = None) -> list[tuple[str, str]]:
    """Find all PTPGE_MCP_<NAME>_AUTH_USER + PTPGE_MCP_<NAME>_AUTH_PASS pairs.

    Returns a list of (username, password) tuples sorted by NAME for
    deterministic order (useful for testing and logs). Unmatched USER or
    PASS entries are silently dropped — both halves of a pair must be set
    and non-empty for the credential to be loaded.

    Note: this pattern requires a NAME segment between MCP and AUTH, so it
    does **not** match the legacy `PTPGE_MCP_AUTH_USER` + `PTPGE_MCP_AUTH_PASS`
    pair. That legacy pair is handled by `_legacy_single_user_credential()`.

    The `env` argument allows dependency injection for unit testing;
    defaults to `os.environ` in production.
    """
    src = env if env is not None else os.environ
    users_by_name: dict[str, str] = {}
    passes_by_name: dict[str, str] = {}
    for var_name, var_value in src.items():
        m_u = _AUTH_USER_PATTERN.match(var_name)
        if m_u:
            users_by_name[m_u.group(1)] = var_value.strip()
            continue
        m_p = _AUTH_PASS_PATTERN.match(var_name)
        if m_p:
            passes_by_name[m_p.group(1)] = var_value.strip()
    credentials: list[tuple[str, str]] = []
    for name in sorted(set(users_by_name) & set(passes_by_name)):
        u = users_by_name[name]
        p = passes_by_name[name]
        if u and p:
            credentials.append((u, p))
    return credentials


def _legacy_single_user_credential(env: dict[str, str] | None = None) -> list[tuple[str, str]]:
    """Return [(user, pass)] if the legacy single-user env vars are set, else []."""
    src = env if env is not None else os.environ
    u = src.get("PTPGE_MCP_AUTH_USER", "").strip()
    p = src.get("PTPGE_MCP_AUTH_PASS", "").strip()
    if u and p:
        return [(u, p)]
    return []


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
    # v0.2.6+ supports three configuration paths. All paths under
    # the PTPGE_MCP_* namespace for consistency with the existing
    # legacy variables.
    #
    # When PTPGE_MCP_AUTH_USERS (path 1) is set, it overrides everything
    # else. Otherwise, paths 2 and 3 are merged so that the legacy
    # single-user fallback can coexist with per-recipient pairs (useful
    # for keeping an internal/testing credential alongside per-recipient
    # ones).
    #
    # 1. PTPGE_MCP_AUTH_USERS — comma-separated `user:pass` pairs in a
    #    single env var. Highest precedence; overrides paths 2 and 3.
    #    e.g. "frankenstein-stealth:p1,zipper-stealth:p2".
    #
    # 2. PTPGE_MCP_<NAME>_AUTH_USER + PTPGE_MCP_<NAME>_AUTH_PASS — per-
    #    recipient pairs. cPanel-native: easy to add, revoke, and rotate
    #    individual recipients without touching the others.
    #    e.g. PTPGE_MCP_ZIPPER_AUTH_USER + PTPGE_MCP_ZIPPER_AUTH_PASS.
    #
    # 3. PTPGE_MCP_AUTH_USER + PTPGE_MCP_AUTH_PASS — legacy single-user
    #    pair (v0.2.4 and earlier). Merged with per-recipient pairs when
    #    both are configured, so internal/testing access can coexist with
    #    issued per-recipient credentials.
    #
    # If none of the paths produce any credentials, Basic Auth is disabled
    # entirely and the server runs open (used at public launch).
    credentials: list[tuple[str, str]] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "Config":
        """Build a Config from environment variables.

        All variables are optional; defaults are tuned for production use
        against api.ptpge.org during Stealth Mode.
        """
        # Path 1: explicit comma-separated list takes absolute precedence.
        # When set, paths 2 and 3 are intentionally ignored so a deployer
        # has full override capability.
        credentials = _parse_credentials(os.getenv("PTPGE_MCP_AUTH_USERS", ""))

        if not credentials:
            # Merge paths 2 + 3: per-recipient pairs alongside legacy single.
            # Deduplicate on the (user, pass) tuple in case both paths
            # somehow define the same credential.
            per_recipient = _collect_per_recipient_credentials()
            legacy = _legacy_single_user_credential()
            seen: set[tuple[str, str]] = set()
            for pair in per_recipient + legacy:
                if pair not in seen:
                    seen.add(pair)
                    credentials.append(pair)

        return cls(
            api_base=os.getenv("PTPGE_API_BASE", "https://api.ptpge.org/v1").rstrip("/"),
            api_user=os.getenv("PTPGE_API_USER"),
            api_pass=os.getenv("PTPGE_API_PASS"),
            refresh_seconds=int(os.getenv("PTPGE_REFRESH_SECONDS", "900")),
            log_level=os.getenv("PTPGE_LOG_LEVEL", "INFO"),
            credentials=credentials,
        )
