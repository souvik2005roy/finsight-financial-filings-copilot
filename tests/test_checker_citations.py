from checker import unverified_numbers


def test_checker_ignores_pdf_page_citations():
    answer = (
        "Supply disruptions may affect production "
        "[tata_motors_fy2025.pdf, PDF page 75, PDF page 194]."
    )
    assert unverified_numbers(
        answer, "Supply disruptions can affect production."
    ) == []


def test_checker_ignores_fiscal_year_ranges():
    answer = "The report discusses risks in FY2024–25."
    assert unverified_numbers(answer, "The report discusses risks.") == []


def test_checker_still_flags_unsupported_financial_percentage():
    answer = "Raw material costs increased by 18.5%."
    evidence = "Raw material supply constraints remain a concern."
    assert unverified_numbers(answer, evidence) == [18.5]
