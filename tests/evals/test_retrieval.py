from pathlib import Path

from terramind.rag.evaluation import evaluate_retrieval
from tests.knowledge_helpers import local_system


def test_ten_curated_queries_using_local_lexical_test_double():
    _, _, _, retriever = local_system()
    result = evaluate_retrieval(
        retriever, Path("tests/evals/retrieval-queries.json"), mode="local-test-double"
    )
    assert result["mode"] == "local-test-double"
    assert result["queries"] == 10
    assert result["passed"], result
