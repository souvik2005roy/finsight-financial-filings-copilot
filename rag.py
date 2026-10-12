"""RAG: page-aware document chunks, BM25/vector retrieval, RRF and cited answers.

This module is designed for FinSight. PDF page numbers are 1-based PDF page
positions, which may differ from the printed page numbers inside a report.
"""

from __future__ import annotations

import glob
import os
import re
from typing import Iterable

import numpy as np
from pypdf import PdfReader
from rank_bm25 import BM25Okapi

from llm import ask_llm


DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
RRF_K = 60
RRF_DEPTH = 60
# Weighted RRF: favor exact-term matching while retaining semantic recall.
# Configure through environment variables if a later evaluation justifies it.
BM25_RRF_WEIGHT = float(os.getenv("FINSIGHT_BM25_RRF_WEIGHT", "2.0"))
VECTOR_RRF_WEIGHT = float(os.getenv("FINSIGHT_VECTOR_RRF_WEIGHT", "1.0"))


def chunk(text: str, size: int = 700, overlap: int = 120) -> list[str]:
    """Split text into overlapping character chunks, skipping empty text."""
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("Require size > 0 and 0 <= overlap < size")

    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []

    step = size - overlap
    return [text[i : i + size] for i in range(0, len(text), step)]


def tokens(text: str) -> list[str]:
    """Simple lowercase tokenizer used by BM25."""
    return re.findall(r"[a-z0-9]+", (text or "").lower())


