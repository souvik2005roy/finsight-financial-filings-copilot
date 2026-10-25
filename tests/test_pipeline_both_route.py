import pipeline
from pipeline import FinSight


def test_both_route_combines_sql_and_report_evidence(monkeypatch):
    """Verify the integrated answer receives both evidence sources."""

    sql_result = (
        "Reported EBIT margin: 7.9%",
        "SELECT ebit_margin_pct FROM financials WHERE fiscal_year = 2025",
        "fiscal_year | ebit_margin_pct\n2025 | 7.9",
    )

    citation = "[tata_motors_fy2025.pdf, PDF page 194]"
    report_text = (
        "Supplier disruptions and raw-material shortages may affect operations."
    )

    class FakeRetriever:
        chunks = [report_text]

        def search(
            self, query, k=4, mode="hybrid", diversify_pages=False
        ):
            assert mode == "hybrid"
            assert diversify_pages is True
            return [0]

        def citation_for(self, idx):
            return citation

    prompts = []

    def fake_llm(prompt):
        prompts.append(prompt)
        return (
            "Reported EBIT margin was 7.9%. "
            f"Supplier risks are discussed {citation}"
        )

    monkeypatch.setattr(pipeline, "sql_answer", lambda *args: sql_result)
    monkeypatch.setattr(pipeline, "ask_llm", fake_llm)

    bot = FinSight.__new__(FinSight)
    bot.conn = object()
    bot.schema = "financials(fiscal_year, ebit_margin_pct)"
    bot.sample = "FY2025 | 7.9"
    bot.retriever = FakeRetriever()

    answer, sql, sources, evidence = bot._both_answer(
        "How did margins change and what supply-chain risks matter?"
    )

    # The final LLM call must see both types of evidence.
    assert len(prompts) == 1
    assert "2025 | 7.9" in prompts[0]
    assert report_text in prompts[0]
    assert citation in prompts[0]

    assert sql == sql_result[1]
    assert answer
    assert "financials table" in sources
    assert citation in sources
    assert sql_result[2] in evidence
    assert report_text in evidence


def test_ask_dispatches_both_route(monkeypatch):
    """Verify ask() returns the combined route's output correctly."""

    bot = FinSight.__new__(FinSight)
    citation = "[tata_motors_fy2025.pdf, PDF page 194]"

    monkeypatch.setattr(bot, "route", lambda question: "both")
    monkeypatch.setattr(
        bot,
        "_both_answer",
        lambda question, mode="hybrid": (
            "Combined financial and risk answer.",
            "SELECT ebit_margin_pct FROM financials",
            ["financials table", citation],
            "SQL evidence and annual-report evidence.",
        ),
    )
    monkeypatch.setattr(
        pipeline,
        "unverified_numbers",
        lambda answer, evidence: [],
    )

    result = bot.ask("Combine the financial result and report risks.")

    assert result["route"] == "both"
    assert result["answer"] == "Combined financial and risk answer."
    assert result["sql"] == "SELECT ebit_margin_pct FROM financials"
    assert "financials table" in result["sources"]
    assert citation in result["sources"]
    assert result["evidence"] == "SQL evidence and annual-report evidence."
    assert result["unverified"] == []
