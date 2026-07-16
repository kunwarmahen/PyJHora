"""RAG over classical Jyotish texts (§5.12) — retrieval + citations.

Readings can ground themselves in a local corpus of **public-domain** classical
translations (BPHS, Saravali, Phaladeepika, …) so the AI cites a source
("BPHS 24.13 says…") instead of asserting on its own authority. Embeddings are
computed with a local **Ollama** model (no new cloud service); the index is
cached to disk and rebuilt only when the corpus changes.

Integrity: this module invents nothing. It returns only passages that are
present in the corpus files, with whatever `source`/`reference` each entry
carries. Ship real public-domain texts (with genuine references) in
`rag_corpus/*.jsonl` to get real citations; the bundled seed file deliberately
uses honest "General principle" references, never fabricated verse numbers.

Corpus format — one JSON object per line in any `rag_corpus/*.jsonl`:
    {"source": "BPHS", "reference": "Ch.24 v.13", "text": "…translation…"}

Graceful degradation: if the corpus is empty or Ollama embeddings are
unreachable, `available()` is False and `retrieve()` returns [] — callers treat
citations as simply absent.
"""
import glob
import hashlib
import json
import os
import urllib.error
import urllib.request
from typing import List, Dict, Any, Optional

CORPUS_DIR = os.path.join(os.path.dirname(__file__), "rag_corpus")
CACHE_PATH = os.path.join(CORPUS_DIR, ".index.json")

OLLAMA_URL = (os.getenv("OLLAMA_URL") or "http://localhost:11434").rstrip("/")
EMBED_MODEL = os.getenv("RAG_EMBED_MODEL", "nomic-embed-text")
EMBED_TIMEOUT = float(os.getenv("RAG_EMBED_TIMEOUT", "20"))

# In-memory index: list of {source, reference, text, embedding:[float]}.
_INDEX: Optional[List[Dict[str, Any]]] = None
_CORPUS_HASH: Optional[str] = None


def _embed(text: str) -> Optional[List[float]]:
    """One Ollama embedding, or None if the service/model is unavailable."""
    payload = json.dumps({"model": EMBED_MODEL, "prompt": text}).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/embeddings", data=payload,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=EMBED_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
        emb = data.get("embedding")
        return emb if isinstance(emb, list) and emb else None
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None


def _load_corpus() -> List[Dict[str, str]]:
    entries: List[Dict[str, str]] = []
    for path in sorted(glob.glob(os.path.join(CORPUS_DIR, "*.jsonl"))):
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    obj = json.loads(line)
                    if obj.get("text"):
                        entries.append({
                            "source": obj.get("source", "Unknown"),
                            "reference": obj.get("reference", ""),
                            "text": obj["text"].strip(),
                        })
        except (OSError, ValueError):
            continue
    return entries


def _corpus_hash(entries: List[Dict[str, str]]) -> str:
    h = hashlib.sha1()
    h.update(EMBED_MODEL.encode())
    for e in entries:
        h.update((e["source"] + "|" + e["reference"] + "|" + e["text"]).encode("utf-8"))
    return h.hexdigest()


def _load_cache(expected_hash: str) -> Optional[List[Dict[str, Any]]]:
    try:
        with open(CACHE_PATH, encoding="utf-8") as fh:
            cache = json.load(fh)
        if cache.get("hash") == expected_hash and cache.get("model") == EMBED_MODEL:
            return cache.get("entries")
    except (OSError, ValueError):
        pass
    return None


def _save_cache(entries: List[Dict[str, Any]], corpus_hash: str) -> None:
    try:
        os.makedirs(CORPUS_DIR, exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as fh:
            json.dump({"hash": corpus_hash, "model": EMBED_MODEL, "entries": entries}, fh)
    except OSError:
        pass


def build_index(force: bool = False) -> int:
    """Ensure the in-memory index is current; (re)embed if the corpus changed.
    Returns the number of indexed passages (0 if unavailable)."""
    global _INDEX, _CORPUS_HASH
    corpus = _load_corpus()
    if not corpus:
        _INDEX, _CORPUS_HASH = [], ""
        return 0
    chash = _corpus_hash(corpus)
    if not force and _INDEX is not None and _CORPUS_HASH == chash:
        return len(_INDEX)

    cached = None if force else _load_cache(chash)
    if cached is not None:
        _INDEX, _CORPUS_HASH = cached, chash
        return len(_INDEX)

    # Embed each passage. If embeddings are unreachable, leave the index empty
    # (feature simply stays off) rather than a partial index.
    built: List[Dict[str, Any]] = []
    for e in corpus:
        emb = _embed(e["text"])
        if emb is None:
            _INDEX, _CORPUS_HASH = [], ""
            return 0
        built.append({**e, "embedding": emb})
    _INDEX, _CORPUS_HASH = built, chash
    _save_cache(built, chash)
    return len(built)


def available() -> bool:
    """True when there is a usable, embedded corpus."""
    if _INDEX is None:
        build_index()
    return bool(_INDEX)


def _cosine(a: List[float], b: List[float]) -> float:
    import numpy as np
    va, vb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    na, nb = np.linalg.norm(va), np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def retrieve(query: str, k: int = 3) -> List[Dict[str, Any]]:
    """Top-k corpus passages for `query`, each {source, reference, text, score}.
    Empty when the corpus/embeddings are unavailable."""
    if _INDEX is None:
        build_index()
    if not _INDEX:
        return []
    qemb = _embed(query)
    if qemb is None:
        return []
    scored = [
        {"source": e["source"], "reference": e["reference"], "text": e["text"],
         "score": round(_cosine(qemb, e["embedding"]), 4)}
        for e in _INDEX
    ]
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:k]
