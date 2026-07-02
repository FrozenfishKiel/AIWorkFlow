from __future__ import annotations

import math
import re

from app.core.settings import get_settings
from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.embedding_service import HashEmbeddingService
from app.services.retrieval_profile_provider import (
    RetrievalProfileProvider,
    build_retrieval_profile_provider,
)

TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9\-]{3,}")
TOKEN_SYNONYMS = {
    "sign-off": "approval",
    "signoffs": "approval",
    "signoff": "approval",
    "externally": "public",
    "external": "public",
    "visible": "public",
}


class RetrievalService:
    """Performs a lightweight but reviewer-visible retrieval over knowledge chunks.

    The current implementation is a hybrid ranker:
    - vector-style similarity over normalized retrieval profiles
    - lexical/title/phrase signals as visible reviewer-facing tiebreakers
    """

    def __init__(
        self,
        repository: KnowledgeRepository,
        *,
        retrieval_profile_provider: RetrievalProfileProvider | None = None,
        embedding_service: HashEmbeddingService | None = None,
    ) -> None:
        self.repository = repository
        self.retrieval_profile_provider = retrieval_profile_provider or build_retrieval_profile_provider()
        settings = get_settings()
        self.embedding_service = embedding_service or HashEmbeddingService(
            dimension=settings.retrieval_embedding_dimension,
        )

    def retrieve(self, query_text: str, *, top_k: int = 3, domain: str | None = None) -> list[dict[str, str]]:
        """Return visible retrieval hits using deterministic lexical overlap.

        The ranking is deliberately simple for now, but the output contract is
        already treated as stable by review, persistence, and frontend display:
        every hit needs a source id, title, snippet, and human-readable reason.
        """

        query_profile = self.retrieval_profile_provider.build_query_profile(
            query_text=query_text,
            domain=domain,
        )
        query_retrieval_text = str(query_profile.get("retrieval_text") or query_text)
        query_tokens = self._tokenize(query_retrieval_text)
        query_vector = self.embedding_service.embed_text(query_retrieval_text)
        if not query_tokens and self._is_zero_vector(query_vector):
            return []

        ranked_hits: list[tuple[float, dict[str, str]]] = []
        for document, chunk in self.repository.list_indexed_chunks(domain=domain):
            ranking_text = chunk.retrieval_text or chunk.content
            chunk_tokens = self._tokenize(ranking_text)
            overlap = sorted(query_tokens & chunk_tokens)
            title_tokens = self._tokenize(document.title)
            title_overlap = sorted(query_tokens & title_tokens)
            vector_score = self._cosine_similarity(
                query_vector,
                chunk.embedding_vector or self.embedding_service.embed_text(ranking_text),
            )
            if vector_score <= 0 and not overlap and not title_overlap:
                continue
            phrase_score = self._phrase_score(query_retrieval_text, ranking_text)
            title_phrase_score = self._phrase_score(query_retrieval_text, document.title)
            overlap_score = len(overlap)
            title_overlap_score = len(title_overlap)
            density_score = overlap_score / max(len(chunk_tokens), 1)
            total_score = (
                vector_score * 10
                + title_phrase_score * 4
                + phrase_score * 3
                + title_overlap_score * 2
                + overlap_score
                + density_score
            )
            reason_parts = [
                f"Matched domain '{document.domain}' with score {total_score:.2f}",
                f"vector score {vector_score:.3f}",
            ]
            if title_overlap:
                reason_parts.append(f"title signals: {', '.join(title_overlap[:5])}")
            if overlap:
                reason_parts.append(f"content overlap: {', '.join(overlap[:5])}")
            ranked_hits.append(
                (
                    total_score,
                    {
                        "source_id": str(document.id),
                        "title": document.title,
                        "snippet": chunk.content[:280],
                        "reason": "; ".join(reason_parts) + ".",
                    },
                )
            )

        ranked_hits.sort(key=lambda item: item[0], reverse=True)
        return [hit for _, hit in ranked_hits[:top_k]]

    def _tokenize(self, text: str) -> set[str]:
        """Extract comparable lexical tokens for the lightweight Phase 1 ranker."""

        return set(self._extract_terms(text))

    def _extract_terms(self, text: str) -> list[str]:
        """Return normalized lexical terms while preserving their original order."""

        return [self._normalize_token(token) for token in TOKEN_PATTERN.findall(text)]

    def _normalize_token(self, token: str) -> str:
        """Apply minimal lexical normalization without pretending to do semantic RAG.

        This keeps the Phase 1 ranker intentionally lightweight while removing a
        few high-frequency reviewer pain points such as simple plural forms and
        a tiny approval/sign-off vocabulary mismatch.
        """

        normalized = token.lower()
        normalized = TOKEN_SYNONYMS.get(normalized, normalized)

        if normalized.endswith("ies") and len(normalized) > 4:
            normalized = normalized[:-3] + "y"
        elif normalized.endswith("s") and len(normalized) > 4 and not normalized.endswith("ss"):
            normalized = normalized[:-1]

        return TOKEN_SYNONYMS.get(normalized, normalized)

    def _phrase_score(self, query_text: str, chunk_text: str) -> int:
        """Reward short multi-token phrases that survive between query and chunk."""

        query_terms = self._extract_terms(query_text)
        chunk_terms = self._extract_terms(chunk_text)
        chunk_phrases = {
            " ".join(chunk_terms[index : index + window_size])
            for window_size in (4, 3, 2)
            for index in range(len(chunk_terms) - window_size + 1)
        }
        score = 0
        for window_size in (4, 3, 2):
            for index in range(len(query_terms) - window_size + 1):
                phrase = " ".join(query_terms[index : index + window_size])
                if phrase in chunk_phrases:
                    score += 1
        return score

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        """Return cosine similarity for two embedding vectors."""

        if not left or not right or len(left) != len(right):
            return 0.0
        numerator = sum(left_value * right_value for left_value, right_value in zip(left, right, strict=False))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return numerator / (left_norm * right_norm)

    def _is_zero_vector(self, vector: list[float]) -> bool:
        return not vector or all(value == 0 for value in vector)
