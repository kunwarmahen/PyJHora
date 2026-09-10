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
import logging
import os
import urllib.error
import urllib.request
from typing import List, Dict, Any, Optional

CORPUS_DIR = os.path.join(os.path.dirname(__file__), "rag_corpus")
CACHE_PATH = os.path.join(CORPUS_DIR, ".index.json")

logger = logging.getLogger(__name__)

OLLAMA_URL = (os.getenv("OLLAMA_URL") or "http://localhost:11434").rstrip("/")
EMBED_MODEL = os.getenv("RAG_EMBED_MODEL", "nomic-embed-text")
EMBED_TIMEOUT = float(os.getenv("RAG_EMBED_TIMEOUT", "20"))
EMBED_BATCH = max(1, int(os.getenv("RAG_EMBED_BATCH", "16")))

# In-memory index: list of {source, reference, text, embedding:[float]}.
_INDEX: Optional[List[Dict[str, Any]]] = None
_CORPUS_HASH: Optional[str] = None
# Normalised embedding matrix, derived from _INDEX and rebuilt whenever it is.
_MATRIX: Dict[str, Any] = {}


def _post(path: str, body: Dict[str, Any], timeout: float) -> Optional[Dict[str, Any]]:
    req = urllib.request.Request(
        f"{OLLAMA_URL}{path}", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None


def _embed(text: str) -> Optional[List[float]]:
    """One Ollama embedding, or None if the service/model is unavailable."""
    data = _post("/api/embeddings", {"model": EMBED_MODEL, "prompt": text},
                 EMBED_TIMEOUT)
    emb = (data or {}).get("embedding")
    return emb if isinstance(emb, list) and emb else None


def _embed_batch(texts: List[str]) -> Optional[List[List[float]]]:
    """Embed a batch through Ollama's newer `/api/embed`, or None if it is not
    there. Older builds only have the one-at-a-time `/api/embeddings`, and a
    real corpus is hundreds of passages — one HTTP round trip each turns a
    first build into minutes of nothing happening."""
    data = _post("/api/embed", {"model": EMBED_MODEL, "input": texts},
                 EMBED_TIMEOUT * max(1, len(texts) / 8))
    embs = (data or {}).get("embeddings")
    if isinstance(embs, list) and len(embs) == len(texts) and all(embs):
        return embs
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
        _MATRIX.clear()
        return 0
    chash = _corpus_hash(corpus)
    if not force and _INDEX is not None and _CORPUS_HASH == chash:
        return len(_INDEX)

    cached = None if force else _load_cache(chash)
    if cached is not None:
        _INDEX, _CORPUS_HASH = cached, chash
        _MATRIX.clear()
        return len(_INDEX)

    # Embed every passage. If embeddings are unreachable, leave the index empty
    # (the feature simply stays off) rather than a partial index.
    vectors: List[List[float]] = []
    batched = True
    for start in range(0, len(corpus), EMBED_BATCH):
        chunk = [e["text"] for e in corpus[start:start + EMBED_BATCH]]
        embs = _embed_batch(chunk) if batched else None
        if embs is None:
            batched = False           # no /api/embed here — fall back for good
            embs = []
            for text in chunk:
                emb = _embed(text)
                if emb is None:
                    _INDEX, _CORPUS_HASH = [], ""
                    _MATRIX.clear()
                    return 0
                embs.append(emb)
        vectors.extend(embs)
        logger.info("rag: embedded %d/%d passages", len(vectors), len(corpus))

    built = [{**e, "embedding": v} for e, v in zip(corpus, vectors)]
    _INDEX, _CORPUS_HASH = built, chash
    _MATRIX.clear()
    _save_cache(built, chash)
    return len(built)


def available() -> bool:
    """True when there is a usable, embedded corpus. Builds one if none is
    loaded yet, so the first caller pays for the embeddings."""
    if _INDEX is None:
        build_index()
    return bool(_INDEX)


def is_indexed() -> bool:
    """True when an index is ALREADY in memory — never builds one.

    For callers on a user's critical path. `available()` embeds the whole corpus
    on a cold process, and a first question should not wait on that; a prompt
    that mentions citations one request late is a far smaller problem than a
    question that hangs. `warm()` is what makes this true in practice."""
    return bool(_INDEX)


def warm() -> int:
    """Build the index if it isn't built, swallowing every failure.

    Called once at startup so `is_indexed()` is true by the time anyone asks a
    question. A failure here is not an error: Ollama may simply not be up yet,
    and the next caller retries (a failed build resets the corpus hash rather
    than caching the failure)."""
    try:
        return build_index()
    except Exception as e:          # noqa: BLE001 - startup must never fail here
        logger.info("rag: index not warmed (%s)", e)
        return 0


def _unit_matrix():
    """The index as one L2-normalised matrix, built once per index.

    Scoring a query is then a single matrix-vector product instead of a Python
    loop over every passage — which matters once the corpus is a whole book
    rather than the 21-line seed.
    """
    import numpy as np
    cached = _MATRIX.get("m")
    if cached is not None:
        return cached
    m = np.asarray([e["embedding"] for e in _INDEX or []], dtype=float)
    if m.size:
        norms = np.linalg.norm(m, axis=1, keepdims=True)
        m = m / np.where(norms == 0, 1.0, norms)
    _MATRIX["m"] = m
    return m


def retrieve(query: str, k: int = 3) -> List[Dict[str, Any]]:
    """Top-k corpus passages for `query`, each {source, reference, text, score}.
    Empty when the corpus/embeddings are unavailable."""
    import numpy as np
    if _INDEX is None:
        build_index()
    if not _INDEX:
        return []
    qemb = _embed(query)
    if qemb is None:
        return []
    q = np.asarray(qemb, dtype=float)
    qn = np.linalg.norm(q)
    if qn == 0:
        return []
    scores = _unit_matrix() @ (q / qn)
    top = np.argsort(scores)[::-1][:k]
    return [
        {"source": _INDEX[i]["source"], "reference": _INDEX[i]["reference"],
         "text": _INDEX[i]["text"], "score": round(float(scores[i]), 4)}
        for i in top
    ]
