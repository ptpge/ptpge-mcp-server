"""Shared-htpasswd verification for Basic Auth (Private Beta).

The register app provisions ONE gate entry per beta user in the shared
Apache htpasswd file (APR1-MD5 — see register-server gates.py). The same
file guards gutenlex.org/preview and api.ptpge.org /v1. Pointing
PTPGE_MCP_HTPASSWD at that file makes the welcome email's promise true:
the same personal username/password opens preview, the API *and* this
MCP server. Env-pair credentials (PTPGE_MCP_*_AUTH_USER/_PASS) keep
working alongside and are checked first.

Supported hash formats: $apr1$ (Apache MD5 — what the register and
cPanel Directory Privacy write), {SHA} (base64 SHA-1), and bcrypt
($2a/$2b/$2y) if the bcrypt package is installed. Unknown formats fail
closed.

Pure stdlib. The APR1 implementation is ported verbatim from
register-server/ptpge_register/gates.py (the algorithm is Apache's
`htpasswd -m`).
"""
from __future__ import annotations

import base64
import hashlib
import os
import secrets
import threading

_ITOA64 = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def _to64(value: int, length: int) -> str:
    out = []
    for _ in range(length):
        out.append(_ITOA64[value & 0x3F])
        value >>= 6
    return "".join(out)


def apr1(password: str, salt: str) -> str:
    """Apache APR1-MD5 crypt — the format `htpasswd -m` produces."""
    pw = password.encode("utf-8")
    sl = salt.encode("ascii")

    ctx = hashlib.md5(pw + b"$apr1$" + sl)
    inner = hashlib.md5(pw + sl + pw).digest()
    plen = len(pw)
    while plen > 0:
        ctx.update(inner[: min(16, plen)])
        plen -= 16
    i = len(pw)
    while i:
        ctx.update(b"\0" if i & 1 else pw[:1])
        i >>= 1
    final = ctx.digest()

    for i in range(1000):
        c = hashlib.md5()
        c.update(pw if i & 1 else final)
        if i % 3:
            c.update(sl)
        if i % 7:
            c.update(pw)
        c.update(final if i & 1 else pw)
        final = c.digest()

    f = final
    encoded = (
        _to64((f[0] << 16) | (f[6] << 8) | f[12], 4)
        + _to64((f[1] << 16) | (f[7] << 8) | f[13], 4)
        + _to64((f[2] << 16) | (f[8] << 8) | f[14], 4)
        + _to64((f[3] << 16) | (f[9] << 8) | f[15], 4)
        + _to64((f[4] << 16) | (f[10] << 8) | f[5], 4)
        + _to64(f[11], 2)
    )
    return f"$apr1${salt}${encoded}"


class HtpasswdVerifier:
    """mtime-cached username→hash map with fail-closed verification.

    The file is re-read only when its mtime changes, so a register-side
    approval, rotation or suspension takes effect on the next request —
    no restart, same pattern as CapabilityTokenMiddleware's tokens file.
    """

    def __init__(self, path: str) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._mtime: float | None = None
        self._entries: dict[str, str] = {}

    def _refresh(self) -> None:
        try:
            mtime = os.path.getmtime(self._path)
        except OSError:
            with self._lock:
                self._entries, self._mtime = {}, None
            return
        with self._lock:
            if mtime == self._mtime:
                return
            entries: dict[str, str] = {}
            try:
                with open(self._path, encoding="utf-8", errors="ignore") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line or line.startswith("#") or ":" not in line:
                            continue
                        user, hashed = line.split(":", 1)
                        entries[user.strip()] = hashed.strip()
            except OSError:
                entries = {}
            self._entries, self._mtime = entries, mtime

    def verify(self, username: str, password: str) -> bool:
        self._refresh()
        with self._lock:
            hashed = self._entries.get(username)
        if not hashed:
            # Burn comparable work so username existence doesn't leak
            # through response timing.
            apr1(password, "xxxxxxxx")
            return False
        if hashed.startswith("$apr1$"):
            try:
                _, _, salt, _ = hashed.split("$", 3)
            except ValueError:
                return False
            return secrets.compare_digest(apr1(password, salt), hashed)
        if hashed.startswith("{SHA}"):
            digest = base64.b64encode(
                hashlib.sha1(password.encode("utf-8")).digest()).decode("ascii")
            return secrets.compare_digest("{SHA}" + digest, hashed)
        if hashed.startswith(("$2a$", "$2b$", "$2y$")):
            try:
                import bcrypt  # optional dependency
            except ImportError:
                return False
            try:
                return bcrypt.checkpw(password.encode("utf-8"),
                                      hashed.encode("ascii"))
            except ValueError:
                return False
        return False
