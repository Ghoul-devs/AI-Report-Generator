from sentence_transformers import SentenceTransformer
import hashlib
import re
import warnings
import numpy as np

_model = None
_fallback_mode = False


def get_model():
    """Load the embedding model only when an upload or search needs it."""
    global _model
    if _model is None:
        from huggingface_hub import try_to_load_from_cache
        model_id = "sentence-transformers/all-MiniLM-L6-v2"
        cached = try_to_load_from_cache(model_id, "modules.json")
        _model = SentenceTransformer("all-MiniLM-L6-v2", local_files_only=cached is not None)
    return _model


def create_embeddings(texts: list[str]):
    global _fallback_mode
    if _fallback_mode:
        return _lexical_embeddings(texts)
    try:
        return get_model().encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    except Exception as error:
        _fallback_mode = True
        warnings.warn(f"Sentence Transformer unavailable; using disclosed lexical fallback ({type(error).__name__}).")
        return _lexical_embeddings(texts)


def create_query_embedding(query: str):
    return create_embeddings([query])


def get_embedding_mode():
    return "lexical_fallback" if _fallback_mode else "sentence_transformer"


def _lexical_embeddings(texts: list[str], dimension: int = 384):
    """Stable hashed-token vectors keep local FAISS retrieval usable offline."""
    vectors = np.zeros((len(texts), dimension), dtype="float32")
    for row, text in enumerate(texts):
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            index = int.from_bytes(hashlib.blake2b(token.encode(), digest_size=4).digest(), "little") % dimension
            vectors[row, index] += 1.0
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.maximum(norms, 1e-12)
