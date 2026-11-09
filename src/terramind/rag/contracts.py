"""Provider-independent contracts for synthetic evidence."""

import hashlib
import math
from typing import Annotated, Literal, Protocol

from pydantic import Field, field_validator, model_validator

from terramind.schemas.normalized import ClosedModel

DIMENSIONS = 768
MAX_CHUNKS = 128
Identifier = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{0,79}$")]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Text = Annotated[str, Field(min_length=1, max_length=3200)]
Vector = tuple[float, ...]


class Document(ClosedModel):
    doc_id: Identifier
    title: Annotated[str, Field(min_length=1, max_length=120)]
    version: Annotated[str, Field(pattern=r"^[0-9]+\.[0-9]+$")]
    source_path: Annotated[str, Field(pattern=r"^(runbooks|incidents)/[a-z0-9-]+\.md$")]
    content_hash: Digest
    synthetic: Literal[True] = True
    body: Annotated[str, Field(min_length=1, max_length=40000)]


class Chunk(ClosedModel):
    chunk_id: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    doc_id: Identifier
    title: Annotated[str, Field(min_length=1, max_length=120)]
    version: Annotated[str, Field(pattern=r"^[0-9]+\.[0-9]+$")]
    source_path: Annotated[str, Field(pattern=r"^(runbooks|incidents)/[a-z0-9-]+\.md$")]
    content_hash: Digest
    section_id: Identifier
    chunk_hash: Digest
    text: Text
    synthetic: Literal[True] = True

    @property
    def citation_id(self) -> str:
        return f"{self.doc_id}:{self.section_id}"

    @model_validator(mode="after")
    def verify_hashes(self) -> "Chunk":
        expected_id = hashlib.sha256(f"{self.doc_id}:{self.section_id}".encode()).hexdigest()
        if (
            self.chunk_id != expected_id
            or self.chunk_hash != hashlib.sha256(self.text.encode()).hexdigest()
        ):
            raise ValueError("Knowledge chunk integrity check failed")
        return self


class IndexedChunk(ClosedModel):
    chunk: Chunk
    embedding_model: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9.-]{0,79}$")]
    embedding: Annotated[Vector, Field(min_length=DIMENSIONS, max_length=DIMENSIONS)]

    @field_validator("embedding")
    @classmethod
    def validate_embedding(cls, value: Vector) -> Vector:
        return unit_vector(value)


def unit_vector(value: Vector) -> Vector:
    if len(value) != DIMENSIONS or not all(math.isfinite(x) for x in value):
        raise ValueError("Embedding must have 768 finite dimensions")
    norm = math.sqrt(sum(x * x for x in value))
    if not math.isfinite(norm) or norm < 1e-12:
        raise ValueError("Embedding must have nonzero finite magnitude")
    return value if abs(norm - 1) < 1e-9 else tuple(x / norm for x in value)


class Embedder(Protocol):
    @property
    def model_id(self) -> str: ...

    def embed(
        self, text: str, *, task: Literal["document", "query"], title: str = ""
    ) -> Vector: ...


class KnowledgeStore(Protocol):
    def snapshot(self) -> tuple[IndexedChunk, ...]: ...

    def synchronize(self, desired: tuple[IndexedChunk, ...]) -> None: ...

    def nearest(self, vector: Vector, *, limit: int) -> tuple[IndexedChunk, ...]: ...


class SourcePublisher(Protocol):
    def publish(self, documents: tuple[Document, ...]) -> None: ...
