import copy
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from terramind.errors import InputError
from terramind.events.app import create_app
from terramind.events.service import (
    EVENT_TYPE,
    EventIndexer,
    IndexingBusy,
    Lease,
    StorageEvent,
    packaged_corpus,
)
from terramind.rag.corpus import load_corpus
from tests.knowledge_helpers import CountingEmbedder


class LocalCoordinator:
    """Durable-state double, with one fenced commit boundary and no provider calls."""

    def __init__(self):
        self.records = ()
        self.receipts = set()
        self.lease = None
        self.commits = 0
        self.fail_commit = False
        self.lose_lease = False

    def claim(self, key):
        if key in self.receipts:
            return None
        if self.lease:
            raise IndexingBusy()
        self.lease = Lease(key, "local-owner")
        return self.lease

    def snapshot(self):
        return self.records

    def commit(self, lease, before, desired):
        if self.lose_lease or self.lease != lease or self.records != before:
            raise IndexingBusy()
        if self.fail_commit:
            raise RuntimeError("synthetic-commit-failure")
        self.records = desired
        self.receipts.add(lease.key)
        self.lease = None
        self.commits += 1

    def release(self, lease):
        if self.lease == lease:
            self.lease = None


class LocalReader:
    def __init__(self, body):
        self.body = body
        self.calls = []

    def read(self, event):
        self.calls.append(event)
        return self.body


def system():
    documents = packaged_corpus()
    doc = documents[0]
    event = StorageEvent("synthetic-runbooks", f"sources/{doc.doc_id}/{doc.content_hash}.md", 123)
    reader, embedder, coordinator = (
        LocalReader(doc.body.encode()),
        CountingEmbedder(),
        LocalCoordinator(),
    )
    return EventIndexer(documents, embedder, reader, coordinator), event


def envelope(event):
    return {
        "ce-specversion": "1.0",
        "ce-type": EVENT_TYPE,
        "ce-id": "synthetic-event-1",
        "ce-source": f"//storage.googleapis.com/projects/_/buckets/{event.bucket}",
        "ce-subject": f"objects/{event.name}",
    }, {"bucket": event.bucket, "name": event.name, "generation": str(event.generation)}


def test_packaged_synthetic_manifest_matches_reviewed_markdown():
    assert packaged_corpus() == load_corpus(Path("knowledge-base"))


def test_duplicate_delivery_survives_a_new_worker_without_embedding_or_source_reads():
    indexer, event = system()
    first = indexer.handle(event)
    assert first.status == "indexed" and first.ingestion.embedded == 12
    indexer.embedder.calls.clear()
    indexer.reader.calls.clear()
    restarted = EventIndexer(
        indexer.documents, indexer.embedder, indexer.reader, indexer.coordinator
    )
    assert restarted.handle(event).status == "duplicate"
    assert indexer.embedder.calls == [] and indexer.reader.calls == []
    assert indexer.coordinator.commits == 1


def test_new_generation_with_identical_content_reuses_vectors():
    indexer, event = system()
    indexer.handle(event)
    indexer.embedder.calls.clear()
    result = indexer.handle(replace(event, generation=124))
    assert result.status == "indexed" and result.ingestion.embedded == 0
    assert not result.ingestion.changed and indexer.embedder.calls == []


@pytest.mark.parametrize(
    "name",
    [
        "../private.md",
        "unreviewed.md",
        "sources/unknown/hash.md",
        "sources/public-bucket/" + "0" * 64 + ".md",
    ],
)
def test_unknown_or_old_revision_objects_are_acknowledged_without_provider_work(name):
    indexer, event = system()
    assert indexer.handle(replace(event, name=name)).status == "ignored"
    assert indexer.reader.calls == [] and indexer.embedder.calls == []
    assert indexer.coordinator.lease is None


def test_source_integrity_fails_before_embeddings_and_releases_lease():
    indexer, event = system()
    indexer.reader.body = b"synthetic content different from approved corpus"
    with pytest.raises(InputError):
        indexer.handle(event)
    assert indexer.embedder.calls == []
    assert indexer.coordinator.lease is None and not indexer.coordinator.receipts


@pytest.mark.parametrize("failure", ["commit", "lease", "embedding"])
def test_failed_ingestion_never_records_success_and_can_retry(failure):
    indexer, event = system()
    if failure == "embedding":
        original = indexer.embedder.embed
        indexer.embedder.embed = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("outage"))
    else:
        indexer.coordinator.fail_commit = failure == "commit"
        indexer.coordinator.lose_lease = failure == "lease"
    with pytest.raises((RuntimeError, IndexingBusy)):
        indexer.handle(event)
    assert indexer.coordinator.records == () and not indexer.coordinator.receipts
    assert indexer.coordinator.lease is None
    if failure == "embedding":
        indexer.embedder.embed = original
    indexer.coordinator.fail_commit = indexer.coordinator.lose_lease = False
    assert indexer.handle(event).status == "indexed"


def test_busy_worker_is_retryable_without_embedding():
    indexer, event = system()
    indexer.coordinator.lease = Lease("another-event", "another-worker")
    with pytest.raises(IndexingBusy):
        indexer.handle(event)
    assert indexer.embedder.calls == [] and indexer.reader.calls == []


def test_receiver_processes_binary_cloudevent_and_duplicates():
    indexer, event = system()
    headers, data = envelope(event)
    client = TestClient(create_app(indexer, event.bucket))
    first = client.post("/events/storage", headers=headers, json=data)
    assert first.status_code == 200 and first.json()["ingestion"]["embedded"] == 12
    headers["ce-id"] = "different-delivery-id"
    assert (
        client.post("/events/storage", headers=headers, json=data).json()["status"] == "duplicate"
    )


