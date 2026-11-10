"""Separate private Eventarc receiver; no provider discovery until a validated delivery."""

import asyncio
import os
from contextlib import ExitStack, suppress
from dataclasses import asdict
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from terramind.cloud.settings import CloudSettings
from terramind.errors import InputError
from terramind.events.service import EventIndexer, IndexingBusy, StorageEvent, packaged_corpus
from terramind.normalizer.io import parse_json


def create_app(indexer: EventIndexer | None = None, bucket: str | None = None) -> FastAPI:
    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @application.get("/healthz")
    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "terramind-eventarc"}

    def deliver(event: StorageEvent) -> dict[str, object]:
        if indexer is not None:
            return asdict(indexer.handle(event))
        documents = packaged_corpus()
        if event.name not in {f"sources/{doc.doc_id}/{doc.content_hash}.md" for doc in documents}:
            return {"status": "ignored", "ingestion": None}
        from terramind.cloud.budget import CallBudget
        from terramind.cloud.google import GoogleEmbedder
        from terramind.events.google import FirestoreIndexCoordinator, GoogleSourceReader

        settings = CloudSettings.from_env()
        budget = CallBudget(seconds=220, max_calls=160, per_call=20)

        def close(client: Any) -> None:
            with suppress(Exception):
                client.close()

        with ExitStack() as stack:
            embedder = GoogleEmbedder(settings, budget)
            stack.callback(close, embedder.client)
            coordinator = FirestoreIndexCoordinator(settings, budget)
            stack.callback(close, coordinator.client)
            reader = GoogleSourceReader(settings, budget)
            stack.callback(close, reader.client)
            return asdict(EventIndexer(documents, embedder, reader, coordinator).handle(event))

    @application.post("/events/storage")
    async def storage(request: Request) -> dict[str, object]:
        if indexer is None and os.environ.get("TERRAMIND_EVENTARC_MODE") != "cloud":
            raise HTTPException(503, "Eventarc ingestion is disabled")
        if request.headers.get("content-type", "").split(";", 1)[0] != "application/json":
            raise HTTPException(415, "Use a binary CloudEvent with JSON data")
        if request.headers.get("content-encoding", "identity") != "identity":
            raise HTTPException(415, "Encoded events are unsupported")
        raw = bytearray()
        try:
            async with asyncio.timeout(5):
                async for chunk in request.stream():
                    if len(raw) + len(chunk) > 64 * 1024:
                        raise HTTPException(413, "Event exceeds its size limit")
                    raw.extend(chunk)
            expected_bucket = bucket or CloudSettings.from_env().bucket
            if not expected_bucket:
                raise HTTPException(503, "Eventarc source is not configured")
            event = StorageEvent.parse(
                dict(request.headers), parse_json(bytes(raw), 64 * 1024), expected_bucket
            )
            return await run_in_threadpool(deliver, event)
        except TimeoutError:
            raise HTTPException(408, "Event body timeout") from None
        except InputError:
            raise HTTPException(400, "Invalid storage event or synthetic source") from None
        except IndexingBusy:
            raise HTTPException(
                503, "Ingestion busy; retry delivery", headers={"Retry-After": "30"}
            ) from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Eventarc ingestion unavailable") from None

    return application


app = create_app()
