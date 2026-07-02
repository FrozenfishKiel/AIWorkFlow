from __future__ import annotations

import hashlib
import math
import re

TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9\u4e00-\u9fff\-]{2,}")


class HashEmbeddingService:
    """Creates deterministic dense vectors for local vector-style retrieval.

    This is intentionally lightweight so the current prototype can land a real
    retrieval pipeline without introducing a second external model dependency.
    Semantic normalization is expected to happen one layer earlier in the
    retrieval profile provider.
    """

    def __init__(self, *, dimension: int = 128) -> None:
        self.dimension = dimension

    def embed_text(self, text: str) -> list[float]:
        """Embed text into a normalized dense vector using stable hashing."""

        features = [
            *self._extract_terms(text),
            *self._extract_char_ngrams(text),
        ]
        if not features:
            return [0.0] * self.dimension

        vector = [0.0] * self.dimension
        for feature in features:
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 1.5 if len(feature) > 6 else 1.0
            vector[index] += sign * weight

        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude == 0:
            return [0.0] * self.dimension
        return [value / magnitude for value in vector]

    def _extract_terms(self, text: str) -> list[str]:
        return [token.lower() for token in TOKEN_PATTERN.findall(text)]

    def _extract_char_ngrams(self, text: str) -> list[str]:
        normalized = "".join(character.lower() for character in text if not character.isspace())
        if len(normalized) < 3:
            return []
        return [normalized[index : index + 3] for index in range(len(normalized) - 2)]
