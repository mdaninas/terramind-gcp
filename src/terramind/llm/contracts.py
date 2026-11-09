"""Closed, bounded output contracts for untrusted model text."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Annotated, Literal, Protocol

from pydantic import Field, field_validator

from terramind.rag.contracts import Chunk, Digest
from terramind.schemas.normalized import ClosedModel

if TYPE_CHECKING:
    from terramind.schemas.report import Finding

NarrativeText = Annotated[str, Field(min_length=1, max_length=1200)]
CitationId = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9:._-]{0,159}$")]
FindingId = Annotated[str, Field(pattern=r"^TM-GCP-00[1-4]:google_[a-z0-9_]+\.resource_[0-9]{4}$")]
RagStatus = Literal["available", "partial", "unavailable"]


class FindingExplanation(ClosedModel):
    finding_id: FindingId
    text: NarrativeText
    citation_ids: Annotated[tuple[CitationId, ...], Field(min_length=1, max_length=5)]

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        check_advisory_text(value)
        return value


class ModelNarrative(ClosedModel):
    summary: NarrativeText
    explanations: Annotated[tuple[FindingExplanation, ...], Field(min_length=1, max_length=100)]
    recommendations: Annotated[tuple[NarrativeText, ...], Field(min_length=1, max_length=8)]
    citations: Annotated[
        tuple[Annotated[str, Field(min_length=1, max_length=256)], ...],
        Field(min_length=1, max_length=12),
    ]
    limitations: Annotated[tuple[NarrativeText, ...], Field(max_length=8)]

    @field_validator("summary", "recommendations", "limitations")
    @classmethod
    def validate_text(cls, value: str | tuple[str, ...]) -> str | tuple[str, ...]:
        for text in (value,) if isinstance(value, str) else value:
            check_advisory_text(text)
        return value


def check_advisory_text(text: str) -> None:
    if not text.isascii() or any(ord(c) < 32 and c not in "\n\t" for c in text):
        raise ValueError("Advisory text must use plain English or Indonesian characters")
    # Defense in depth, not semantic proof. The immutable report owns severity.
    if re.search(
        r"\bSAFE\b|\bapproved\b|\bno (?:known )?(?:risks?|findings)\b|"
        r"-----BEGIN .*PRIVATE KEY|\bBearer\s+|\bya29\.|\bAIza[\w-]{20,}",
        text,
        re.I,
    ):
        raise ValueError("Advisory contains a forbidden assertion or credential marker")


class SourceCitation(ClosedModel):
    citation_id: CitationId
    chunk_id: Digest
    doc_id: str
    section_id: str
    title: str
    version: str
    source_path: str
    content_hash: Digest

    @classmethod
    def from_chunk(cls, chunk: Chunk) -> SourceCitation:
        return cls(**{key: getattr(chunk, key) for key in cls.model_fields})


class Advisory(ModelNarrative):
    citations: Annotated[tuple[CitationId, ...], Field(min_length=1, max_length=12)]
    model_id: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9.-]{0,79}$")]
    rag_status: RagStatus
    sources: Annotated[tuple[SourceCitation, ...], Field(min_length=1, max_length=12)]


class Synthesizer(Protocol):
    @property
    def model_id(self) -> str: ...

    def generate(self, prompt: str) -> str: ...


def finding_id(finding: Finding) -> str:
    return f"{finding.rule_id}:{finding.resource}"
