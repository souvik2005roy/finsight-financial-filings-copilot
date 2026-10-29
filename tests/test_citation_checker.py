from checker import unverified_citations


def test_accepts_citation_present_in_retrieved_sources():
    citation = "[tata_motors_fy2025.pdf, PDF page 194]"

    assert unverified_citations(
        f"Reported EBIT margin was 7.9%. {citation}",
        [citation],
    ) == []


def test_flags_citation_not_present_in_retrieved_sources():
    answer = "Supplier risks are discussed in the report. [tata_motors_fy2025.pdf, PDF page 77]"
    sources = ["[tata_motors_fy2025.pdf, PDF page 194]"]

    assert unverified_citations(answer, sources) == [
        "[tata_motors_fy2025.pdf, PDF page 77]"
    ]


def test_ignores_sql_only_answer_without_pdf_citations():
    answer = "Reported EBIT margin was 7.9% in FY2025."

    assert unverified_citations(answer, ["financials table"]) == []


def test_normalizes_citation_case_and_whitespace():
    answer = "Source: [tata_motors_fy2025.pdf, PDF page 194]"
    sources = [" [TATA_MOTORS_FY2025.PDF, PDF PAGE 194] "]

    assert unverified_citations(answer, sources) == []


def test_returns_only_the_unverified_citation():
    answer = (
        "[tata_motors_fy2025.pdf, PDF page 194] "
        "[tata_motors_fy2025.pdf, PDF page 77]"
    )
    sources = ["[tata_motors_fy2025.pdf, PDF page 194]"]

    assert unverified_citations(answer, sources) == [
        "[tata_motors_fy2025.pdf, PDF page 77]"
    ]
