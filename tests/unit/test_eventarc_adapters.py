import copy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from terramind.cloud.budget import CallBudget
from terramind.cloud.settings import CloudSettings
from terramind.events.google import FirestoreIndexCoordinator, GoogleSourceReader
from terramind.events.service import IndexingBusy, Lease, StorageEvent
from tests.integration.test_eventarc import system

SETTINGS = CloudSettings(project_id="terramind-demo", bucket="synthetic-runbooks")


def test_source_adapter_reads_the_exact_generation_with_preconditions_and_bounds():
    indexer, event = system()
    client, blob = MagicMock(), MagicMock()
    client.bucket.return_value.blob.return_value = blob
    blob.size = len(indexer.reader.body)
    blob.metadata = {"synthetic": "true", "content_hash": indexer.documents[0].content_hash}
    blob.content_type = "text/markdown; charset=utf-8"
    blob.download_as_bytes.return_value = indexer.reader.body
    reader = GoogleSourceReader(SETTINGS, CallBudget(), client)
    assert reader.read(event) == indexer.reader.body
    client.bucket.assert_called_once_with("synthetic-runbooks")
    client.bucket.return_value.blob.assert_called_once_with(event.name, generation=123)
    assert blob.reload.call_args.kwargs["if_generation_match"] == 123
    assert blob.download_as_bytes.call_args.kwargs["if_generation_match"] == 123
    assert blob.download_as_bytes.call_args.kwargs["end"] == 48 * 1024


@pytest.mark.parametrize("change", ["oversize", "metadata", "hash", "type", "truncated", "bucket"])
def test_source_adapter_rejects_untrusted_metadata_and_content_lengths(change):
    indexer, event = system()
    client, blob = MagicMock(), MagicMock()
    client.bucket.return_value.blob.return_value = blob
    blob.size = len(indexer.reader.body)
    blob.metadata = {"synthetic": "true", "content_hash": indexer.documents[0].content_hash}
    blob.content_type = "text/markdown"
    blob.download_as_bytes.return_value = indexer.reader.body
    if change == "oversize":
        blob.size = 50 * 1024
    elif change == "metadata":
        blob.metadata = None
    elif change == "hash":
        blob.metadata["content_hash"] = "0" * 64
    elif change == "type":
        blob.content_type = "application/octet-stream"
    elif change == "truncated":
        blob.download_as_bytes.return_value = b"truncated"
    else:
        event = StorageEvent("other-bucket", event.name, event.generation)
    with pytest.raises(ValueError):
        GoogleSourceReader(SETTINGS, CallBudget(), client).read(event)


class FakeDocument:
    def __init__(self, client, collection, key):
        self.client, self.collection, self.id = client, collection, key

    @property
    def path(self):
        return self.collection + "/" + self.id

    def get(self, **kwargs):
        value = copy.deepcopy(self.client.data.get(self.path))
        return SimpleNamespace(id=self.id, exists=value is not None, to_dict=lambda: value)


class FakeCollection:
    def __init__(self, client, name):
        self.client, self.name = client, name

    def document(self, key):
        return FakeDocument(self.client, self.name, key)

    def limit(self, limit):
        self.bound = limit
        return self

    def stream(self, **kwargs):
        keys = [key.split("/", 1)[1] for key in self.client.data if key.startswith(self.name + "/")]
        return [self.document(key).get() for key in keys[: self.bound]]


class FakeTransaction:
    def __init__(self, client):
        self.client, self.writes = client, []

    def set(self, ref, value):
        self.writes.append((ref.path, copy.deepcopy(value)))

    def delete(self, ref):
        self.writes.append((ref.path, None))

    def commit(self):
        if self.client.fail_commit:
            raise RuntimeError("synthetic transaction commit failure")
        staged = copy.deepcopy(self.client.data)
        for path, value in self.writes:
            if value is None:
                staged.pop(path, None)
            else:
                staged[path] = value
        self.client.data = staged


class FakeFirestore:
    def __init__(self):
        self.data = {}
        self.fail_commit = False

    def collection(self, name):
        return FakeCollection(self, name)

    def transaction(self, *, max_attempts):
        assert max_attempts == 1
        return FakeTransaction(self)


def coordinator(monkeypatch):
    def transactional(operation):
        def wrapped(transaction, **kwargs):
            result = operation(transaction, **kwargs)
            transaction.commit()
            return result

        return wrapped

    monkeypatch.setattr("terramind.events.google.firestore.transactional", transactional)
    client = FakeFirestore()
    return FirestoreIndexCoordinator(SETTINGS, CallBudget(seconds=20, max_calls=20), client), client


def test_firestore_lease_receipt_and_index_changes_commit_together(monkeypatch):
    target, client = coordinator(monkeypatch)
    lease = target.claim("a" * 64)
    with pytest.raises(IndexingBusy):
        target.claim("b" * 64)
    indexer, event = system()
    indexer.handle(event)
    target.commit(lease, (), indexer.coordinator.records)
    assert len(target.snapshot()) == 12
    assert "ingestion_control/corpus" not in client.data
    assert target.claim("a" * 64) is None
    newer = target.claim("b" * 64)
    target.release(Lease(newer.key, "other-owner"))
    assert "ingestion_control/corpus" in client.data
    target.release(newer)
    assert "ingestion_control/corpus" not in client.data


@pytest.mark.parametrize("failure", ["expired", "stolen", "commit", "external-write"])
def test_firestore_fencing_and_failed_commits_do_not_record_receipts(monkeypatch, failure):
    target, client = coordinator(monkeypatch)
    lease = target.claim("a" * 64)
    indexer, event = system()
    indexer.handle(event)
    if failure == "expired":
        client.data["ingestion_control/corpus"]["expires_at"] = datetime.now(UTC) - timedelta(
            seconds=1
        )
    elif failure == "stolen":
        client.data["ingestion_control/corpus"]["owner"] = "another-owner"
    elif failure == "commit":
        client.fail_commit = True
    else:
        existing = indexer.coordinator.records[0]
        from google.cloud.firestore_v1.vector import Vector

        payload = existing.model_dump()
        payload["embedding"] = Vector(existing.embedding)
        client.data["knowledge_chunks/" + existing.chunk.chunk_id] = payload
    with pytest.raises((IndexingBusy, RuntimeError)):
        target.commit(lease, (), indexer.coordinator.records)
    assert not any(key.startswith("ingestion_receipts/") for key in client.data)
    assert len([key for key in client.data if key.startswith("knowledge_chunks/")]) <= 1
