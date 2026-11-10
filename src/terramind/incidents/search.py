"""Transparent TF-IDF cosine matching over the packaged fabricated incidents."""

import hashlib
import math
import re
from collections import Counter
from typing import Annotated, Final, Literal

from pydantic import Field

from terramind.events.service import packaged_corpus
from terramind.rag.contracts import Digest, Document, Identifier
from terramind.rag.local import STOP_WORDS
from terramind.rag.retrieval import RULE_QUERIES
from terramind.schemas.normalized import ClosedModel
from terramind.schemas.report import Report

LABEL: Final = (
    "Synthetic tabletop incident, contextual similarity only; not evidence of a real incident."
)


class IncidentMatch(ClosedModel):
    doc_id: Identifier
    title: Annotated[str, Field(min_length=1, max_length=120)]
    source_path: Annotated[str, Field(pattern=r"^incidents/[a-z0-9-]+\.md$")]
    content_hash: Digest
    version: Annotated[str, Field(pattern=r"^[0-9]+\.[0-9]+$")]
    similarity: Annotated[float, Field(ge=0, le=1)]
    related_rules: tuple[str, ...] = Field(min_length=1, max_length=20)
    excerpt: Annotated[str, Field(min_length=1, max_length=600)]
    evidence_label: Literal[
        "Synthetic tabletop incident, contextual similarity only; not evidence of a real incident."
    ] = LABEL


class IncidentMemory(ClosedModel):
    schema_version: Literal["1.0"] = "1.0"
    method: Literal["local-tfidf-cosine"] = "local-tfidf-cosine"
    status: Literal["available", "not_requested", "partial"]
    matches: tuple[IncidentMatch, ...] = Field(max_length=5)
    limitations: tuple[str, ...]


def words(text: str) -> Counter[str]:
    return Counter(
        word for word in re.findall(r"[a-z0-9]+", text.lower()) if word not in STOP_WORDS
    )


class IncidentSearcher:
    def __init__(self, documents: tuple[Document, ...] | None = None):
        self.documents = tuple(
            document
            for document in (documents if documents is not None else packaged_corpus())
            if document.source_path.startswith("incidents/")
        )
        if not 1 <= len(self.documents) <= 12:
            raise ValueError("Incident memory requires a bounded synthetic incident corpus")
        if len({doc.doc_id for doc in self.documents}) != len(self.documents) or any(
            doc.content_hash != hashlib.sha256(doc.body.encode()).hexdigest()
            for doc in self.documents
        ):
            raise ValueError("Incident corpus integrity check failed")
        self.counts = [words(f"{doc.title} {doc.body}") for doc in self.documents]
        vocabulary = set().union(*(set(count) for count in self.counts))
        self.idf = {
            word: math.log((1 + len(self.documents)) / (1 + sum(word in c for c in self.counts)))
            + 1
            for word in vocabulary
        }
        self.vectors = [self._vector(count) for count in self.counts]

    def _vector(self, count: Counter[str]) -> dict[str, float]:
        weighted = {
            word: (1 + math.log(value)) * self.idf[word]
            for word, value in count.items()
            if word in self.idf
        }
        norm = math.sqrt(sum(value * value for value in weighted.values()))
        return {word: value / norm for word, value in weighted.items()} if norm else {}

    def search(self, report: Report, *, limit: int = 3) -> IncidentMemory:
        if not 1 <= limit <= 5:
            raise ValueError("Incident result limit must be between one and five")
        rules = sorted({finding.rule_id for finding in report.findings})
        queries = {
            rule: self._vector(words(RULE_QUERIES[rule])) for rule in rules if rule in RULE_QUERIES
        }
        matches = []
        for document, vector in zip(self.documents, self.vectors, strict=True):
            scores = {
                rule: sum(value * vector.get(word, 0) for word, value in query.items())
                for rule, query in queries.items()
            }
            related = tuple(rule for rule, score in scores.items() if score >= 0.08)
            if not related:
                continue
            matches.append(
                IncidentMatch(
                    doc_id=document.doc_id,
                    title=document.title,
                    source_path=document.source_path,
                    content_hash=document.content_hash,
                    version=document.version,
                    similarity=round(min(1.0, max(scores.values())), 6),
                    related_rules=related,
                    excerpt=document.body[:600],
                )
            )
        matches.sort(key=lambda item: (-item.similarity, item.doc_id))
        return IncidentMemory(
            status="not_requested"
            if not rules
            else "partial"
            if len(queries) != len(rules)
            else "available",
            matches=tuple(matches[:limit]),
            limitations=(
                LABEL,
                "Scores measure lexical overlap, not probability, causation or semantic proof.",
                "Only supported policy queries and the packaged fabricated corpus are searched.",
                "Incident similarity cannot remove, downgrade or approve policy findings.",
            ),
        )
