"""Local lexical test doubles. These do not establish Google embedding quality."""

import hashlib
import math
import re
from collections import Counter
from typing import Literal

from terramind.rag.contracts import DIMENSIONS, IndexedChunk, Vector, unit_vector

STOP_WORDS = frozenset(
    [
        "a",
        "an",
        "the",
        "and",
        "or",
        "to",
        "of",
        "for",
        "in",
        "on",
        "with",
        "as",
        "is",
        "are",
        "be",
        "from",
        "that",
        "this",
        "it",
        "by",
        "how",
        "what",
        "should",
        "can",
        "do",
        "does",
        "which",
        "where",
        "when",
        "was",
        "were",
        "its",
        "intended",
        "review",
        "synthetic",
        "fabricated",
        "training",
        "runbook",
        "exercise",
        "find",
        "proposed",
    ]
)


class LexicalTestEmbedder:
    model_id = "local-lexical-test-double"

    def embed(self, text: str, *, task: Literal["document", "query"], title: str = "") -> Vector:
        vector = [0.0] * DIMENSIONS
        words = Counter(re.findall(r"[a-z0-9]+", f"{title} {text}".lower()))
        for word, count in words.items():
            if word in STOP_WORDS:
                continue
            slot = int.from_bytes(hashlib.sha256(word.encode()).digest()[:4]) % DIMENSIONS
            vector[slot] += 1 + math.log(count)
        return unit_vector(tuple(vector))


class MemoryKnowledgeStore:
    def __init__(self) -> None:
        self.records: tuple[IndexedChunk, ...] = ()
        self.writes = 0

    def snapshot(self) -> tuple[IndexedChunk, ...]:
        return self.records

    def synchronize(self, desired: tuple[IndexedChunk, ...]) -> None:
        self.records = desired
        self.writes += 1

    def nearest(self, vector: Vector, *, limit: int) -> tuple[IndexedChunk, ...]:
        return tuple(
            sorted(
                self.records,
                key=lambda record: (
                    -sum(a * b for a, b in zip(record.embedding, vector, strict=True)),
                    record.chunk.chunk_id,
                ),
            )[:limit]
        )
