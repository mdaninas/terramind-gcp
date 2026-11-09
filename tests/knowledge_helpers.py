"""Explicit local doubles shared by integration and adversarial contract tests."""

import json
from pathlib import Path

from terramind.rag.corpus import load_corpus
from terramind.rag.ingestion import ingest
from terramind.rag.local import LexicalTestEmbedder, MemoryKnowledgeStore
from terramind.rag.retrieval import Retriever


class CountingEmbedder(LexicalTestEmbedder):
    def __init__(self):
        self.calls = []

    def embed(self, text, *, task, title=""):
        self.calls.append((task, text, title))
        return super().embed(text, task=task, title=title)


class RecordingSynthesizer:
    model_id = "fixture-synthesis-not-gemini"

    def __init__(self, transform=None):
        self.prompts = []
        self.transform = transform

    def generate(self, prompt):
        self.prompts.append(prompt)
        data = json.loads(prompt)
        explanations = [
            {
                "finding_id": finding["finding_id"],
                "text": finding["facts"]["rationale"],
                "citation_ids": [finding["allowed_citation_ids"][0]],
            }
            for finding in data["findings"]
        ]
        value = {
            "summary": "Review the proposed changes and their deterministic findings.",
            "explanations": explanations,
            "recommendations": ["Review the original change locally before any deployment."],
            "citations": list(
                dict.fromkeys(c for item in explanations for c in item["citation_ids"])
            ),
            "limitations": ["Local test double; no Gemini quality claim."],
        }
        if self.transform:
            value = self.transform(value)
        return value if isinstance(value, str) else json.dumps(value)


def local_system():
    documents = load_corpus(Path("knowledge-base"))
    embedder, store = CountingEmbedder(), MemoryKnowledgeStore()
    ingest(documents, embedder, store)
    embedder.calls.clear()
    return documents, embedder, store, Retriever(embedder, store)
