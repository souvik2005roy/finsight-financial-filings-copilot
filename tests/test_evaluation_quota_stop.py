import evaluate_answers as ea


def test_quota_exhaustion_skips_remaining_questions(monkeypatch):
    class FakeBot:
        def __init__(self):
            self.calls = []

        def ask(self, question, mode="hybrid"):
            self.calls.append(question)
            raise RuntimeError(
                "Server requested retry after 52917s. "
                "This is treated as a quota exhaustion."
            )

    bot = FakeBot()
    captured = {}

    cases = [
        {
            "name": "Question 1",
            "question": "What was the reported EBIT margin?",
            "route": "sql",
            "expected_numbers": [7.9],
        },
        {
            "name": "Question 2",
            "question": "What was revenue?",
            "route": "sql",
            "expected_numbers": [439695],
        },
        {
            "name": "Question 3",
            "question": "What supply-chain risks were reported?",
            "route": "docs",
            "expected_pages": set(),
        },
    ]

    monkeypatch.setattr(ea, "FinSight", lambda **kwargs: bot)
    monkeypatch.setattr(ea, "CASES", cases)

    def capture_summary(records, checker_results):
        captured["records"] = list(records)
        captured["checker_results"] = checker_results

    monkeypatch.setattr(ea, "save_summary", capture_summary)

    ea.main()

    # Only the first question should reach the fake client.
    assert len(bot.calls) == 1

    records = captured["records"]
    assert [r["status"] for r in records] == [
        "api_error",
        "skipped",
        "skipped",
    ]

    summary = ea.build_summary(
        records,
        captured["checker_results"],
    )

    assert summary["evaluation_status"] == "blocked"
    assert summary["questions_attempted"] == 1
    assert summary["questions_completed"] == 0
    assert summary["questions_failed"] == 1
    assert summary["questions_skipped"] == 2

    assert summary["routing_accuracy"] is None
    assert summary["sql_answer_pass_rate"] is None
    assert summary["rag_retrieval_and_citation_pass_rate"] is None


def test_temporary_timeout_is_not_quota_exhaustion():
    error = TimeoutError("Request timed out.")

    assert ea.is_api_failure(error) is True
    assert ea.is_quota_exhaustion(error) is False
