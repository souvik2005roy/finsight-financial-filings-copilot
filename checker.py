
"""Flag numeric claims not supported by supplied evidence."""

import re

NUMBER = re.compile(r"(?<![\w.])-?\d[\d,]*\.?\d*")

CITATION = re.compile(
    r"\[[^\]]*(?:\.pdf\b|PDF\s+page)[^\]]*\]",
    re.IGNORECASE,
)

FISCAL_YEAR = re.compile(
    r"\bFY\s*\d{2,4}(?:\s*[-–/]\s*\d{2,4})?\b",
    re.IGNORECASE,
)

FISCAL_YEAR_VALUE = re.compile(
    r"\bFY\s*(\d{2,4})\b",
    re.IGNORECASE,
)

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

FINANCIAL_CONTEXT = re.compile(
    r"\b(?:margin|profit|revenue|sales|EBIT|EBITDA|income|"
    r"debt|cost|growth|rate|ratio|return|cash\s+flow|"
    r"assets|liabilities|expense|earnings|turnover)\b",
    re.IGNORECASE,
)

# Specific metric phrases are listed before general terms.
METRIC_PATTERNS = [
    ("ebitda_margin", re.compile(r"\bEBITDA\s+margin\b", re.I)),
    ("ebit_margin", re.compile(r"\bEBIT\s+margin\b", re.I)),
    ("operating_margin", re.compile(r"\boperating\s+margin\b", re.I)),
    ("gross_margin", re.compile(r"\bgross\s+margin\b", re.I)),
    ("net_margin", re.compile(r"\bnet\s+margin\b", re.I)),
    (
        "revenue_growth",
        re.compile(r"\b(?:revenue|sales)\s+growth\b", re.I),
    ),
    ("operating_profit", re.compile(r"\boperating\s+profit\b", re.I)),
    ("net_profit", re.compile(r"\bnet\s+profit\b", re.I)),
    ("revenue", re.compile(r"\b(?:revenue|sales|turnover)\b", re.I)),
    ("profit", re.compile(r"\bprofit\b", re.I)),
    ("debt", re.compile(r"\bdebt\b", re.I)),
    ("margin", re.compile(r"\bmargin\b", re.I)),
    ("growth", re.compile(r"\bgrowth\b", re.I)),
]


def numbers_in(text):
    """Extract numeric values from text."""
    result = []

    for match in NUMBER.findall(text):
        try:
            result.append(float(match.replace(",", "").rstrip(".")))
        except ValueError:
            pass

    return result


def _mask_matches(pattern, text):
    """Replace matches with spaces while preserving text positions."""
    return pattern.sub(
        lambda match: " " * len(match.group()),
        text,
    )


def _clean_answer_for_number_check(answer):
    """Mask citations and fiscal-year labels without shifting positions."""
    answer = _mask_matches(CITATION, answer)
    return _mask_matches(FISCAL_YEAR, answer)


def _sentence_bounds(text, position):
    """Find the sentence containing a character position."""
    start = 0

    for index, char in enumerate(text[:position]):
        if char == "\n":
            start = index + 1
        elif (
            char in ".!?"
            and (index + 1 == len(text) or text[index + 1].isspace())
        ):
            start = index + 1

    end = len(text)

    for index in range(position, len(text)):
        char = text[index]

        if char == "\n":
            end = index
            break

        if (
            char in ".!?"
            and (index + 1 == len(text) or text[index + 1].isspace())
        ):
            end = index + 1
            break

    while start < end and text[start].isspace():
        start += 1

    return start, end


