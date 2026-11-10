import copy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from google.api_core import exceptions as api_errors
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector
from google.genai import types

from terramind.cloud.budget import CallBudget, DependencyUnavailable
from terramind.cloud.google import (
    FirestoreKnowledgeStore,
    GeminiSynthesizer,
    GoogleEmbedder,
    StorageSourcePublisher,
)
from terramind.cloud.settings import CloudSettings
from tests.knowledge_helpers import local_system


def settings():
    return CloudSettings(project_id="terramind-synthetic-example", bucket="synthetic-runbooks")


def test_embedding_sdk_task_dimension_and_retry_configuration():
    response = types.EmbedContentResponse(embeddings=[types.ContentEmbedding(values=[1.0] * 768)])
    method = Mock(return_value=response)
    client = SimpleNamespace(models=SimpleNamespace(embed_content=method))
    budget = CallBudget()
    embedder = GoogleEmbedder(settings(), budget, client)
    document = embedder.embed(
        "Synthetic public bucket document", task="document", title="Synthetic"
    )
    embedder.embed("Synthetic query", task="query")
    assert len(document) == 768 and budget.calls == 2
    config = method.call_args_list[0].kwargs["config"]
    assert config.task_type == "RETRIEVAL_DOCUMENT" and config.title == "Synthetic"
    assert config.output_dimensionality == 768 and config.auto_truncate is False
    assert config.http_options.timeout <= 8000 and config.http_options.retry_options.attempts == 1
    query = method.call_args_list[1].kwargs["config"]
    assert query.task_type == "RETRIEVAL_QUERY" and query.title is None


@pytest.mark.parametrize("values", [[], [1.0], [float("nan")] * 768, [0.0] * 768])
def test_embedding_provider_values_are_validated(values):
    response = types.EmbedContentResponse(embeddings=[types.ContentEmbedding(values=values)])
    client = SimpleNamespace(models=SimpleNamespace(embed_content=Mock(return_value=response)))
    with pytest.raises(DependencyUnavailable):
        GoogleEmbedder(settings(), CallBudget(), client).embed("Synthetic", task="query")


def test_gemini_disables_tools_and_continuation_and_uses_structured_schema():
    method = Mock(
        return_value=SimpleNamespace(
            text='{"synthetic":"response"}',
            candidates=[SimpleNamespace(finish_reason=types.FinishReason.STOP)],
        )
    )
    client = SimpleNamespace(models=SimpleNamespace(generate_content=method))
    assert (
        GeminiSynthesizer(settings(), CallBudget(), client).generate("{}")
        == '{"synthetic":"response"}'
    )
    config = method.call_args.kwargs["config"]
    assert method.call_args.kwargs["model"] == "gemini-3.5-flash"
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema["additionalProperties"] is False
    assert set(config.response_json_schema["properties"]) == {
        "summary",
        "explanations",
        "recommendations",
        "citations",
        "limitations",
    }
    assert not any(
        key in json.dumps(config.response_json_schema) for key in ("$ref", "pattern", "maxLength")
    )
    assert config.response_json_schema["properties"]["explanations"]["maxItems"] == 12
    assert config.max_output_tokens == 4096
    assert config.thinking_config.thinking_level == types.ThinkingLevel.MINIMAL
    assert config.automatic_function_calling.disable is True
    assert config.automatic_continuation is False and config.tools is None
    assert "untrusted DATA" in config.system_instruction


@pytest.mark.parametrize("model", ["gemini-3.1-flash-lite", "synthetic-other-model"])
def test_thinking_parameters_are_sent_only_to_verified_supported_models(model):
    method = Mock(
        return_value=SimpleNamespace(
            text='{"synthetic":"response"}',
            candidates=[SimpleNamespace(finish_reason=types.FinishReason.STOP)],
        )
    )
    client = SimpleNamespace(models=SimpleNamespace(generate_content=method))
    config = settings().model_copy(update={"gemini_model": model})
    GeminiSynthesizer(config, CallBudget(), client).generate("{}")
    thinking = method.call_args.kwargs["config"].thinking_config
    assert (thinking is not None) is (model == "gemini-3.1-flash-lite")


def test_truncated_generation_is_not_accepted_even_if_its_text_is_valid_json():
    method = Mock(
        return_value=SimpleNamespace(
            text='{"synthetic":"response"}',
            candidates=[SimpleNamespace(finish_reason=types.FinishReason.MAX_TOKENS)],
        )
    )
    client = SimpleNamespace(models=SimpleNamespace(generate_content=method))
    with pytest.raises(DependencyUnavailable) as error:
        GeminiSynthesizer(settings(), CallBudget(), client).generate("{}")
    assert error.value.reason.value == "generation_incomplete"
    assert method.call_count == 1


