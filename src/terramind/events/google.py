"""Generation-bound GCS reads and transactional Firestore ingestion receipts."""

from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast
from uuid import uuid4

from google.cloud import firestore
from google.cloud.firestore_v1.vector import Vector
from google.cloud.storage.client import Client as StorageClient  # type: ignore[import-untyped]

from terramind.cloud.budget import CallBudget, DependencyUnavailable
from terramind.cloud.google import COLLECTION, FirestoreKnowledgeStore, is_transient
from terramind.cloud.settings import CloudSettings
from terramind.events.service import IndexingBusy, Lease, StorageEvent
from terramind.rag.contracts import MAX_CHUNKS, IndexedChunk
from terramind.rag.corpus import MAX_DOCUMENT_BYTES


class GoogleSourceReader:
    def __init__(self, settings: CloudSettings, budget: CallBudget, client: Any = None):
        self.settings = settings
        if not settings.bucket:
            raise ValueError("An approved source bucket is required")
        self.bucket_name = settings.bucket
        self.client = client or StorageClient(project=settings.project_id)
        self.budget = budget

    def read(self, event: StorageEvent) -> bytes:
        if event.bucket != self.bucket_name:
            raise ValueError("Unexpected source bucket")
        blob = self.client.bucket(self.bucket_name).blob(event.name, generation=event.generation)
        self.budget.run(
            lambda timeout: blob.reload(
                if_generation_match=event.generation, timeout=timeout, retry=None
            ),
            transient=is_transient,
        )
        if (
            blob.size is None
            or not 0 < blob.size <= MAX_DOCUMENT_BYTES
            or blob.metadata is None
            or blob.metadata.get("synthetic") != "true"
            or blob.metadata.get("content_hash") != event.name.rsplit("/", 1)[-1][:-3]
            or (blob.content_type or "").split(";", 1)[0] != "text/markdown"
        ):
            raise ValueError("Source object failed metadata validation")
        raw = self.budget.run(
            lambda timeout: blob.download_as_bytes(
                start=0,
                end=MAX_DOCUMENT_BYTES,
                if_generation_match=event.generation,
                timeout=timeout,
                retry=None,
            ),
            transient=is_transient,
        )
        if not isinstance(raw, bytes) or len(raw) != blob.size or len(raw) > MAX_DOCUMENT_BYTES:
            raise ValueError("Source object exceeded its byte limit")
        return raw


class FirestoreIndexCoordinator:
    def __init__(self, settings: CloudSettings, budget: CallBudget, client: Any = None):
        self.settings = settings
        self.client = client or firestore.Client(
            project=settings.project_id, database=settings.database
        )
        self.budget = budget
        self.lock = self.client.collection("ingestion_control").document("corpus")
        self.chunks = self.client.collection(COLLECTION)
        self.receipts = self.client.collection("ingestion_receipts")

    def _transaction(self, operation: Any) -> Any:
        # No outer retries on ambiguous commits. Redelivery reconciles durable receipts.
        return self.budget.run(
            lambda timeout: firestore.transactional(operation)(
                self.client.transaction(max_attempts=1),
                timeout=timeout,
            ),
            transient=lambda _: False,
        )

    def claim(self, key: str) -> Lease | None:
        owner = uuid4().hex

        def claim(transaction: Any, *, timeout: float) -> Lease | Literal["busy"] | None:
            receipt = self.receipts.document(key).get(
                transaction=transaction, timeout=timeout, retry=None
            )
            state = (
                self.lock.get(transaction=transaction, timeout=timeout, retry=None).to_dict() or {}
            )
            now = datetime.now(UTC)
            if receipt.exists:
                return None
            if state.get("expires_at", now) > now:
                return "busy"
            transaction.set(self.lock, {"owner": owner, "expires_at": now + timedelta(seconds=300)})
            return Lease(key, owner)

        result = self._transaction(claim)
        if result == "busy":
            raise IndexingBusy("Corpus ingestion is already in progress")
        return cast(Lease | None, result)

    def snapshot(self) -> tuple[IndexedChunk, ...]:
        return FirestoreKnowledgeStore(
            # Reuse the existing initialized client; the constructor only needs configuration
            # when it must create a client, which is avoided here.
            self.settings,
            self.budget,
            client=self.client,
        ).snapshot()

    def commit(
        self, lease: Lease, before: tuple[IndexedChunk, ...], desired: tuple[IndexedChunk, ...]
    ) -> None:
        if len(desired) > MAX_CHUNKS or len({item.chunk.chunk_id for item in desired}) != len(
            desired
        ):
            raise ValueError("Invalid staged knowledge")

        def commit(transaction: Any, *, timeout: float) -> bool:
            state = (
                self.lock.get(transaction=transaction, timeout=timeout, retry=None).to_dict() or {}
            )
            now = datetime.now(UTC)
            if state.get("owner") != lease.owner or state.get("expires_at", now) <= now:
                return False
            rows = tuple(
                self.chunks.limit(MAX_CHUNKS + 1).stream(
                    transaction=transaction,
                    timeout=timeout,
                    retry=None,
                )
            )
            if len(rows) > MAX_CHUNKS:
                raise DependencyUnavailable("Knowledge exceeds its bounds")
            current = {row.id: FirestoreKnowledgeStore._record(row) for row in rows}
            if current != {item.chunk.chunk_id: item for item in before}:
                return False
            wanted = {item.chunk.chunk_id: item for item in desired}
            for key in current.keys() - wanted.keys():
                transaction.delete(self.chunks.document(key))
            for key, record in wanted.items():
                if current.get(key) != record:
                    data = record.model_dump()
                    data["embedding"] = Vector(record.embedding)
                    transaction.set(self.chunks.document(key), data)
            transaction.set(
                self.receipts.document(lease.key),
                {
                    "expires_at": now + timedelta(days=7),
                    "completed_at": now,
                },
            )
            transaction.delete(self.lock)
            return True

        if not self._transaction(commit):
            raise IndexingBusy("Corpus lease expired or knowledge changed before commit")

    def release(self, lease: Lease) -> None:
        def release(transaction: Any, *, timeout: float) -> None:
            state = (
                self.lock.get(transaction=transaction, timeout=timeout, retry=None).to_dict() or {}
            )
            if state.get("owner") == lease.owner:
                transaction.delete(self.lock)

        self._transaction(release)
