"""Local embedding backends (NFR1: nothing leaves the perimeter).

* ``tfidf`` (default): TF-IDF (1-2 grams) + truncated SVD → 64-d dense vectors,
  L2-normalised so cosine distance in Qdrant is meaningful. Fully offline, deterministic.
* ``ollama``: calls a locally hosted embedding model (e.g. ``nomic-embed-text``).

The vector dimension is fixed when the collection is (re)built — Section 8.4.
"""
from __future__ import annotations

import pickle

import httpx
import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer

from app.config import DATA_DIR, settings

MODEL_PATH = DATA_DIR / "embedder.pkl"
TFIDF_DIM = 64


class CorpusEmbedder:
    def __init__(self) -> None:
        self.backend = settings.embedder.lower()
        self.vectorizer: TfidfVectorizer | None = None
        self.svd: TruncatedSVD | None = None
        self._ollama_dim: int | None = None

    # ------------------------------------------------------------------ fit/load
    def fit(self, texts: list[str]) -> None:
        if self.backend == "ollama":
            return  # pretrained model, nothing to fit
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2), min_df=1, max_features=8192,
            stop_words="english", sublinear_tf=True,
        )
        x = self.vectorizer.fit_transform(texts)
        n_comp = max(2, min(TFIDF_DIM, x.shape[0] - 1, x.shape[1] - 1))
        self.svd = TruncatedSVD(n_components=n_comp, random_state=7)
        self.svd.fit(x)
        MODEL_PATH.write_bytes(pickle.dumps((self.vectorizer, self.svd)))

    def load(self) -> bool:
        if self.backend == "ollama":
            return True
        if not MODEL_PATH.exists():
            return False
        self.vectorizer, self.svd = pickle.loads(MODEL_PATH.read_bytes())
        return True

    @property
    def ready(self) -> bool:
        if self.backend == "ollama":
            return True
        return self.vectorizer is not None and self.svd is not None

    @property
    def dim(self) -> int:
        if self.backend == "ollama":
            if self._ollama_dim is None:
                self._ollama_dim = len(self.embed(["dimension probe"])[0])
            return self._ollama_dim
        # pad to TFIDF_DIM so the collection dimension never changes on refit
        return TFIDF_DIM

    # ------------------------------------------------------------------ embed
    def embed(self, texts: list[str]) -> list[list[float]]:
        if self.backend == "ollama":
            return self._embed_ollama(texts)
        if not self.ready:
            raise RuntimeError("embedder not fitted")
        dense = self.svd.transform(self.vectorizer.transform(texts))
        if dense.shape[1] < TFIDF_DIM:
            dense = np.hstack([dense, np.zeros((dense.shape[0], TFIDF_DIM - dense.shape[1]))])
        norms = np.linalg.norm(dense, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return (dense / norms).astype(float).tolist()

    def _embed_ollama(self, texts: list[str]) -> list[list[float]]:
        r = httpx.post(
            f"{settings.ollama_url}/api/embed",
            json={"model": settings.ollama_embed_model, "input": texts},
            timeout=60,
        )
        r.raise_for_status()
        vecs = np.array(r.json()["embeddings"], dtype=float)
        vecs /= np.maximum(np.linalg.norm(vecs, axis=1, keepdims=True), 1e-12)
        return vecs.tolist()

    # ------------------------------------------------------------------ 2-D map
    @staticmethod
    def project_2d(vectors: list[list[float]]) -> list[list[float]]:
        """PCA to 2-D for the similarity-neighbourhood plot in the console."""
        arr = np.array(vectors, dtype=float)
        if arr.shape[0] < 3:
            return [[float(i), 0.0] for i in range(arr.shape[0])]
        arr = arr - arr.mean(axis=0)
        u, s, _ = np.linalg.svd(arr, full_matrices=False)
        return (u[:, :2] * s[:2]).tolist()


embedder = CorpusEmbedder()
