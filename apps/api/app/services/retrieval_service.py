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

LATIN_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9\-]{2,}")
CHINESE_TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,}")
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
        query_keywords = self._coerce_string_list(query_profile.get("keywords"))
        query_synonyms = self._coerce_string_list(query_profile.get("synonyms"))
        query_constraints = self._coerce_string_list(query_profile.get("constraints"))
        effective_constraints = [
            constraint
            for constraint in query_constraints
            if not (domain and constraint == domain)
        ]
        query_retrieval_text = self._compose_query_signal_text(
            base_text=str(query_profile.get("retrieval_text") or query_text),
            keywords=query_keywords,
            synonyms=query_synonyms,
            constraints=effective_constraints,
        )
        query_tokens = self._tokenize(f"{query_text}\n{query_retrieval_text}")
        query_terms = self._extract_terms(query_text)
        normalized_query_terms = self._extract_terms(query_retrieval_text)
        query_vector = self.embedding_service.embed_text(query_retrieval_text)
        if not query_tokens and self._is_zero_vector(query_vector):
            return []

        ranked_hits: list[tuple[tuple[float, float, float, float, float], dict[str, str | float | list[str]]]] = []
        for document, chunk in self.repository.list_indexed_chunks(domain=domain):
            ranking_text = chunk.retrieval_text or chunk.content
            visible_text = f"{document.title}\n{chunk.content}"
            match_text = f"{document.title}\n{ranking_text}\n{chunk.content}\n{document.domain}\n{document.source_type}"
            chunk_tokens = self._tokenize(match_text)
            overlap = sorted(query_tokens & chunk_tokens)
            title_tokens = self._tokenize(document.title)
            title_overlap = sorted(query_tokens & title_tokens)
            title_keyword_matches = self._match_raw_phrases(query_keywords, document.title)
            title_synonym_matches = self._match_raw_phrases(query_synonyms, document.title)
            title_constraint_matches = self._match_raw_phrases(effective_constraints, document.title)
            keyword_matches = self._match_raw_phrases(query_keywords, match_text)
            synonym_matches = self._match_raw_phrases(query_synonyms, match_text)
            constraint_matches = self._match_raw_phrases(
                effective_constraints,
                f"{document.domain}\n{document.source_type}\n{document.title}\n{ranking_text}",
            )
            semantic_phrase_matches = self._matching_phrases(
                normalized_query_terms,
                self._extract_terms(ranking_text),
            )
            title_phrase_matches = self._matching_phrases(
                query_terms or normalized_query_terms,
                self._extract_terms(document.title),
            ) or self._matching_phrases(normalized_query_terms, self._extract_terms(document.title))
            fact_card_types = {"product_fact_card", "category_fact_card"}
            fact_card_has_title_alignment = bool(
                title_phrase_matches
                or title_keyword_matches
                or title_synonym_matches
                or title_constraint_matches
            )
            if document.source_type in fact_card_types and not fact_card_has_title_alignment:
                continue
            vector_score = self._cosine_similarity(
                query_vector,
                chunk.embedding_vector or self.embedding_service.embed_text(ranking_text),
            )
            if vector_score <= 0 and not overlap and not title_overlap and not keyword_matches and not synonym_matches and not constraint_matches:
                continue
            content_phrase_matches = self._matching_phrases(
                query_terms or normalized_query_terms,
                self._extract_terms(chunk.content),
            ) or self._matching_phrases(normalized_query_terms, self._extract_terms(chunk.content))
            phrase_score = len(content_phrase_matches)
            title_phrase_score = len(title_phrase_matches)
            overlap_score = len(overlap)
            title_overlap_score = len(title_overlap)
            keyword_score = len(keyword_matches)
            synonym_score = len(synonym_matches)
            constraint_score = len(constraint_matches)
            title_keyword_score = len(title_keyword_matches)
            title_synonym_score = len(title_synonym_matches)
            title_constraint_score = len(title_constraint_matches)
            density_score = overlap_score / max(len(chunk_tokens), 1)
            source_type_score = 0.0
            if document.source_type in fact_card_types and fact_card_has_title_alignment:
                source_type_score = 6.0

            total_score = (
                vector_score * 10
                + title_phrase_score * 4
                + phrase_score * 3
                + title_overlap_score * 2
                + title_keyword_score * 2
                + title_synonym_score * 2.5
                + title_constraint_score * 5
                + keyword_score * 3.5
                + synonym_score * 4.5
                + constraint_score * 3.5
                + overlap_score
                + density_score
                + source_type_score
            )
            ranking_key = (
                total_score,
                title_constraint_score + title_synonym_score,
                synonym_score + constraint_score,
                title_phrase_score + title_overlap_score,
                phrase_score + overlap_score,
            )
            reason_parts = [f"命中《{document.title}》"]
            if title_phrase_matches:
                reason_parts.append(f"标题直接覆盖“{title_phrase_matches[0]}”")
            elif title_constraint_matches:
                reason_parts.append(f"标题直接对应“{title_constraint_matches[0]}”")
            elif title_synonym_matches:
                reason_parts.append(f"标题直接对应“{title_synonym_matches[0]}”")
            elif title_overlap:
                reason_parts.append(f"标题包含“{', '.join(title_overlap[:3])}”")
            if keyword_matches:
                reason_parts.append(f"关键信号命中“{', '.join(keyword_matches[:3])}”")
            if synonym_matches:
                reason_parts.append(f"扩展表达对齐“{', '.join(synonym_matches[:3])}”")
            if constraint_matches:
                reason_parts.append(f"检索约束匹配“{', '.join(constraint_matches[:3])}”")
            if semantic_phrase_matches and vector_score >= 0.85:
                reason_parts.append(f"检索画像对齐“{semantic_phrase_matches[0]}”")
            content_excerpt = self._best_excerpt(query_tokens, chunk.content)
            if content_excerpt:
                reason_parts.append(f"核心内容提到“{content_excerpt}”")
            elif content_phrase_matches:
                reason_parts.append(f"正文重点提到“{content_phrase_matches[0]}”")
            elif overlap:
                reason_parts.append(f"正文包含“{', '.join(overlap[:3])}”")
            if document.domain and not (keyword_matches or synonym_matches or constraint_matches):
                reason_parts.append(f"属于 {document.domain} 资料域")
            ranked_hits.append(
                (
                    ranking_key,
                    {
                        "source_id": str(document.id),
                        "title": document.title,
                        "snippet": chunk.content[:280],
                        "reason": "；".join(reason_parts) + "。",
                        "score": total_score,
                        "matched_terms": self._dedupe_preserve_order([*keyword_matches[:4], *synonym_matches[:4], *overlap[:8]]),
                        "matched_phrases": self._dedupe_preserve_order(
                            [*title_phrase_matches[:2], *content_phrase_matches[:2], *constraint_matches[:2]]
                        ),
                        "visible_text": visible_text[:400],
                        "source_type": document.source_type,
                        "domain": document.domain,
                    },
                )
            )

        ranked_hits.sort(key=lambda item: item[0], reverse=True)

        deduped_hits: list[dict[str, str]] = []
        seen_source_ids: set[str] = set()
        for _, hit in ranked_hits:
            source_id = str(hit["source_id"])
            if source_id in seen_source_ids:
                continue
            seen_source_ids.add(source_id)
            deduped_hits.append(hit)
            if len(deduped_hits) >= top_k:
                break

        return deduped_hits

    def _tokenize(self, text: str) -> set[str]:
        """Extract comparable lexical tokens for the lightweight Phase 1 ranker."""

        return set(self._extract_terms(text))

    def _extract_terms(self, text: str) -> list[str]:
        """Return normalized lexical terms while preserving their original order."""

        latin_terms = [self._normalize_token(token) for token in LATIN_TOKEN_PATTERN.findall(text)]
        chinese_terms: list[str] = []
        for sequence in CHINESE_TOKEN_PATTERN.findall(text):
            chinese_terms.extend(self._extract_chinese_terms(sequence))
        return [*latin_terms, *chinese_terms]

    def _extract_chinese_terms(self, sequence: str) -> list[str]:
        if len(sequence) <= 3:
            return [sequence]

        terms: list[str] = []
        max_window = 3
        for window_size in range(2, max_window + 1):
            for index in range(len(sequence) - window_size + 1):
                terms.append(sequence[index : index + window_size])
        return terms

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

    def _matching_phrases(self, query_terms: list[str], chunk_terms: list[str]) -> list[str]:
        """Return matched multi-term phrases shared by query and chunk."""

        if not query_terms or not chunk_terms:
            return []

        chunk_phrases = {
            " ".join(chunk_terms[index : index + window_size])
            for window_size in (5, 4, 3, 2)
            for index in range(len(chunk_terms) - window_size + 1)
        }
        matched: list[str] = []
        for window_size in (5, 4, 3, 2):
            for index in range(len(query_terms) - window_size + 1):
                phrase = " ".join(query_terms[index : index + window_size])
                if phrase in chunk_phrases and phrase not in matched:
                    matched.append(phrase)
        return matched

    def _match_raw_phrases(self, phrases: list[str], text: str) -> list[str]:
        normalized_text = text.lower()
        matched: list[str] = []
        for phrase in phrases:
            candidate = str(phrase).strip()
            if not candidate:
                continue
            if candidate.lower() in normalized_text and candidate not in matched:
                matched.append(candidate)
        return matched

    def _compose_query_signal_text(
        self,
        *,
        base_text: str,
        keywords: list[str],
        synonyms: list[str],
        constraints: list[str],
    ) -> str:
        parts = [base_text.strip()]
        if keywords:
            parts.append(" ".join(keywords))
        if synonyms:
            parts.append(" ".join(synonyms))
        if constraints:
            parts.append(" ".join(constraints))
        return "\n".join(part for part in parts if part)

    def _coerce_string_list(self, value: object) -> list[str]:
        if isinstance(value, list):
            return self._dedupe_preserve_order([str(item).strip() for item in value if str(item).strip()])
        if value is None:
            return []
        cleaned = str(value).strip()
        return [cleaned] if cleaned else []

    def _dedupe_preserve_order(self, items: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for item in items:
            cleaned = str(item).strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            deduped.append(cleaned)
        return deduped

    def _best_excerpt(self, query_tokens: set[str], content: str) -> str:
        """Return the strongest human-readable sentence excerpt for the reason field."""

        sentences = [
            sentence.strip()
            for sentence in re.split(r"[。！？；.!?]\s*", content)
            if sentence.strip()
        ]
        if not sentences:
            return ""

        scored_sentences: list[tuple[int, str]] = []
        for sentence in sentences:
            sentence_tokens = self._tokenize(sentence)
            overlap_count = len(query_tokens & sentence_tokens)
            if overlap_count > 0:
                scored_sentences.append((overlap_count, sentence))

        if not scored_sentences:
            return ""

        scored_sentences.sort(key=lambda item: (item[0], len(item[1])), reverse=True)
        top_score = scored_sentences[0][0]
        excerpts = [
            sentence[:40]
            for score, sentence in scored_sentences
            if score == top_score
        ][:2]
        return " / ".join(excerpts)

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