@pytest.mark.parametrize("change", ["bucket", "source", "type", "subject", "generation", "id"])
def test_receiver_rejects_forged_or_invalid_envelopes_before_io(change):
    indexer, event = system()
    headers, data = envelope(event)
    if change == "bucket":
        data["bucket"] = "another-bucket"
    elif change == "generation":
        data["generation"] = "-1"
    elif change == "id":
        headers["ce-id"] = "invalid event id"
    else:
        headers["ce-" + change] = "untrusted"
    response = TestClient(create_app(indexer, event.bucket)).post(
        "/events/storage",
        headers=headers,
        json=data,
    )
    assert response.status_code == 400
    assert indexer.reader.calls == [] and indexer.embedder.calls == []


def test_receiver_rejects_oversized_duplicate_json_and_unexpected_media():
    indexer, event = system()
    client = TestClient(create_app(indexer, event.bucket))
    headers, data = envelope(event)
    headers["content-type"] = "application/json"
    assert client.post("/events/storage", headers=headers, content=b" " * 65537).status_code == 413
    duplicate = json.dumps(data)[:-1] + ',"generation":"124"}'
    assert client.post("/events/storage", headers=headers, content=duplicate).status_code == 400
    headers["content-type"] = "text/plain"
    assert client.post("/events/storage", headers=headers, content=b"synthetic").status_code == 415
    assert indexer.reader.calls == []


def test_receiver_is_disabled_by_default_and_health_never_discovers_credentials(monkeypatch):
    monkeypatch.delenv("TERRAMIND_EVENTARC_MODE", raising=False)
    client = TestClient(create_app())
    assert client.get("/health").json()["service"] == "terramind-eventarc"
    assert client.post("/events/storage", json={}).status_code == 503


def test_cloud_receiver_ignores_unapproved_objects_before_discovering_credentials(monkeypatch):
    monkeypatch.setenv("TERRAMIND_EVENTARC_MODE", "cloud")
    monkeypatch.setenv("GCP_PROJECT_ID", "terramind-demo")
    monkeypatch.setenv("RUNBOOK_BUCKET", "synthetic-runbooks")
    event = StorageEvent("synthetic-runbooks", "unapproved-object.md", 123)
    headers, data = envelope(event)
    response = TestClient(create_app()).post("/events/storage", headers=headers, json=data)
    assert response.status_code == 200 and response.json()["status"] == "ignored"


def test_busy_http_response_has_retry_after_and_no_private_details():
    indexer, event = system()
    indexer.coordinator.lease = Lease("synthetic", "private-worker")
    headers, data = envelope(event)
    response = TestClient(create_app(indexer, event.bucket)).post(
        "/events/storage",
        headers=headers,
        json=data,
    )
    assert response.status_code == 503 and response.headers["retry-after"] == "30"
    assert "private-worker" not in response.text


def test_changes_in_the_packaged_manifest_change_receipt_identity():
    indexer, _ = system()
    documents = list(copy.copy(indexer.documents))
    documents[0] = documents[0].model_copy(update={"version": "2.0"})
    newer = EventIndexer(tuple(documents), indexer.embedder, indexer.reader, indexer.coordinator)
    assert newer.revision != indexer.revision


@pytest.mark.parametrize("failure", ["none", "coordinator-init", "source-read"])
def test_cloud_receiver_composition_closes_created_clients_and_sanitizes_errors(
    monkeypatch, failure
):
    indexer, event = system()
    closed = []
    indexer.embedder.client = SimpleNamespace(close=lambda: closed.append("embedding"))
    indexer.coordinator.client = SimpleNamespace(close=lambda: closed.append("firestore"))
    indexer.reader.client = SimpleNamespace(close=lambda: closed.append("storage"))
    monkeypatch.setenv("TERRAMIND_EVENTARC_MODE", "cloud")
    monkeypatch.setenv("GCP_PROJECT_ID", "terramind-demo")
    monkeypatch.setenv("RUNBOOK_BUCKET", event.bucket)
    monkeypatch.setattr("terramind.cloud.google.GoogleEmbedder", lambda *args: indexer.embedder)

    def coordinator_factory(*args):
        if failure == "coordinator-init":
            raise RuntimeError("synthetic-private-provider-message")
        return indexer.coordinator

    monkeypatch.setattr("terramind.events.google.FirestoreIndexCoordinator", coordinator_factory)
    monkeypatch.setattr("terramind.events.google.GoogleSourceReader", lambda *args: indexer.reader)
    if failure == "source-read":

        def unavailable(event):
            raise RuntimeError("synthetic-private-provider-message")

        indexer.reader.read = unavailable
    headers, data = envelope(event)
    response = TestClient(create_app()).post("/events/storage", headers=headers, json=data)
    assert response.status_code == (200 if failure == "none" else 503)
    assert "synthetic-private" not in response.text
    assert "embedding" in closed
    assert len(closed) == (1 if failure == "coordinator-init" else 3)


def test_receiver_rejects_encoded_events_before_source_reads():
    indexer, event = system()
    headers, data = envelope(event)
    headers["content-encoding"] = "gzip"
    response = TestClient(create_app(indexer, event.bucket)).post(
        "/events/storage",
        headers=headers,
        json=data,
    )
    assert response.status_code == 415 and indexer.reader.calls == []
