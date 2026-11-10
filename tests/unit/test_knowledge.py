import hashlib
import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from terramind.errors import InputError
from terramind.rag.contracts import DIMENSIONS, Document, IndexedChunk, unit_vector
from terramind.rag.corpus import TARGET_CHARACTERS, chunk_document, corpus_chunks, load_corpus
from terramind.rag.ingestion import ingest
from terramind.rag.local import MemoryKnowledgeStore
from terramind.rag.retrieval import RetrievalUnavailable, Retriever
from tests.knowledge_helpers import CountingEmbedder, local_system


def changed(document, **updates):
    data = {**document.model_dump(), **updates}
    data["content_hash"] = hashlib.sha256(data["body"].encode()).hexdigest()
    return Document.model_validate(data)


def test_corpus_has_synthetic_provenance_and_repeatable_chunks():
    documents = load_corpus(Path("knowledge-base"))
    assert len(documents) == 12
    assert sum(d.source_path.startswith("incidents/") for d in documents) == 4
    chunks = corpus_chunks(documents)
    assert chunks == corpus_chunks(load_corpus(Path("knowledge-base")))
    assert len({c.chunk_id for c in chunks}) == len(chunks)
    assert all(c.synthetic and len(c.text) <= TARGET_CHARACTERS for c in chunks)
    assert all("prompt_injection" not in c.source_path for c in chunks)
    for document in documents:
        assert document.content_hash == hashlib.sha256(document.body.encode()).hexdigest()


def test_heading_chunks_preserve_context_and_ignore_fenced_headings():
    document = load_corpus(Path("knowledge-base"))[0]
    text = "# First\n" + "word " * 600 + "\n## Second\n```\n# Not a section\n```\nReview."
    chunks = chunk_document(changed(document, body=text))
    assert len(chunks) >= 3
    assert chunks[0].section_id == "first-000"
    assert any(c.section_id == "second-000" and "# Not a section" in c.text for c in chunks)
    assert not any(c.section_id.startswith("not-a-section") for c in chunks)
    with pytest.raises(InputError):
        chunk_document(changed(document, body="# Duplicate\none\n## Duplicate\ntwo"))


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "unknown", "real", "secret", "large"])
def test_corpus_rejects_invalid_metadata_and_content(tmp_path, mutation):
    for doc in load_corpus(Path("knowledge-base")):
        destination = tmp_path / doc.source_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((Path("knowledge-base") / doc.source_path).read_bytes())
    target = next((tmp_path / "runbooks").glob("*.md"))
    original = target.read_text()
    value = {
        "missing": original.replace("synthetic: true\n", ""),
        "duplicate": original.replace("synthetic: true", "synthetic: true\nsynthetic: true"),
        "unknown": original.replace("synthetic: true", "synthetic: true\nextra: value"),
        "real": original.replace("synthetic: true", "synthetic: false"),
        "secret": original + "\nBearer synthetic-token-canary-long",
        "large": original + "x" * (49 * 1024),
    }[mutation]
    target.write_text(value)
    with pytest.raises(InputError):
        load_corpus(tmp_path)


def test_empty_and_duplicate_document_corpora_are_rejected(tmp_path):
    with pytest.raises(InputError):
        load_corpus(tmp_path)
    with pytest.raises(InputError):
        corpus_chunks(())


def test_ingestion_rerun_does_not_embed_or_write_unchanged_content():
    documents, embedder, store, _ = local_system()
    writes = store.writes
    result = ingest(documents, embedder, store)
    assert result.embedded == 0 and not result.changed
    assert not embedder.calls and store.writes == writes
    changed_documents = (
        changed(documents[0], body=documents[0].body + "\nAdditional exercise note."),
        *documents[1:],
    )
    result = ingest(changed_documents, embedder, store)
    assert result.embedded == 1 and result.changed
    result = ingest(changed_documents[1:], embedder, store)
    assert result.deleted == 1 and len(store.snapshot()) == 11


def test_embedding_profile_and_title_changes_force_reembedding():
    documents, embedder, store, _ = local_system()
    updated = (changed(documents[0], title="Synthetic changed source title"), *documents[1:])
    assert ingest(updated, embedder, store).embedded == 1
    embedder.model_id = "another-test-profile"
    assert ingest(updated, embedder, store).embedded == len(store.snapshot())


def test_embedding_failure_does_not_publish_or_mutate_store():
    documents = load_corpus(Path("knowledge-base"))
    store = MemoryKnowledgeStore()

    class FailingEmbedder(CountingEmbedder):
        def embed(self, *args, **kwargs):
            raise RuntimeError("synthetic-provider-secret")

    class Publisher:
        def publish(self, documents):
            raise AssertionError("Sources must not publish after an embedding failure")

    with pytest.raises(RuntimeError):
        ingest(documents, FailingEmbedder(), store, Publisher())
    assert store.snapshot() == () and store.writes == 0


@pytest.mark.parametrize(
    "vector", [(1.0,), (0.0,) * DIMENSIONS, (math.nan,) * DIMENSIONS, (math.inf,) * DIMENSIONS]
)
def test_invalid_vectors_are_rejected(vector):
    with pytest.raises(ValueError):
        unit_vector(vector)


def test_embedding_normalization_and_hash_integrity():
    _, _, store, _ = local_system()
    original = store.records[0]
    assert sum(x * x for x in original.embedding) == pytest.approx(1.0)
    assert unit_vector(original.embedding) == original.embedding
    with pytest.raises(ValidationError):
        IndexedChunk.model_validate({**original.model_dump(), "embedding": (0.0,) * DIMENSIONS})
    bad = original.model_dump()
    bad["chunk"]["text"] += "tampered"
    with pytest.raises(ValidationError):
        IndexedChunk.model_validate(bad)


def test_empty_store_profile_mismatch_and_limits():
    _, embedder, store, retriever = local_system()
    with pytest.raises(RetrievalUnavailable):
        Retriever(embedder, MemoryKnowledgeStore()).search("bucket access")
    embedder.model_id = "incompatible-test-profile"
    with pytest.raises(RetrievalUnavailable):
        retriever.search("bucket access")
    with pytest.raises(ValueError):
        Retriever(embedder, store, 2)
    with pytest.raises(ValueError):
        retriever.search("x" * 1001)
