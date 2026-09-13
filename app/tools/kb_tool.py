"""
Knowledge Base tool (RAG retriever) — organisation-specific grounding.

Retrieves the most relevant chunks from MRPL's own reference documents
so the reasoning model answers from plant material, not general
knowledge. Runs fully offline once the embedding model is cached.

Degrades gracefully: if chromadb / sentence-transformers are not
installed, or the index has not been built yet, retrieval returns an
empty string and the rest of the pipeline carries on unaffected. That
means a teammate who has not set up the KB can still run every flow.

Owner: Track A/B. Build the index with:  python -m app.kb.build_index
"""
import os
from .. import config

_collection = None
_load_attempted = False
_load_error = None


def _get_collection():
    """Lazily open the persistent Chroma collection. Returns None if the
    KB is unavailable for any reason (not installed, not built yet)."""
    global _collection, _load_attempted, _load_error

    if _load_attempted:
        return _collection
    _load_attempted = True

    if not config.USE_KNOWLEDGE_BASE:
        _load_error = "knowledge base disabled in config"
        return None

    try:
        import chromadb
        from chromadb.utils import embedding_functions

        if not os.path.exists(config.KB_INDEX_DIR):
            _load_error = "index not built yet — run: python -m app.kb.build_index"
            return None

        client = chromadb.PersistentClient(path=config.KB_INDEX_DIR)
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        _collection = client.get_collection(name="mrpl_docs", embedding_function=ef)
    except Exception as e:  # noqa: BLE001 - any failure means "no KB", never a crash
        _load_error = str(e)
        _collection = None

    return _collection


def retrieve_context(query: str, top_k: int | None = None) -> str:
    """Return concatenated reference text relevant to `query`, or "" if
    the knowledge base is unavailable."""
    collection = _get_collection()
    if collection is None:
        return ""

    k = top_k or config.KB_TOP_K
    try:
        res = collection.query(query_texts=[query], n_results=k)
        docs = res.get("documents", [[]])[0]
        if not docs:
            return ""
        return "\n---\n".join(docs)
    except Exception:  # noqa: BLE001
        return ""


def kb_status() -> dict:
    """Diagnostics for /api/health and for teammates debugging setup."""
    collection = _get_collection()
    return {
        "available": collection is not None,
        "reason": None if collection is not None else _load_error,
    }
