
from evaluate_answers import build_summary


def test_api_failure_is_excluded_from_metrics():
    records = [
        {
            "name": "SQL success",
            "expected_route": "sql",
            "status": "completed",
            "route_pass": True,
            "answer_pass": True,
        },
        {
            "name": "SQL timeout",
            "expected_route": "sql",
            "status": "api_error",
            "error": "APITimeoutError: Request timed out",
        },
        {
            "name": "RAG incorrect answer",
            "expected_route": "docs",
            "status": "completed",
            "route_pass": True,
            "answer_pass": False,
        },
    ]

    summary = build_summary(records, {"checker_test": True})

    assert summary["evaluation_status"] == "incomplete"
    assert summary["questions_attempted"] == 3
    assert summary["questions_completed"] == 2
    assert summary["questions_failed"] == 1
    assert summary["api_failures"] == 1

    assert summary["routing_accuracy"] == 1.0
    assert summary["sql_answer_pass_rate"] == 1.0
    assert summary["rag_retrieval_and_citation_pass_rate"] == 0.0


def test_no_successful_questions_produces_unavailable_metrics():
    records = [
        {
            "name": "SQL timeout",
            "expected_route": "sql",
            "status": "api_error",
            "error": "APITimeoutError",
        },
    ]

    summary = build_summary(records, {"checker_test": True})

    assert summary["evaluation_status"] == "blocked"
    assert summary["questions_completed"] == 0
    assert summary["routing_accuracy"] is None
    assert summary["sql_answer_pass_rate"] is None
    assert summary["rag_retrieval_and_citation_pass_rate"] is None