def _context_for_number(text, start, end):
    """Infer the nearest metric and fiscal year for a numeric value."""
    sentence_start, sentence_end = _sentence_bounds(text, start)
    sentence = text[sentence_start:sentence_end]

    number_start = start - sentence_start
    number_end = end - sentence_start

    # Find the closest financial metric in the sentence.
    metric_candidates = []

    for metric_name, pattern in METRIC_PATTERNS:
        for match in pattern.finditer(sentence):
            if match.end() <= number_start:
                distance = number_start - match.end()
            elif match.start() >= number_end:
                distance = match.start() - number_end
            else:
                distance = 0

            metric_candidates.append(
                (distance, -len(match.group()), metric_name)
            )

    metric = min(metric_candidates)[2] if metric_candidates else None

    # First, look for an explicit year following the numeric value.
    # Examples: "7.9% in FY2025", "revenue of 5 crore for FY2025".
    tail = sentence[number_end:]

    after_value_year = re.match(
        r"\s*(?:%|percent\b|percentage(?:\s+points?)?\b|"
        r"percentage-point\b|crores?\b|cr\b|lakhs?\b|"
        r"million\b|billion\b|rupees?\b|dollars?\b)?"
        r"\s*(?:in|for|during|as of)\s+FY\s*(\d{2,4})\b",
        tail,
        re.IGNORECASE,
    )

    if after_value_year:
        year_text = after_value_year.group(1)
        year = int(year_text)

        if len(year_text) == 2:
            year += 2000

        return metric, year

    # Otherwise, use the nearest year in the sentence.
    # Prefer a year before the value if distances are equal.
    year_candidates = []

    for match in FISCAL_YEAR_VALUE.finditer(sentence):
        year_text = match.group(1)
        year = int(year_text)

        if len(year_text) == 2:
            year += 2000

        if match.end() <= number_start:
            distance = number_start - match.end()
            side_priority = 0
        elif match.start() >= number_end:
            distance = match.start() - number_end
            side_priority = 1
        else:
            distance = 0
            side_priority = 0

        year_candidates.append((distance, side_priority, year))

    year = min(year_candidates)[2] if year_candidates else None

    return metric, year


def unverified_numbers(answer, evidence, tol=0.01):
    """Flag numbers unsupported by the supplied evidence.

    Numbers are compared using a tolerance. Where possible, matching
    values must also share the same inferred metric and fiscal year.

    This is a heuristic check, not a complete semantic fact verifier.
    """
    answer_context = _mask_matches(CITATION, answer)
    evidence_context = _mask_matches(CITATION, evidence)
    cleaned_answer = _clean_answer_for_number_check(answer)

    evidence_numbers = []

    for match in NUMBER.finditer(evidence_context):
        try:
            value = float(match.group().replace(",", "").rstrip("."))
        except ValueError:
            continue

        context = _context_for_number(
            evidence_context,
            match.start(),
            match.end(),
        )

        evidence_numbers.append((value, context))

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

        # Ignore ordinary small counts and list markers, but retain
        # small numbers that express financial claims or have units.
        if (
            number.is_integer()
            and abs(number) <= 10
            and not has_unit
            and not has_currency
            and not has_financial_context
        ):
            continue

        answer_metric, answer_year = _context_for_number(
            answer_context,
            match.start(),
            match.end(),
        )

        supported = False

        for evidence_value, evidence_context_info in evidence_numbers:
            tolerance = max(0.06, tol * abs(evidence_value))

            if abs(number - evidence_value) > tolerance:
                continue

            evidence_metric, evidence_year = evidence_context_info

            # Do not accept a figure associated with another metric.
            if (
                answer_metric is not None
                and evidence_metric is not None
                and answer_metric != evidence_metric
            ):
                continue

            # Do not accept a figure associated with another year.
            if (
                answer_year is not None
                and evidence_year is not None
                and answer_year != evidence_year
            ):
                continue

            supported = True
            break

        if not supported:
            bad.append(number)

    return bad




def unverified_citations(answer: str, sources: list[str]) -> list[str]:
    """
    Detect PDF-page citations in an answer that do not appear
    in the retrieved-source list.

    Supports grouped citations containing multiple PDF pages.
    """

    import re

    citation_pattern = re.compile(
        r"(?P<filename>[\w.-]+\.pdf)"
        r"\s*,\s*PDF\s+page\s+"
        r"(?P<page>\d+)",
        re.IGNORECASE,
    )

    # Extract all valid citations from the retrieved sources.
    valid_sources = set()

    for source in sources or []:
        for match in citation_pattern.finditer(str(source)):
            filename = match.group("filename").casefold()
            page = int(match.group("page"))

            valid_sources.add((filename, page))

    # Check every individual PDF-page reference in the answer.
    unverified = []
    seen = set()

    for match in citation_pattern.finditer(str(answer or "")):
        filename = match.group("filename")
        page = int(match.group("page"))

        key = (filename.casefold(), page)

        if key not in valid_sources and key not in seen:
            seen.add(key)
            unverified.append(
                f"[{filename}, PDF page {page}]"
            )

    return unverified
