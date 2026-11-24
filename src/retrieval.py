from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI
from rank_bm25 import BM25Okapi

import ssl_bootstrap  # noqa: F401


ROOT = Path(__file__).resolve().parents[1]
CHUNK_FILE = ROOT / "data" / "chunks.jsonl"
INDEX_DIR = ROOT / "index"
EMBEDDING_MODEL = "text-embedding-3-small"


def load_chunks() -> list[dict]:
    return [
        json.loads(line)
        for line in CHUNK_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def tokenize(text: str) -> list[str]:
    stopwords = {
        "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
        "had", "has", "have", "he", "her", "hers", "him", "his", "i", "in", "is",
        "it", "its", "me", "my", "of", "on", "or", "our", "she", "so", "that",
        "the", "their", "them", "then", "there", "these", "they", "this", "to",
        "was", "we", "were", "what", "when", "where", "which", "who", "will",
        "with", "would", "you", "your",
    }
    tokens = "".join(char.lower() if char.isalnum() else " " for char in text).split()
    return [token for token in tokens if token not in stopwords]


class Retriever:
    def __init__(self, chunks: list[dict] | None = None, embeddings: np.ndarray | None = None) -> None:
        self.chunks = chunks if chunks is not None else load_chunks()
        self.bm25 = BM25Okapi([
            tokenize(
                chunk["title"] + " " + chunk["section"] + " " + chunk["text"]
            )
            for chunk in self.chunks
        ])
        self._embeddings = embeddings
        self._client: OpenAI | None = None
        self.query_embedding_tokens = 0

    @property
    def embeddings(self) -> np.ndarray:
        if self._embeddings is None:
            self._embeddings = np.load(INDEX_DIR / "embeddings.npy")
        return self._embeddings

    @property
    def client(self) -> OpenAI:
        # Created on first use so BM25-only code paths and tests need no API key.
        if self._client is None:
            load_dotenv(ROOT / ".env", override=True)
            self._client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        return self._client

    def _embed_query(self, query: str) -> np.ndarray:
        response = self.client.embeddings.create(model=EMBEDDING_MODEL, input=query)
        self.query_embedding_tokens += response.usage.total_tokens
        return np.asarray(response.data[0].embedding, dtype=np.float32)

    def bm25_search(self, query: str, k: int = 3) -> list[dict]:
        scores = self.bm25.get_scores(tokenize(query))
        ranked = np.argsort(-scores)[:k]
        return [dict(self.chunks[index], score=float(scores[index])) for index in ranked]

    def embedding_search(self, query: str, k: int = 3) -> list[dict]:
        query_embedding = self._embed_query(query)
        norms = np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(query_embedding)
        scores = (self.embeddings @ query_embedding) / np.where(norms == 0, 1, norms)
        ranked = np.argsort(-scores)[:k]
        return [dict(self.chunks[index], score=float(scores[index])) for index in ranked]

    def hybrid_search(self, query: str, k: int = 3, rrf_k: int = 60) -> list[dict]:
        bm25_count = min(len(self.chunks), max(k * 4, 20))
        bm25_scores = self.bm25.get_scores(tokenize(query))
        bm25_ranked = np.argsort(-bm25_scores)[:bm25_count]

        query_embedding = self._embed_query(query)
        norms = np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(query_embedding)
        embedding_scores = (self.embeddings @ query_embedding) / np.where(norms == 0, 1, norms)
        embedding_ranked = np.argsort(-embedding_scores)[:bm25_count]

        fused: dict[int, float] = {}
        for rank, index in enumerate(bm25_ranked):
            fused[int(index)] = fused.get(int(index), 0.0) + 1.0 / (rrf_k + rank + 1)
        for rank, index in enumerate(embedding_ranked):
            fused[int(index)] = fused.get(int(index), 0.0) + 1.0 / (rrf_k + rank + 1)

        ranked = sorted(fused, key=fused.get, reverse=True)[:k]
        return [dict(self.chunks[index], score=float(fused[index])) for index in ranked]


def build_embeddings() -> dict:
    load_dotenv(ROOT / ".env", override=True)
    chunks = load_chunks()
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    vectors: list[list[float]] = []
    total_tokens = 0

    for start in range(0, len(chunks), 100):
        batch = [chunk["text"][:8000] for chunk in chunks[start:start + 100]]
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        ordered = sorted(response.data, key=lambda item: item.index)
        vectors.extend([item.embedding for item in ordered])
        total_tokens += response.usage.total_tokens

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    np.save(INDEX_DIR / "embeddings.npy", np.asarray(vectors, dtype=np.float32))
    usage = {
        "model": EMBEDDING_MODEL,
        "input_tokens": total_tokens,
        "cost_usd": total_tokens * 0.020 / 1_000_000,
    }
    (INDEX_DIR / "embedding_usage.json").write_text(
        json.dumps(usage, indent=2),
        encoding="utf-8",
    )
    return usage


if __name__ == "__main__":
    print(json.dumps(build_embeddings(), indent=2))
