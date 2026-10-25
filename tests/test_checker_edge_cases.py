
from checker import unverified_numbers


def test_supported_financial_numbers_are_not_flagged():
    answer = (
        "EBIT margin rose from 3.6% in FY2023 to 7.9% "
        "in FY2025, an increase of 4.3 percentage points."
    )
    evidence = (
        "Reported EBIT margin: FY2023 3.6%, FY2025 7.9%. "
        "The change was 4.3 percentage points."
    )

    assert unverified_numbers(answer, evidence) == []


def test_unsupported_percentage_is_flagged():
    answer = "The reported EBIT margin reached 12.5%."
    evidence = "The reported EBIT margin was 7.9%."

    assert unverified_numbers(answer, evidence) == [12.5]


def test_pdf_citation_page_numbers_are_ignored():
    answer = (
        "Climate risks may affect supply chains "
        "[tata_motors_fy2025.pdf, PDF page 77]."
    )
    evidence = "Climate risks may affect supply chains."

    assert unverified_numbers(answer, evidence) == []


def test_comma_formatted_financial_value_is_recognized():
    answer = "Revenue was 439,695 crore."
    evidence = "Revenue from operations was 439,695 crore."

    assert unverified_numbers(answer, evidence) == []


def test_small_list_numbers_are_not_flagged():
    answer = (
        "The key risks are 1. supplier disruption "
        "and 2. climate exposure."
    )
    evidence = "Supplier disruption and climate exposure."

    assert unverified_numbers(answer, evidence) == []

def test_unsupported_small_percentage_is_flagged():
    answer = "The reported EBIT margin was 5%."
    evidence = "The reported EBIT margin was 7.9%."

    assert unverified_numbers(answer, evidence) == [5.0]