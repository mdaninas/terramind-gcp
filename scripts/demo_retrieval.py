"""Credential-free integration demo using explicitly labeled local test doubles."""

import json
from pathlib import Path

from terramind.llm.service import explain
from terramind.normalizer.io import load_normalized
from terramind.rag.corpus import load_corpus
from terramind.rag.evaluation import evaluate_retrieval, evaluation_json
from terramind.rag.ingestion import ingest
from terramind.rag.local import LexicalTestEmbedder, MemoryKnowledgeStore
from terramind.rag.retrieval import Retriever
from terramind.reports.render import markdown


class FixtureSynthesis:
    model_id = "local-fixture-not-gemini"

    def generate(self, prompt: str) -> str:
        data = json.loads(prompt)
        items = [
            {
                "finding_id": item["finding_id"],
                "text": item["facts"]["rationale"],
                "citation_ids": [item["allowed_citation_ids"][0]],
            }
            for item in data["findings"]
        ]
        return json.dumps(
            {
                "summary": "Local integration demonstration. Review the deterministic findings.",
                "explanations": items,
                "recommendations": [
                    "Correlate the resource alias with the original change locally."
                ],
                "citations": list(dict.fromkeys(c for item in items for c in item["citation_ids"])),
                "limitations": [
                    "Fixture prose and lexical vectors are local test doubles, not Gemini output."
                ],
            }
        )


def main() -> None:
    embedder, store = LexicalTestEmbedder(), MemoryKnowledgeStore()
    result = ingest(load_corpus(Path("knowledge-base")), embedder, store)
    assert ingest(load_corpus(Path("knowledge-base")), embedder, store).embedded == 0
    retriever = Retriever(embedder, store)
    measured = evaluate_retrieval(
        retriever, Path("tests/evals/retrieval-queries.json"), mode="local-test-double"
    )
    report = explain(
        load_normalized(Path("examples/normalized-plans/public_bucket.json").read_bytes()),
        retriever,
        FixtureSynthesis(),
    )
    assert report.advisory is not None and report.overall_risk == "HIGH"
    target = Path("artifacts")
    target.mkdir(exist_ok=True)
    (target / "retrieval-local-evaluation.json").write_text(
        evaluation_json(measured), encoding="utf-8"
    )
    (target / "retrieval-demo-report.json").write_text(
        report.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    (target / "retrieval-demo-report.md").write_text(markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "mode": "local-test-double",
                "documents": result.documents,
                "chunks": result.chunks,
                "retrieval_hits_at_3": measured["hits_at_3"],
                "queries": 10,
                "cloud_calls": 0,
                "overall_risk": report.overall_risk,
            }
        )
    )


if __name__ == "__main__":
    main()