def test_shared_call_budget_transient_retries_and_permanent_failures(monkeypatch):
    monkeypatch.setattr("terramind.cloud.budget.time.sleep", lambda _: None)
    budget = CallBudget(max_calls=2)
    transient = Mock(side_effect=api_errors.ServiceUnavailable("synthetic-private-canary"))
    with pytest.raises(DependencyUnavailable, match="budget exhausted") as error:
        budget.run(transient, transient=lambda _: True)
    assert transient.call_count == 2 and "synthetic-private-canary" not in str(error.value)
    budget = CallBudget()
    permanent = Mock(side_effect=api_errors.PermissionDenied("synthetic-private-canary"))
    with pytest.raises(DependencyUnavailable):
        budget.run(permanent, transient=lambda _: False)
    assert permanent.call_count == 1
    attempts = Mock(side_effect=TimeoutError("synthetic-private-canary"))
    with pytest.raises(DependencyUnavailable):
        budget.run(attempts, transient=lambda _: True)
    assert attempts.call_count == 3


def test_deadline_is_shared_and_limits_individual_calls(monkeypatch):
    clock = [10.0]
    monkeypatch.setattr("terramind.cloud.budget.time.monotonic", lambda: clock[0])
    budget = CallBudget(seconds=3, per_call=8)
    operation = Mock(return_value="ok")
    assert budget.run(operation, transient=lambda _: False) == "ok"
    assert operation.call_args.args[0] == 3
    clock[0] = 13.1
    with pytest.raises(DependencyUnavailable):
        budget.run(operation, transient=lambda _: False)
    assert operation.call_count == 1


def snapshots(records):
    return [
        SimpleNamespace(
            id=r.chunk.chunk_id,
            to_dict=lambda r=r: {**copy.deepcopy(r.model_dump()), "embedding": Vector(r.embedding)},
        )
        for r in records
    ]


def test_firestore_uses_fixed_collection_real_vector_type_and_bounded_rpc():
    _, _, memory, _ = local_system()
    client = Mock()
    collection = client.collection.return_value
    collection.find_nearest.return_value.get.return_value = snapshots(memory.records[:3])
    collection.limit.return_value.stream.return_value = snapshots(memory.records)
    store = FirestoreKnowledgeStore(settings(), CallBudget(), client)
    assert store.snapshot() == memory.records
    nearest = store.nearest(memory.records[0].embedding, limit=3)
    assert nearest == memory.records[:3]
    client.collection.assert_called_once_with("knowledge_chunks")
    args = collection.find_nearest.call_args.kwargs
    assert isinstance(args["query_vector"], Vector)
    assert args["vector_field"] == "embedding" and args["limit"] == 3
    assert args["distance_measure"] == DistanceMeasure.COSINE
    rpc = collection.find_nearest.return_value.get.call_args.kwargs
    assert rpc["retry"] is None and 0 < rpc["timeout"] <= 8


def test_firestore_sync_prunes_stale_ids_atomically_and_unchanged_sync_is_noop():
    _, _, memory, _ = local_system()
    client = Mock()
    client.collection.return_value.limit.return_value.stream.side_effect = [
        snapshots(memory.records),
        snapshots(memory.records),
    ]
    store = FirestoreKnowledgeStore(settings(), CallBudget(), client)
    store.synchronize(memory.records)
    client.batch.return_value.commit.assert_not_called()
    store.synchronize(memory.records[1:])
    assert client.batch.return_value.delete.call_count == 1
    assert client.batch.return_value.set.call_count == 0
    client.batch.return_value.commit.assert_called_once()
    assert client.batch.return_value.commit.call_args.kwargs["retry"] is None


def test_storage_publishes_only_content_addressed_synthetic_markdown():
    documents, _, _, _ = local_system()
    client = Mock()
    blob = client.bucket.return_value.blob.return_value
    blob.exists.return_value = False
    publisher = StorageSourcePublisher(settings(), CallBudget(max_calls=50), client)
    publisher.publish(documents[:1])
    document = documents[0]
    client.bucket.assert_called_once_with("synthetic-runbooks")
    client.bucket.return_value.blob.assert_called_with(
        f"sources/{document.doc_id}/{document.content_hash}.md"
    )
    assert blob.upload_from_string.call_args.args[0] == document.body
    assert blob.upload_from_string.call_args.kwargs["if_generation_match"] == 0
    assert blob.upload_from_string.call_args.kwargs["retry"] is None
    blob.exists.return_value = True
    publisher.publish(documents[:1])
    assert blob.upload_from_string.call_count == 1


def test_settings_do_not_accept_api_keys_or_arbitrary_service_endpoints(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT_ID", "terramind-synthetic-example")
    monkeypatch.setenv("SYNTHETIC_SECRET", "synthetic-unshared-canary")
    monkeypatch.setenv("GOOGLE_API_KEY", "synthetic-key-not-used-by-settings")
    config = CloudSettings.from_env()
    assert "synthetic-unshared-canary" not in config.model_dump_json()
    assert "synthetic-key-not-used-by-settings" not in config.model_dump_json()
    assert config.embedding_location == "us-central1" and config.gemini_location == "global"
    assert set(json.loads(config.model_dump_json())) <= set(CloudSettings.model_fields)
