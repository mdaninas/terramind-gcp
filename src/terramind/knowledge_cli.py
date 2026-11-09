"""Explicit synthetic-only cloud operations; the offline CLI never imports this module."""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from pydantic import ValidationError

from terramind.cli import _write
from terramind.cloud.budget import CallBudget
from terramind.cloud.settings import CloudSettings
from terramind.errors import InputError
from terramind.llm.service import explain, policy_fallback
from terramind.normalizer.io import load_normalized, read_bounded
from terramind.rag.corpus import corpus_chunks, load_corpus
from terramind.reports.render import build_report, markdown
from terramind.schemas.normalized import MAX_REQUEST_BYTES, NormalizedPlan
from terramind.schemas.report import Report


def _analyze(plan: NormalizedPlan, settings: CloudSettings) -> tuple[Report, int]:
    base = build_report(plan)
    if not base.findings:
        return base, 0
    budget = CallBudget(seconds=25, per_call=20)
    try:
        from terramind.cloud.google import (
            FirestoreKnowledgeStore,
            GeminiSynthesizer,
            GoogleEmbedder,
        )
        from terramind.rag.retrieval import Retriever

        retriever = Retriever(
            GoogleEmbedder(settings, budget), FirestoreKnowledgeStore(settings, budget)
        )
        report = explain(
            plan, retriever, GeminiSynthesizer(settings, budget), language=settings.language
        )
        return report, budget.calls
    except Exception:
        return policy_fallback(
            base, "unavailable", "Cloud adapter or credentials unavailable."
        ), budget.calls


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Terramind synthetic knowledge operations")
    commands = parser.add_subparsers(dest="command", required=True)
    plan_parser = commands.add_parser("plan", help="Validate and count local synthetic documents")
    plan_parser.add_argument("--corpus", type=Path, default=Path("knowledge-base"))
    ingestion = commands.add_parser("ingest", help="Publish the approved synthetic corpus to GCP")
    ingestion.add_argument("--corpus", type=Path, default=Path("knowledge-base"))
    ingestion.add_argument(
        "--execute", action="store_true", help="Explicitly enable metered cloud calls"
    )
    analyze = commands.add_parser("analyze", help="Explain a synthetic normalized plan using GCP")
    analyze.add_argument("--input", type=Path, required=True)
    analyze.add_argument("--output", type=Path, required=True)
    analyze.add_argument("--format", choices=("json", "markdown"), default="json")
    analyze.add_argument("--execute", action="store_true")
    evaluate = commands.add_parser("evaluate", help="Run ten live retrieval queries")
    evaluate.add_argument(
        "--queries", type=Path, default=Path("tests/evals/retrieval-queries.json")
    )
    evaluate.add_argument("--output", type=Path, required=True)
    evaluate.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            documents = load_corpus(args.corpus)
            print(
                json.dumps(
                    {
                        "mode": "local-corpus-plan",
                        "documents": len(documents),
                        "chunks": len(corpus_chunks(documents)),
                        "cloud_calls": 0,
                    }
                )
            )
            return 0
        if not args.execute:
            raise InputError(
                "Cloud operations require --execute and approved project configuration"
            )
        documents = load_corpus(args.corpus) if args.command == "ingest" else ()
        plan = None
        if args.command == "analyze":
            if args.input.resolve() == args.output.resolve():
                raise InputError("Input and output must be different files")
            plan = load_normalized(read_bounded(args.input, MAX_REQUEST_BYTES))
            if plan.source != "synthetic-demo":
                raise InputError("Cloud demonstration accepts synthetic-demo facts only")
            report, calls = _analyze(plan, CloudSettings.from_env())
            _write(
                args.output,
                markdown(report) if args.format == "markdown" else report.model_dump_json(indent=2),
            )
            print(
                json.dumps(
                    {
                        "rag_status": report.rag_status,
                        "model_id": report.model_id,
                        "overall_risk": report.overall_risk,
                        "rpc_attempts": calls,
                    }
                )
            )
            return 0 if report.advisory is not None or not report.findings else 1
        # Optional SDK imports and credential discovery happen only after local validation.
        from terramind.cloud.google import (
            FirestoreKnowledgeStore,
            GoogleEmbedder,
            StorageSourcePublisher,
        )
        from terramind.rag.evaluation import evaluate_retrieval, evaluation_json
        from terramind.rag.ingestion import ingest
        from terramind.rag.retrieval import Retriever

        settings = CloudSettings.from_env()
        budget = CallBudget(
            seconds=240 if args.command == "ingest" else 120 if args.command == "evaluate" else 20,
            max_calls=200 if args.command == "ingest" else 50 if args.command == "evaluate" else 20,
        )
        embedder = GoogleEmbedder(settings, budget)
        store = FirestoreKnowledgeStore(settings, budget)
        if args.command == "ingest":
            result = ingest(documents, embedder, store, StorageSourcePublisher(settings, budget))
            print(
                json.dumps(
                    {"mode": "google-firestore", **asdict(result), "rpc_attempts": budget.calls}
                )
            )
            return 0
        retriever = Retriever(embedder, store)
        if args.command == "evaluate":
            measured = evaluate_retrieval(retriever, args.queries, mode="google-firestore")
            measured["rpc_attempts"] = budget.calls
            _write(args.output, evaluation_json(measured).rstrip())
            print(json.dumps({key: value for key, value in measured.items() if key != "results"}))
            return 0 if measured["passed"] else 1
        return 1
    except (InputError, ValidationError):
        print(
            "terramind-knowledge: invalid synthetic input or cloud configuration", file=sys.stderr
        )
        return 2
    except Exception:
        print(
            "terramind-knowledge: cloud operation unavailable; no provider details logged",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
