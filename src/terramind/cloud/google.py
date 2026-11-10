"""Official SDK adapters with explicit project, collection, timeout and retry boundaries."""

import json
from typing import Any, Literal

from google import genai
from google.api_core import exceptions as api_errors
from google.cloud import firestore
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector
from google.cloud.storage.client import Client as StorageClient  # type: ignore[import-untyped]
from google.genai import errors, types
from pydantic import TypeAdapter

from terramind.cloud.budget import CallBudget, DependencyUnavailable
from terramind.cloud.settings import CloudSettings
from terramind.llm.contracts import CitationId, FindingId, ModelNarrative
from terramind.llm.diagnostics import AdvisoryReason
from terramind.llm.service import SYSTEM_INSTRUCTION
from terramind.rag.contracts import MAX_CHUNKS, Document, IndexedChunk, unit_vector

COLLECTION = "knowledge_chunks"


def is_transient(error: Exception) -> bool:
    return isinstance(
        error,
        (
            api_errors.ServiceUnavailable,
            api_errors.DeadlineExceeded,
            api_errors.TooManyRequests,
            api_errors.InternalServerError,
        ),
    ) or (isinstance(error, errors.APIError) and error.code in (429, 500, 502, 503, 504))


def http_options(timeout: float) -> types.HttpOptions:
    return types.HttpOptions(
        api_version="v1",
        timeout=max(1, int(timeout * 1000)),
        retry_options=types.HttpRetryOptions(attempts=1),
    )


def generation_schema(prompt: str = "{}") -> dict[str, Any]:
    """Use a small provider schema; the full strict contract is validated locally."""
    schema = ModelNarrative.model_json_schema()
    definitions = schema.get("$defs", {})

    def portable(node: dict[str, Any]) -> dict[str, Any]:
        if "$ref" in node:
            node = definitions[node["$ref"].rsplit("/", 1)[1]]
        result = {"type": node["type"]}
        if node["type"] == "object":
            result["properties"] = {
                key: portable(value) for key, value in node["properties"].items()
            }
            result["required"] = node["required"]
            result["additionalProperties"] = False
        elif node["type"] == "array":
            result["items"] = portable(node["items"])
            for bound in ("minItems", "maxItems"):
                if bound in node:
                    result[bound] = node[bound]
        return result

    result = portable(schema)
    explanations = result["properties"]["explanations"]
    explanations["maxItems"] = 12
    result["properties"]["recommendations"]["maxItems"] = 3
    result["properties"]["limitations"]["maxItems"] = 3
    # These identifiers come from the bounded plan/retrieval payload, never provider text.
    payload = json.loads(prompt)
    findings = payload.get("findings", []) if isinstance(payload, dict) else []
    if isinstance(findings, list) and 1 <= len(findings) <= 12:
        ids = TypeAdapter(list[FindingId]).validate_python([f["finding_id"] for f in findings])
        citations = TypeAdapter(list[CitationId]).validate_python(
            list(dict.fromkeys(c for f in findings for c in f["allowed_citation_ids"]))
        )
        if len(set(ids)) != len(ids) or not 1 <= len(citations) <= 60:
            raise ValueError("Invalid generation identifiers")
        explanations["minItems"] = explanations["maxItems"] = len(ids)
        explanations["items"]["properties"]["finding_id"]["enum"] = ids
        explanations["items"]["properties"]["citation_ids"]["items"]["enum"] = citations
        result["properties"]["citations"]["items"]["enum"] = citations
    return result


class GoogleEmbedder:
    def __init__(
        self, settings: CloudSettings, budget: CallBudget, client: genai.Client | None = None
    ):
        self.settings = settings
        self.budget = budget
        self.client = client or genai.Client(
            vertexai=True,
            project=settings.project_id,
            location=settings.embedding_location,
            http_options=http_options(budget.per_call),
        )

    @property
    def model_id(self) -> str:
        return self.settings.embedding_model

    def embed(
        self, text: str, *, task: Literal["document", "query"], title: str = ""
    ) -> tuple[float, ...]:
        if not text or len(text) > 3200:
            raise ValueError("Embedding input exceeds its limit")

        def request(timeout: float) -> tuple[float, ...]:
            result = self.client.models.embed_content(
                model=self.model_id,
                contents=text,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT" if task == "document" else "RETRIEVAL_QUERY",
                    title=title if task == "document" else None,
                    output_dimensionality=768,
                    auto_truncate=False,
                    http_options=http_options(timeout),
                ),
            )
            if not result.embeddings or len(result.embeddings) != 1:
                raise DependencyUnavailable("Invalid embedding response")
            embedding = result.embeddings[0]
            if embedding.statistics and embedding.statistics.truncated:
                raise DependencyUnavailable("Embedding input was truncated")
            return unit_vector(tuple(embedding.values or ()))

        return self.budget.run(request, transient=is_transient)


