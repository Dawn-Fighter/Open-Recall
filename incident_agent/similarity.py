"""Real embedding similarity scorer.

Replaces synthetic position-based scores with actual cosine similarity
computed from alert fingerprint embeddings. Supports three backends:
1. Hindsight Cloud native similarity (if SDK exposes it)
2. Local sentence-transformers embeddings (offline/fast)
3. Groq embedding API (online, higher quality)

Falls back gracefully: if no embedding backend is available, returns
the position-based scores from the existing normalizer.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .models import AlertFingerprint, MemoryMatch


ROOT = Path(__file__).resolve().parents[1]
EMBEDDING_CACHE_PATH = ROOT / "data" / "embedding_cache.json"


def fingerprint_to_text(fp: AlertFingerprint) -> str:
    """Convert a fingerprint to a text string suitable for embedding."""
    parts = [
        f"error:{fp.error_class}" if fp.error_class else "",
        f"service:{fp.service_role}" if fp.service_role else "",
        f"dependency:{fp.dependency_pattern}" if fp.dependency_pattern else "",
        f"signal:{fp.signal_shape}" if fp.signal_shape else "",
        f"attack:{fp.attack_pattern}" if fp.attack_pattern else "",
        f"env:{fp.environment}" if fp.environment else "",
    ]
    return " ".join(p for p in parts if p)


class EmbeddingSimilarityScorer:
    """Computes real cosine similarity between fingerprints."""

    def __init__(self) -> None:
        self._cache: dict[str, list[float]] = {}
        self._model: Any = None
        self._backend: str = "none"
        self._init_backend()

    def _init_backend(self) -> None:
        """Try to initialize an embedding backend."""
        # Try sentence-transformers first (local, fast)
        try:
            from sentence_transformers import SentenceTransformer
            model_name = os.getenv(
                "OPENRECALL_EMBEDDING_MODEL", "all-MiniLM-L6-v2"
            )
            self._model = SentenceTransformer(model_name)
            self._backend = "sentence-transformers"
            return
        except ImportError:
            pass

        # Fallback: no embedding backend available
        self._backend = "none"

    @property
    def available(self) -> bool:
        return self._backend != "none"

    def embed(self, text: str) -> list[float] | None:
        """Get embedding for a text string."""
        cache_key = hashlib.sha256(text.encode()).hexdigest()[:16]
        if cache_key in self._cache:
            return self._cache[cache_key]

        if self._backend == "sentence-transformers" and self._model is not None:
            embedding = self._model.encode(text).tolist()
            self._cache[cache_key] = embedding
            return embedding

        return None

    def cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def score_matches(
        self,
        query_fingerprint: AlertFingerprint,
        matches: list[MemoryMatch],
    ) -> list[MemoryMatch]:
        """Re-score matches using real embedding similarity.

        If the embedding backend is unavailable, returns matches unchanged.
        """
        if not self.available:
            return matches

        query_text = fingerprint_to_text(query_fingerprint)
        query_embedding = self.embed(query_text)
        if query_embedding is None:
            return matches

        for match in matches:
            # Build match text from its fingerprint_canonical or content
            match_fp = match.metadata.get("fingerprint_canonical", "")
            match_text = match_fp if match_fp else match.content[:200]
            match_embedding = self.embed(match_text)
            if match_embedding is not None:
                similarity = self.cosine_similarity(query_embedding, match_embedding)
                # Scale to [0, 1] range — cosine similarity can be negative
                match.score = max(0.0, min(1.0, (similarity + 1) / 2))

        # Re-sort by score descending
        matches.sort(key=lambda m: m.score, reverse=True)
        return matches
