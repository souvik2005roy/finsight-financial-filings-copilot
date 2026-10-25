
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

# Units that make a number meaningful even when it is small.
EXPLICIT_UNIT = re.compile(
    r"\s*(?:%|percent\b|percentage(?:\s+points?)?\b|"
    r"percentage-point\b|crores?\b|cr\b|lakhs?\b|"
    r"million\b|billion\b|rupees?\b|dollars?\b)",
    re.IGNORECASE,
)

CURRENCY_PREFIX = re.compile(
    r"(?:₹|INR|USD|Rs\.?)\s*$",
    re.IGNORECASE,
)

# Financial terminology immediately before a number suggests a claim.
FINANCIAL_CONTEXT = re.compile(
    r"\b(?:margin|profit|revenue|sales|EBIT|EBITDA|income|"
    r"debt|cost|growth|rate|ratio|return|cash\s+flow|"
    r"assets|liabilities|expense|earnings|turnover)\b",
    re.IGNORECASE,
)


def numbers_in(text):
    """Extract numeric values from text."""
    out = []

    for match in NUMBER.findall(text):
        try:
            out.append(float(match.replace(",", "").rstrip(".")))
        except ValueError:
            pass

    return out


def _clean_answer_for_number_check(answer):
    """Remove citation metadata and fiscal-year labels."""
    answer = CITATION.sub(" ", answer)
    answer = FISCAL_YEAR.sub(" ", answer)
    return answer


def unverified_numbers(answer, evidence, tol=0.01):
    """Return answer numbers not supported by the supplied evidence.

    Ignores citation metadata, fiscal-year labels, calendar years,
    and small whole numbers used as ordinary counts or list markers.
    Small numbers with units or financial context are still checked.

    Note: This is a heuristic evidence check, not a semantic
    verification of whether a number belongs to the correct metric.
    """
    known = numbers_in(evidence)
    cleaned_answer = _clean_answer_for_number_check(answer)
    bad = []

    for match in NUMBER.finditer(cleaned_answer):
        token = match.group()

        try:
            number = float(token.replace(",", "").rstrip("."))
        except ValueError:
            continue

        # Calendar years are labels, not financial claims.
        if number.is_integer() and 1900 <= number <= 2100:
            continue

        suffix = cleaned_answer[match.end():]
        prefix = cleaned_answer[:match.start()]

        has_unit = bool(EXPLICIT_UNIT.match(suffix))
        has_currency = bool(CURRENCY_PREFIX.search(prefix))
        has_financial_context = bool(
            FINANCIAL_CONTEXT.search(prefix[-80:])
        )

        # Ignore small whole numbers used as counts/list markers,
        # but check them when they express a financial claim.
        if (
            number.is_integer()
            and abs(number) <= 10
            and not has_unit
            and not has_currency
            and not has_financial_context
        ):
            continue

        # Check whether the answer number is supported by evidence.
        if not any(
            abs(number - value) <= max(0.06, tol * abs(value))
            for value in known
        ):
            bad.append(number)

    return bad


