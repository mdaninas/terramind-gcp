"""Versioned synthetic retrieval cases; local-double and live results stay distinct."""

import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from terramind.normalizer.io import read_bounded
from terramind.rag.retrieval import Retriever
from terramind.schemas.normalized import ClosedModel


class RetrievalCase(ClosedModel):
    id: Annotated[str, Field(pattern=r"^[a-z0-9-]{1,60}$")]
    query: Annotated[str, Field(min_length=1, max_length=1000)]
    expected_doc_id: Annotated[str, Field(pattern=r"^[a-z0-9-]{1,80}$")]


def evaluate_retrieval(
    retriever: Retriever,
    cases_path: Path,
    *,
    mode: Literal["local-test-double", "google-firestore"],
) -> dict[str, object]:
    cases = TypeAdapter(tuple[RetrievalCase, ...]).validate_json(
        read_bounded(cases_path, 16 * 1024)
    )
    if len(cases) != 10 or len({case.id for case in cases}) != 10:
        raise ValueError("Retrieval evaluation requires ten distinct cases")
    results = []
    for case in cases:
        try:
            chunks = retriever.search(case.query)
            returned = tuple(chunk.doc_id for chunk in chunks)
            hit = case.expected_doc_id in returned[:3]
        except Exception:
            returned, hit = (), False
        results.append(
            {
                "id": case.id,
                "expected_doc_id": case.expected_doc_id,
                "returned_doc_ids": returned,
                "hit_at_3": hit,
            }
        )
    hits = sum(bool(row["hit_at_3"]) for row in results)
    return {
        "mode": mode,
        "model_id": retriever.embedder.model_id,
        "queries": 10,
        "hits_at_3": hits,
        "passed": hits >= 8,
        "results": results,
    }


def evaluation_json(result: dict[str, object]) -> str:
    return json.dumps(result, indent=2) + "\n"
