"""Flag numeric claims not supported by the supplied evidence."""
import re

NUMBER = re.compile(r"(?<![\w.])-?\d[\d,]*\.?\d*")

# Citation metadata is not a financial claim.
CITATION = re.compile(
    r"\[[^\]]*(?:\.pdf\b|PDF\s+page)[^\]]*\]",
    re.IGNORECASE,
)

# Fiscal years and ranges are labels, not financial metrics.
FISCAL_YEAR = re.compile(
    r"\bFY\s*\d{2,4}(?:\s*[-–/]\s*\d{2,4})?\b",
    re.IGNORECASE,
)


def numbers_in(text):
    out = []
    for match in NUMBER.findall(text):
        try:
            out.append(float(match.replace(",", "").rstrip(".")))
        except ValueError:
            pass
    return out


def _clean_answer_for_number_check(answer):
    answer = CITATION.sub(" ", answer)
    answer = FISCAL_YEAR.sub(" ", answer)
    return answer


def unverified_numbers(answer, evidence, tol=0.01):
    """Return answer numbers not found in the supplied evidence.

    Ignores PDF page citations, fiscal-year labels, calendar years
    from 1900 to 2100, and small whole numbers such as list items.
    """
    known = numbers_in(evidence)
    answer_numbers = numbers_in(_clean_answer_for_number_check(answer))
    bad = []

    for number in answer_numbers:
        if number == int(number) and (
            1900 <= number <= 2100 or abs(number) <= 10
        ):
            continue

        if not any(
            abs(number - value) <= max(0.06, tol * abs(value))
            for value in known
        ):
            bad.append(number)

    return bad
