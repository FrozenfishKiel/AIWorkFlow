from __future__ import annotations

import re

from app.repositories.knowledge_repository import KnowledgeRepository

TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9\-]{3,}")


class RetrievalService:
    """Performs a lightweight but reviewer-visible retrieval over knowledge chunks.

    This is still not target-state embedding retrieval. The current goal is to
    make lexical retrieval less naive by combining a few deterministic signals
    so the project can surface retrieval quality problems more honestly.
    """

    def __init__(self, repository: KnowledgeRepository) -> None:
        self.repository = repository

    def retrieve(self, query_text: str, *, top_k: int = 3, domain: str | None = None) -> list[dict[str, str]]:
        """Return visible retrieval hits using deterministic lexical overlap.

        The ranking is deliberately simple for now, but the output contract is
        already treated as stable by review, persistence, and frontend display:
        every hit needs a source id, title, snippet, and human-readable reason.
        """

        query_tokens = self._tokenize(query_text)
        if not query_tokens:
            return []

        ranked_hits: list[tuple[float, dict[str, str]]] = []
        for document, chunk in self.repository.list_indexed_chunks(domain=domain):
            chunk_tokens = self._tokenize(chunk.content)
            overlap = sorted(query_tokens & chunk_tokens)
            if not overlap:
                continue
            phrase_score = self._phrase_score(query_text, chunk.content)
            overlap_score = len(overlap)
            density_score = overlap_score / max(len(chunk_tokens), 1)
            total_score = phrase_score * 3 + overlap_score + density_score
            ranked_hits.append(
                (
                    total_score,
                    {
                        "source_id": str(document.id),
                        "title": document.title,
                        "snippet": chunk.content[:280],
                        "reason": (
                            f"Matched domain '{document.domain}' with score {total_score:.2f}; "
                            f"overlapping terms: {', '.join(overlap[:5])}."
                        ),
                    },
                )
            )

        ranked_hits.sort(key=lambda item: item[0], reverse=True)
        return [hit for _, hit in ranked_hits[:top_k]]

    def _tokenize(self, text: str) -> set[str]:
        """Extract comparable lexical tokens for the lightweight Phase 1 ranker."""

        return {token.lower() for token in TOKEN_PATTERN.findall(text)}

    def _phrase_score(self, query_text: str, chunk_text: str) -> int:
        """Reward short multi-token phrases that survive between query and chunk."""

        query_terms = [token.lower() for token in TOKEN_PATTERN.findall(query_text)]
        chunk_lower = chunk_text.lower()
        score = 0
        for window_size in (4, 3, 2):
            for index in range(len(query_terms) - window_size + 1):
                phrase = " ".join(query_terms[index : index + window_size])
                if phrase in chunk_lower:
                    score += 1
        return score