class Retriever:
    """Load PDF/TXT documents and retrieve relevant chunks with citations."""

    def __init__(self, docs_dir: str = "data/docs"):
        self.docs_dir = docs_dir

        # Parallel lists: item i in each list describes the same chunk.
        self.chunks: list[str] = []
        self.sources: list[str] = []
        self.pages: list[int | None] = []
        self.chunk_ids: list[str] = []

        paths = sorted(glob.glob(os.path.join(docs_dir, "*")))
        for path in paths:
            if not os.path.isfile(path):
                continue

            extension = os.path.splitext(path)[1].lower()
            source = os.path.basename(path)

            if extension == ".pdf":
                reader = PdfReader(path)
                for page_number, page in enumerate(reader.pages, start=1):
                    page_text = page.extract_text() or ""
                    self._add_text_chunks(page_text, source, page_number)
            elif extension == ".txt":
                with open(path, "r", encoding="utf-8", errors="replace") as file:
                    self._add_text_chunks(file.read(), source, None)
            # Unsupported extensions are deliberately ignored.

        if not self.chunks:
            raise ValueError(
                f"No extractable .pdf or .txt text found in {docs_dir!r}. "
                "Add a document or check its text extraction."
            )

        tokenized_chunks = [tokens(text) for text in self.chunks]
        self.bm25 = BM25Okapi(tokenized_chunks)

        # SentenceTransformer and document vectors are loaded lazily. BM25-only
        # retrieval therefore does not require an embedding-model download.
        self._embedder = None
        self._vectors = None

    def _add_text_chunks(
        self, text: str, source: str, page_number: int | None
    ) -> None:
        for chunk_number, content in enumerate(chunk(text), start=1):
            if not content.strip():
                continue

            self.chunks.append(content)
            self.sources.append(source)
            self.pages.append(page_number)

            page_tag = f"p{page_number:04d}" if page_number is not None else "pNA"
            self.chunk_ids.append(f"{source}:{page_tag}:c{chunk_number:04d}")

    def citation_for(self, idx: int) -> str:
        """Return a citation label using the source filename and PDF page."""
        source = self.sources[idx]
        page_number = self.pages[idx]
        if page_number is None:
            return f"[{source}]"
        return f"[{source}, PDF page {page_number}]"

    def _vec(self):
        """Load the local embedding model and encode all chunks once."""
        if self._vectors is None:
            from sentence_transformers import SentenceTransformer

            model_name = os.getenv("FINSIGHT_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
            self._embedder = SentenceTransformer(model_name)
            self._vectors = self._embedder.encode(
                self.chunks,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
        return self._embedder, self._vectors

    def search(
        self, query: str, k: int = 4, mode: str = "hybrid",
        diversify_pages: bool = False,
    ) -> list[int]:
        """Return ranked chunk indices using BM25, vector search, or RRF fusion.

        Modes:
          - ``bm25``: lexical keyword retrieval only.
          - ``vector``: semantic embedding retrieval only.
          - ``hybrid``: Reciprocal Rank Fusion of BM25 and vector rankings.
        """
        if mode not in ("vector", "bm25", "hybrid"):
            raise ValueError("mode must be 'vector', 'bm25', or 'hybrid'")
        if not isinstance(k, int):
            raise TypeError("k must be an integer")
        if k <= 0 or not (query or "").strip():
            return []

        # Diversified searches need a wider candidate pool before selecting
        # unique pages. Normal searches preserve the requested top-k behavior.
        candidate_k = max(20, k * 5) if diversify_pages else k
        rankings: dict[str, list[int]] = {}

        if mode in ("vector", "hybrid"):
            embedder, vectors = self._vec()
            query_vector = embedder.encode(
                query,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            scores = vectors @ query_vector
            rankings["vector"] = np.argsort(scores)[::-1].tolist()

        if mode in ("bm25", "hybrid"):
            scores = self.bm25.get_scores(tokens(query))
            rankings["bm25"] = np.argsort(scores)[::-1].tolist()

        if mode != "hybrid":
            ranked = rankings[mode]
            if diversify_pages:
                return self.diversify_pages(ranked[:candidate_k], k)
            return ranked[:k]

        # Chunk-level weighted Reciprocal Rank Fusion. This remains the baseline
        # ranking when diversify_pages=False, so we can compare it fairly.
        chunk_fused_scores: dict[int, float] = {}
        weights = {
            "bm25": BM25_RRF_WEIGHT,
            "vector": VECTOR_RRF_WEIGHT,
        }
        for method, ranking in rankings.items():
            weight = weights[method]
            for rank, idx in enumerate(ranking[:RRF_DEPTH], start=1):
                chunk_fused_scores[idx] = (
                    chunk_fused_scores.get(idx, 0.0)
                    + weight / (RRF_K + rank)
                )

        ranked = sorted(
            chunk_fused_scores,
            key=chunk_fused_scores.get,
            reverse=True,
        )
        if not diversify_pages:
            return ranked[:k]

        # Page-level fusion avoids allowing multiple overlapping chunks from
        # the same report page to consume the context window. For each retrieval
        # method, a page contributes only its best (lowest) chunk rank.
        page_best_ranks: dict[str, dict[tuple[str, object], int]] = {}
        page_candidates: dict[tuple[str, object], list[int]] = {}

        for method, ranking in rankings.items():
            best_for_method: dict[tuple[str, object], int] = {}
            for rank, idx in enumerate(ranking[:RRF_DEPTH], start=1):
                page = self.pages[idx]
                page_key = (
                    self.sources[idx],
                    page if page is not None else self.chunk_ids[idx],
                )
                best_for_method.setdefault(page_key, rank)
                candidates = page_candidates.setdefault(page_key, [])
                if idx not in candidates:
                    candidates.append(idx)
            page_best_ranks[method] = best_for_method

        page_scores: dict[tuple[str, object], float] = {}
        for method, best_ranks in page_best_ranks.items():
            weight = weights[method]
            for page_key, rank in best_ranks.items():
                page_scores[page_key] = (
                    page_scores.get(page_key, 0.0)
                    + weight / (RRF_K + rank)
                )

        ranked_pages = sorted(
            page_scores,
            key=page_scores.get,
            reverse=True,
        )

        # Pick the strongest individual chunk from each selected page, using
        # the chunk-level RRF score, while retaining the page-level order.
        selected: list[int] = []
        for page_key in ranked_pages:
            candidates = page_candidates[page_key]
            representative = max(
                candidates,
                key=lambda idx: chunk_fused_scores.get(idx, 0.0),
            )
            selected.append(representative)
            if len(selected) >= k:
                return selected

        return selected

    def diversify_pages(self, indexes: Iterable[int], k: int) -> list[int]:
        """Choose unique PDF pages first, then fill any remaining slots.

        This is intentionally applied after retrieval so BM25/vector/hybrid
        evaluation rankings remain available without page-diversity changes.
        For TXT files without page metadata, chunks are treated as distinct
        units because their original page locations are unknown.
        """
        if k <= 0:
            return []

        ranked = list(indexes)
        selected: list[int] = []
        seen_pages: set[tuple[str, object]] = set()

        for idx in ranked:
            page = self.pages[idx]
            if page is None:
                page_key: tuple[str, object] = (self.sources[idx], self.chunk_ids[idx])
            else:
                page_key = (self.sources[idx], page)

            if page_key in seen_pages:
                continue

            selected.append(idx)
            seen_pages.add(page_key)
            if len(selected) >= k:
                return selected

        # Not enough distinct pages: preserve ranking order for remaining slots.
        selected_set = set(selected)
        for idx in ranked:
            if idx not in selected_set:
                selected.append(idx)
                selected_set.add(idx)
            if len(selected) >= k:
                break

        return selected


def rag_answer(
    question: str,
    retriever: Retriever,
    mode: str = "hybrid",
    k: int = 4,
) -> tuple[str, list[str], str]:
    """Return answer, citations, and plain-text evidence for the number checker.

    Retrieve a wider candidate pool, then select up to ``k`` chunks while
    preferring distinct source pages. This reduces duplicate-page context and
    improves the chance that multiple relevant disclosures reach the LLM.
    """
    if k <= 0:
        raise ValueError("k must be greater than zero")

    # For hybrid retrieval, diversify_pages=True performs page-level RRF so
    # one page cannot crowd out other relevant report pages with overlapping
    # chunks. BM25/vector modes also select distinct pages from a wider pool.
    indexes = retriever.search(question, k, mode, diversify_pages=True)

    if not indexes:
        return "Not in the documents.", [], ""

    prompt_context = "\n\n".join(
        f"{retriever.citation_for(idx)}\n{retriever.chunks[idx]}"
        for idx in indexes
    )

    # Exclude citation/page metadata from checker evidence: page numbers must
    # not be mistaken for financial numbers supporting the answer.
    evidence = "\n\n".join(retriever.chunks[idx] for idx in indexes)

    prompt = f"""Answer using ONLY the context below. If the answer is not there, say \"Not in the documents\".
Cite each material factual claim using the exact source label shown at the start of its context block, for example [filename.pdf, PDF page 23].
For .txt sources, cite the exact filename label, for example [filename.txt].
Use the supplied PDF page number (1-based PDF page order), not a printed page number that may appear in the document. Never invent facts, figures, page numbers, or citations. If the context does not support a detail, state that the report excerpts provided do not establish it.

Context:
{prompt_context}

Question: {question}"""

    answer = ask_llm(prompt)
    sources = sorted({retriever.citation_for(idx) for idx in indexes})
    return answer, sources, evidence
