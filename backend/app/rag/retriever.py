import faiss
import numpy as np
import re
import math

from app.rag.embeddings import create_embeddings, create_query_embedding


class VectorStore:

    def __init__(self):
        self.index = None
        self.documents = []
        self.loaded_document_ids = set()
        self.attempted_document_ids = set()

    def add_documents(self, chunks: list[dict]):

        embeddings = create_embeddings([chunk["text"] for chunk in chunks])

        dimension = embeddings.shape[1]

        if self.index is None:
            self.index = faiss.IndexFlatIP(dimension)

        self.index.add(
            embeddings.astype("float32")
        )

        self.documents.extend(chunks)
        self.loaded_document_ids.update(chunk.get("document_id") for chunk in chunks if chunk.get("document_id"))

    def _load_saved_documents(self):
        try:
            from app.database.database import connect
            from app.rag.loader import load_pdf_pages
            from app.rag.chunker import chunk_text
            with connect() as db:
                rows = db.execute("SELECT id,filename,path FROM documents WHERE status='ready'").fetchall()
            for row in rows:
                if row["id"] in self.loaded_document_ids or row["id"] in self.attempted_document_ids:
                    continue
                self.attempted_document_ids.add(row["id"])
                chunks = []
                for page in load_pdf_pages(row["path"]):
                    for text in chunk_text(page["text"]):
                        chunks.append({"document_id": row["id"], "filename": row["filename"],
                                       "page": page["page"], "chunk_id": f"{row['id']}-{len(chunks)+1}", "text": text})
                if chunks:
                    self.add_documents(chunks)
        except Exception:
            # A cold/unavailable embedding model must not stop the API from starting.
            return

    def search(self, query: str, top_k: int = 5):

        self._load_saved_documents()
        if self.index is None or not self.documents:
            return []

        query_embedding = create_query_embedding(query)

        scores, indices = self.index.search(
            query_embedding.astype("float32"),
            min(top_k, len(self.documents))
        )

        results = []

        for score, index in zip(scores[0], indices[0]):

            if index == -1:
                continue

            results.append({
                **self.documents[index],
                "score": float(score)
            })

        return results

    def keyword_search(self, query: str, top_k: int = 20):
        self._load_saved_documents()
        if not self.documents:
            return []
        tokenize = lambda text: re.findall(r"[a-z0-9]+", text.lower())
        query_terms = set(tokenize(query))
        corpus = [tokenize(document["text"]) for document in self.documents]
        average_length = sum(map(len, corpus)) / max(1, len(corpus))
        document_frequency = {term: sum(term in set(tokens) for tokens in corpus) for term in query_terms}
        ranked = []
        for document, tokens in zip(self.documents, corpus):
            frequencies = {term: tokens.count(term) for term in query_terms}
            score = 0.0
            for term, frequency in frequencies.items():
                if frequency:
                    idf = math.log(1 + (len(corpus) - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5))
                    denominator = frequency + 1.5 * (1 - 0.75 + 0.75 * len(tokens) / max(1, average_length))
                    score += idf * frequency * 2.5 / denominator
            if score:
                ranked.append({**document, "score": score})
        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked[:top_k]

    def hybrid_search(self, query: str, top_k: int = 20):
        candidates = {}
        for result in self.search(query, top_k=top_k) + self.keyword_search(query, top_k=top_k):
            candidates[result.get("chunk_id", result["text"])] = result
        return list(candidates.values())


vector_store = VectorStore()