class GeminiSynthesizer:
    def __init__(
        self, settings: CloudSettings, budget: CallBudget, client: genai.Client | None = None
    ):
        self.settings = settings
        self.budget = budget
        self.client = client or genai.Client(
            vertexai=True,
            project=settings.project_id,
            location=settings.gemini_location,
            http_options=http_options(budget.per_call),
        )

    @property
    def model_id(self) -> str:
        return self.settings.gemini_model

    def generate(self, prompt: str) -> str:
        if len(prompt.encode()) > 48 * 1024:
            raise ValueError("Model input exceeds its limit")

        def request(timeout: float) -> str:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_json_schema=generation_schema(prompt),
                    max_output_tokens=4096,
                    # Verified model support; other configured models use their defaults.
                    thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.MINIMAL)
                    if self.model_id in {"gemini-3.5-flash", "gemini-3.1-flash-lite"}
                    else None,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    automatic_continuation=False,
                    http_options=http_options(timeout),
                ),
            )
            if not response.candidates or any(
                candidate.finish_reason != types.FinishReason.STOP
                for candidate in response.candidates
            ):
                raise DependencyUnavailable(
                    "Model response did not complete", reason=AdvisoryReason.INCOMPLETE
                )
            if not response.text:
                raise DependencyUnavailable(
                    "Model did not return text", reason=AdvisoryReason.EMPTY
                )
            return response.text

        return self.budget.run(request, transient=is_transient)


class FirestoreKnowledgeStore:
    def __init__(self, settings: CloudSettings, budget: CallBudget, client: Any = None):
        self.client = client or firestore.Client(
            project=settings.project_id, database=settings.database
        )
        self.collection = self.client.collection(COLLECTION)
        self.budget = budget

    @staticmethod
    def _record(snapshot: Any) -> IndexedChunk:
        data = snapshot.to_dict()
        embedding = data.pop("embedding")
        data["embedding"] = (
            tuple(embedding.to_map_value()["value"])  # type: ignore[no-untyped-call]
            if isinstance(embedding, Vector)
            else tuple(embedding)
        )
        record = IndexedChunk.model_validate(data)
        if snapshot.id != record.chunk.chunk_id:
            raise DependencyUnavailable("Stored knowledge ID mismatch")
        return record

    def snapshot(self) -> tuple[IndexedChunk, ...]:
        rows = self.budget.run(
            lambda timeout: tuple(
                self.collection.limit(MAX_CHUNKS + 1).stream(timeout=timeout, retry=None)
            ),
            transient=is_transient,
        )
        if len(rows) > MAX_CHUNKS:
            raise DependencyUnavailable("Stored knowledge exceeds its limit")
        return tuple(self._record(row) for row in rows)

    def synchronize(self, desired: tuple[IndexedChunk, ...]) -> None:
        if len(desired) > MAX_CHUNKS or len({x.chunk.chunk_id for x in desired}) != len(desired):
            raise ValueError("Invalid knowledge synchronization")
        existing = {item.chunk.chunk_id: item for item in self.snapshot()}
        wanted = {item.chunk.chunk_id: item for item in desired}
        batch = self.client.batch()
        for key in existing.keys() - wanted.keys():
            batch.delete(self.collection.document(key))
        changed = existing != wanted
        for key, record in wanted.items():
            if existing.get(key) != record:
                data = record.model_dump()
                data["embedding"] = Vector(record.embedding)
                batch.set(self.collection.document(key), data)
        if changed:
            # An ambiguous commit failure is not retried; a rerun reconciles stable IDs.
            self.budget.run(
                lambda timeout: batch.commit(timeout=timeout, retry=None), transient=lambda _: False
            )

    def nearest(self, vector: tuple[float, ...], *, limit: int) -> tuple[IndexedChunk, ...]:
        if not 3 <= limit <= 5:
            raise ValueError("Invalid knowledge query limit")
        query = self.collection.find_nearest(
            vector_field="embedding",
            query_vector=Vector(unit_vector(vector)),
            distance_measure=DistanceMeasure.COSINE,
            limit=limit,
        )
        rows = self.budget.run(
            lambda timeout: query.get(timeout=timeout, retry=None), transient=is_transient
        )
        return tuple(self._record(row) for row in rows)


class StorageSourcePublisher:
    def __init__(self, settings: CloudSettings, budget: CallBudget, client: Any = None):
        if settings.bucket is None:
            raise ValueError("A synthetic runbook bucket is required")
        self.client = client or StorageClient(project=settings.project_id)
        self.bucket = self.client.bucket(settings.bucket)
        self.budget = budget

    def publish(self, documents: tuple[Document, ...]) -> None:
        for document in documents:
            blob = self.bucket.blob(f"sources/{document.doc_id}/{document.content_hash}.md")

            def exists(timeout: float, blob: Any = blob) -> bool:
                return bool(blob.exists(timeout=timeout, retry=None))

            if not self.budget.run(exists, transient=is_transient):
                blob.metadata = {"synthetic": "true", "content_hash": document.content_hash}

                def upload(
                    timeout: float,
                    blob: Any = blob,
                    document: Document = document,
                ) -> None:
                    blob.upload_from_string(
                        document.body,
                        content_type="text/markdown; charset=utf-8",
                        if_generation_match=0,
                        timeout=timeout,
                        retry=None,
                    )

                self.budget.run(upload, transient=lambda _: False)
