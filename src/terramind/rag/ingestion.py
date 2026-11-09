"""Idempotent full-corpus synchronization; embed only changed content."""

from dataclasses import dataclass

from terramind.rag.contracts import (
    Document,
    Embedder,
    IndexedChunk,
    KnowledgeStore,
    SourcePublisher,
)
from terramind.rag.corpus import corpus_chunks


@dataclass(frozen=True)
class IngestionResult:
    documents: int
    chunks: int
    embedded: int
    deleted: int
    changed: bool


def ingest(
    documents: tuple[Document, ...],
    embedder: Embedder,
    store: KnowledgeStore,
    publisher: SourcePublisher | None = None,
) -> IngestionResult:
    chunks = corpus_chunks(documents)
    existing = store.snapshot()
    # Titles affect document embeddings, so they are part of the reuse key.
    cache = {
        (item.chunk.chunk_hash, item.chunk.title, item.embedding_model): item.embedding
        for item in existing
    }
    desired = []
    embedded = 0
    for chunk in chunks:
        key = (chunk.chunk_hash, chunk.title, embedder.model_id)
        if key not in cache:
            cache[key] = embedder.embed(chunk.text, task="document", title=chunk.title)
            embedded += 1
        desired.append(
            IndexedChunk(
                chunk=chunk,
                embedding_model=embedder.model_id,
                embedding=cache[key],
            )
        )
    if publisher is not None:
        publisher.publish(documents)
    records = tuple(desired)
    changed = {x.chunk.chunk_id: x for x in existing} != {x.chunk.chunk_id: x for x in records}
    if changed:
        store.synchronize(records)
    deleted = len({x.chunk.chunk_id for x in existing} - {x.chunk.chunk_id for x in records})
    return IngestionResult(len(documents), len(chunks), embedded, deleted, changed)
