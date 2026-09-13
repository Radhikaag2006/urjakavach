"""
Build the local knowledge base index from app/kb/documents/.

Run once (and again whenever you add or edit a reference document):

    python -m app.kb.build_index

Everything runs offline after the embedding model is cached on first
run. The index is written to app/kb/index/ which is gitignored — each
teammate builds it locally from the committed markdown documents.

Owner: Track A/B.
"""
import os
import sys
import glob

# Allow running as `python app/kb/build_index.py` as well as `-m`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import config  # noqa: E402


def chunk_text(text: str, max_chars: int = 900) -> list[str]:
    """Split on blank lines, then pack paragraphs into chunks that stay
    under max_chars. Simple and good enough for a handful of documents."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks, current = [], ""

    for p in paragraphs:
        if len(current) + len(p) + 2 <= max_chars:
            current = f"{current}\n\n{p}" if current else p
        else:
            if current:
                chunks.append(current)
            current = p
    if current:
        chunks.append(current)

    return chunks


def main():
    try:
        import chromadb
        from chromadb.utils import embedding_functions
    except ImportError:
        print("ERROR: chromadb / sentence-transformers not installed.")
        print("Run: pip install chromadb sentence-transformers")
        sys.exit(1)

    doc_paths = sorted(glob.glob(os.path.join(config.KB_DOCUMENTS_DIR, "*.md")))
    if not doc_paths:
        print(f"No documents found in {config.KB_DOCUMENTS_DIR}")
        sys.exit(1)

    print(f"Found {len(doc_paths)} reference document(s).")

    os.makedirs(config.KB_INDEX_DIR, exist_ok=True)
    client = chromadb.PersistentClient(path=config.KB_INDEX_DIR)

    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

    # Rebuild from scratch so edits to documents are always reflected
    try:
        client.delete_collection("mrpl_docs")
    except Exception:  # noqa: BLE001 - collection may not exist yet
        pass

    collection = client.create_collection(name="mrpl_docs", embedding_function=ef)

    ids, documents, metadatas = [], [], []
    for path in doc_paths:
        name = os.path.basename(path)
        with open(path, encoding="utf-8") as f:
            text = f.read()

        for i, chunk in enumerate(chunk_text(text)):
            ids.append(f"{name}::{i}")
            documents.append(chunk)
            metadatas.append({"source": name, "chunk": i})

        print(f"  {name}: {len([c for c in chunk_text(text)])} chunk(s)")

    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    print(f"\nIndexed {len(documents)} chunk(s) into {config.KB_INDEX_DIR}")
    print("Knowledge base ready.")


if __name__ == "__main__":
    main()
