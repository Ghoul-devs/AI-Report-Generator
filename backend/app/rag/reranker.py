from sentence_transformers import CrossEncoder

_model = None


def get_model():
    """Load the reranker only when there are candidate chunks to rank."""
    global _model
    if _model is None:
        from huggingface_hub import try_to_load_from_cache
        model_id = "cross-encoder/ms-marco-MiniLM-L-6-v2"
        cached = try_to_load_from_cache(model_id, "config.json")
        _model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", local_files_only=cached is not None)
    return _model


def rerank(query: str, results: list[dict], top_k: int = 5):
    if not results:
        return []

    pairs = [
        (query, result["text"])
        for result in results
    ]

    try:
        scores = get_model().predict(pairs)
    except Exception:
        # FAISS/BM25 candidates remain useful when the optional cross encoder cannot download.
        return sorted(results, key=lambda item: item.get("score", 0.0), reverse=True)[:top_k]

    ranked = []

    for result, score in zip(results, scores):
        ranked.append({
            **result,
            "score": float(score)
        })

    ranked.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return ranked[:top_k]
