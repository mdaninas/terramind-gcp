"""Validate storage events and stage idempotent ingestion behind a fenced lease."""

import hashlib
import re
from contextlib import suppress
from dataclasses import dataclass
from importlib.resources import files
from typing import Literal, Protocol

from pydantic import TypeAdapter

from terramind.errors import InputError
from terramind.rag.contracts import Document, Embedder, IndexedChunk
from terramind.rag.ingestion import IngestionResult, ingest

EVENT_TYPE = "google.cloud.storage.object.v1.finalized"


class IndexingBusy(RuntimeError):
    """Another worker owns the corpus lease; retry this event later."""


@dataclass(frozen=True)
class StorageEvent:
    bucket: str
    name: str
    generation: int

    @classmethod
    def parse(cls, headers: dict[str, str], data: dict[str, object], bucket: str) -> "StorageEvent":
        name, generation = data.get("name"), data.get("generation")
        if (
            headers.get("ce-specversion") != "1.0"
            or headers.get("ce-type") != EVENT_TYPE
            or headers.get("ce-source") != f"//storage.googleapis.com/projects/_/buckets/{bucket}"
            or not re.fullmatch(r"[A-Za-z0-9._:-]{1,200}", headers.get("ce-id", ""))
            or data.get("bucket") != bucket
            or not isinstance(name, str)
            or len(name) > 256
            or headers.get("ce-subject") != f"objects/{name}"
            or not isinstance(generation, str)
            or not re.fullmatch(r"[1-9][0-9]{0,19}", generation)
        ):
            raise InputError("Invalid storage event envelope")
        return cls(bucket, name, int(generation))


@dataclass(frozen=True)
class Lease:
    key: str
    owner: str


class SourceReader(Protocol):
    def read(self, event: StorageEvent) -> bytes: ...


class IndexCoordinator(Protocol):
    def claim(self, key: str) -> Lease | None: ...
    def snapshot(self) -> tuple[IndexedChunk, ...]: ...
    def commit(
        self, lease: Lease, before: tuple[IndexedChunk, ...], desired: tuple[IndexedChunk, ...]
    ) -> None: ...
    def release(self, lease: Lease) -> None: ...


class StagedStore:
    def __init__(self, existing: tuple[IndexedChunk, ...]):
        self.existing = existing
        self.desired = existing

    def snapshot(self) -> tuple[IndexedChunk, ...]:
        return self.existing

    def synchronize(self, desired: tuple[IndexedChunk, ...]) -> None:
        self.desired = desired

    def nearest(self, vector: tuple[float, ...], *, limit: int) -> tuple[IndexedChunk, ...]:
        raise NotImplementedError("The ingestion staging store does not serve queries")


def packaged_corpus() -> tuple[Document, ...]:
    raw = files("terramind.events").joinpath("assets/corpus.json").read_bytes()
    return TypeAdapter(tuple[Document, ...]).validate_json(raw)


@dataclass(frozen=True)
class EventResult:
    status: Literal["indexed", "duplicate", "ignored"]
    ingestion: IngestionResult | None = None


class EventIndexer:
    def __init__(
        self,
        documents: tuple[Document, ...],
        embedder: Embedder,
        reader: SourceReader,
        coordinator: IndexCoordinator,
    ):
        self.documents, self.embedder = documents, embedder
        self.reader, self.coordinator = reader, coordinator
        self.sources = {f"sources/{doc.doc_id}/{doc.content_hash}.md": doc for doc in documents}
        manifest = "\n".join(sorted(doc.model_dump_json() for doc in documents))
        self.revision = hashlib.sha256((embedder.model_id + "\n" + manifest).encode()).hexdigest()

    def handle(self, event: StorageEvent) -> EventResult:
        document = self.sources.get(event.name)
        if document is None:
            # Old revisions, unrelated uploads and arbitrary object paths do not cause SDK calls.
            return EventResult("ignored")
        key = hashlib.sha256(
            f"{self.revision}:{event.bucket}:{event.name}:{event.generation}".encode()
        ).hexdigest()
        lease = self.coordinator.claim(key)
        if lease is None:
            return EventResult("duplicate")
        try:
            raw = self.reader.read(event)
            # Storage contains canonical body-only documents, as published by the knowledge CLI.
            if (
                raw != document.body.encode()
                or hashlib.sha256(raw).hexdigest() != document.content_hash
            ):
                raise InputError("Storage source differs from the packaged synthetic corpus")
            before = self.coordinator.snapshot()
            staged = StagedStore(before)
            result = ingest(self.documents, self.embedder, staged)
            # Lease fencing, corpus writes and the durable receipt commit atomically.
            self.coordinator.commit(lease, before, staged.desired)
            return EventResult("indexed", result)
        except Exception:
            # A failed release expires; never mask the original operation failure.
            with suppress(Exception):
                self.coordinator.release(lease)
            raise
