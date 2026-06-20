"""Optional dense (embedding) retrieval for PTPGE search — graceful fallback.

If numpy + fastembed are installed AND a precomputed `term_embeddings.npz` is
present (built by tools/build_embeddings.py with the SAME model), search() blends
a semantic cosine score with the lexical score. If anything is missing or fails,
this module reports `available() == False` and search() uses pure lexical
matching — the live service can never break on account of semantics.

The embeddings file is keyed by FULL term URI (matching the search index's `id`),
so query_sims() returns {term_uri: cosine}.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_EMB_FILE = Path(__file__).resolve().parent / "term_embeddings.npz"

_state: dict = {
    "tried": False, "ok": False,
    "ids": None, "vecs": None, "model_name": None, "model": None, "np": None,
}


def _ensure() -> bool:
    if _state["tried"]:
        return _state["ok"]
    _state["tried"] = True
    try:
        if not _EMB_FILE.exists():
            logger.info("semantic: no term_embeddings.npz — lexical search only")
            return False
        import numpy as np  # noqa: WPS433
        data = np.load(_EMB_FILE, allow_pickle=False)
        _state["ids"] = [str(x) for x in data["ids"].tolist()]
        vecs = data["vecs"].astype("float32")
        vecs = vecs / (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9)
        _state["vecs"] = vecs
        _state["model_name"] = data["model"].item() if "model" in data else None
        _state["np"] = np
        from fastembed import TextEmbedding  # noqa: WPS433
        _state["model"] = TextEmbedding(model_name=_state["model_name"])
        _state["ok"] = True
        logger.info("semantic: loaded %d vectors (model %s)", len(_state["ids"]), _state["model_name"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("semantic search disabled (%s) — lexical only", exc)
        _state["ok"] = False
    return _state["ok"]


def available() -> bool:
    """True if embeddings + model are ready (lazy-initialized on first call)."""
    return _ensure()


def query_sims(query: str) -> dict | None:
    """Return {term_uri: cosine_similarity} for the query, or None if unavailable."""
    if not _ensure():
        return None
    try:
        np = _state["np"]
        qv = np.array(list(_state["model"].embed([query]))[0], dtype="float32")
        qv = qv / (np.linalg.norm(qv) + 1e-9)
        sims = _state["vecs"] @ qv
        return {tid: float(s) for tid, s in zip(_state["ids"], sims)}
    except Exception as exc:  # noqa: BLE001
        logger.warning("semantic query failed (%s) — lexical only for this query", exc)
        return None
