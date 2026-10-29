from pipeline import FinSight


def make_both_route_bot(monkeypatch, answer, evidence):
    bot = FinSight.__new__(FinSight)

    monkeypatch.setattr(bot, "route", lambda question: "both")
    monkeypatch.setattr(
        bot,
        "_both_answer",
        lambda question, mode="hybrid": (
            answer,
            "SELECT ebit_margin_pct FROM financials WHERE fiscal_year = 2025",
            [
                "financials table",
                "[tata_motors_fy2025.pdf, PDF page 194]",
            ],
            evidence,
        ),
    )

    return bot


def test_both_route_accepts_supported_financial_figure(monkeypatch):
    citation = "[tata_motors_fy2025.pdf, PDF page 194]"
    answer = (
        f"Reported EBIT margin was 7.9% in FY2025. "
        f"Supplier disruptions may affect operations. {citation}"
    )
    evidence = (
        "Reported EBIT margin was 7.9% in FY2025. "
        "Supplier disruptions may affect operations. "
        f"{citation}"
    )

    bot = make_both_route_bot(monkeypatch, answer, evidence)
    result = bot.ask("Summarize margins and supply-chain risks")

    assert result["route"] == "both"
    assert result["unverified"] == []
    assert "7.9%" in result["answer"]


def test_both_route_flags_unsupported_numerical_claim(monkeypatch):
    citation = "[tata_motors_fy2025.pdf, PDF page 194]"
    answer = (
        f"Reported EBIT margin was 7.9% in FY2025. "
        f"Supplier disruptions caused ₹900 crore in losses. {citation}"
    )
    evidence = (
        "Reported EBIT margin was 7.9% in FY2025. "
        "Supplier disruptions may affect operations. "
        f"{citation}"
    )

    bot = make_both_route_bot(monkeypatch, answer, evidence)
    result = bot.ask("Summarize margins and supply-chain risks")

    assert result["route"] == "both"
    assert result["unverified"], (
        "The checker should flag the unsupported ₹900 crore claim."
    )


def test_both_route_flags_citation_missing_from_retrieved_sources(monkeypatch):
    unsupported_citation = "[tata_motors_fy2025.pdf, PDF page 77]"
    answer = (
        "Supplier risks are discussed in the report. "
        f"{unsupported_citation}"
    )
    evidence = (
        "Supplier disruptions may affect operations. "
        "[tata_motors_fy2025.pdf, PDF page 194]"
    )

    bot = make_both_route_bot(monkeypatch, answer, evidence)
    result = bot.ask("Summarize margins and supply-chain risks")

    assert result["route"] == "both"
    assert result["unverified_citations"] == [
        unsupported_citation
    ]
    assert "Citation verification warning" in result["answer"]
