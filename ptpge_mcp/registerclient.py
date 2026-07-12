"""Best-effort self-registration of fingerprints with the public resolver.

Every fingerprint the server computes is POSTed to the resolver's
register endpoint (SD-0058). The endpoint trusts nothing but mathematics:
it re-hashes the canonical string and writes the permanent page only when
sha256(canonical) == hash. Registration is therefore safe to fire blind.

Design constraints:
- stdlib only (urllib) — no new dependencies, no pip on deploy
- never blocks or fails a tool call: daemon thread, short timeout,
  all exceptions swallowed
- process-lifetime dedupe cache so repeated lookups don't re-POST

Disable by setting the environment variable
``PTPGE_RESOLVER_REGISTER_URL`` to an empty string.
"""

from __future__ import annotations

import json
import os
import threading
import urllib.request

REGISTER_URL = os.environ.get(
    "PTPGE_RESOLVER_REGISTER_URL", "https://ptpge.org/f/register.php"
)

_seen: set[str] = set()
_lock = threading.Lock()


def register_async(fingerprint_hash: str, canonical: str) -> None:
    """Fire-and-forget registration of one fingerprint."""
    if not REGISTER_URL:
        return
    with _lock:
        if fingerprint_hash in _seen:
            return
        if len(_seen) > 4096:
            _seen.clear()
        _seen.add(fingerprint_hash)
    threading.Thread(
        target=_post, args=(fingerprint_hash, canonical), daemon=True
    ).start()


def _post(fingerprint_hash: str, canonical: str) -> None:
    try:
        req = urllib.request.Request(
            REGISTER_URL,
            data=json.dumps(
                {"hash": fingerprint_hash, "canonical": canonical}
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=4).read()
    except Exception:
        pass
