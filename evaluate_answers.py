
"""Evaluate FinSight answer quality without confusing API failures
with incorrect answers. Stops the benchmark when API quota is exhausted.
"""

import json
import re
from datetime import datetime
from pathlib import Path

from checker import unverified_numbers
from pipeline import FinSight


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)

# Manually reviewed questions and expected facts for the Tata Motors pilot.
CASES = [
    {
        "name": "FY2025 reported EBIT margin",
        "question": "What was Tata Motors' reported EBIT margin in FY2025?",
        "route": "sql",
        "expected_numbers": [7.9],
    },
    {
        "name": "FY2025 revenue",
        "question": (
            "What was Tata Motors consolidated revenue from operations "
            "in FY2025?"
        ),
        "route": "sql",
        "expected_numbers": [439695],
    },
    {
        "name": "EBIT margin change",
        "question": (
            "How did Tata Motors' reported EBIT margin change from "
            "FY2023 to FY2025? Give both values and the change in "
            "percentage points."
        ),
        "route": "sql",
        "expected_numbers": [3.6, 7.9, 4.3],
    },
    {
        "name": "Supply-chain risks",
        "question": (
            "What supply-chain risks does Tata Motors discuss, including "
            "supplier and logistics disruptions, raw-material shortages, "
            "and climate-related risks?"
        ),
        "route": "docs",
        "expected_pages": {
            ("tata_motors_fy2025.pdf", 75),
            ("tata_motors_fy2025.pdf", 194),
        },
    },
    {
        "name": "Climate and raw-material risks",
        "question": (
            "How could climate change cause shortages of essential "
            "automotive raw materials and affect vulnerable suppliers?"
        ),
        "route": "docs",
        "expected_pages": {
            ("tata_motors_fy2025.pdf", 194),
        },
    },
]

NUMBER_RE = re.compile(
    r"(?<![\w])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
)

CITATION_RE = re.compile(
    r"\[([^\]]+\.pdf\s*,\s*PDF page\s+\d+)\]",
    re.IGNORECASE,
)


def answer_numbers(text):
    """Extract numeric values from an answer."""
    values = []

    for item in NUMBER_RE.findall(text or ""):
        try:
            values.append(float(item.replace(",", "")))
        except ValueError:
            pass

    return values


def contains_value(text, target):
    """Check whether an expected number appears in the answer."""
    return any(
        abs(value - target) <= 0.02
        for value in answer_numbers(text)
    )


def page_pairs(labels):
    """Extract (filename, PDF page number) pairs from source labels."""
    found = set()

    for label in labels:
        match = re.search(
            r"([^,\[\]]+\.pdf)\s*,\s*PDF page\s+(\d+)",
            label,
            re.IGNORECASE,
        )

        if match:
            found.add(
                (match.group(1).strip(), int(match.group(2)))
            )

    return found


def normalized_citation(citation):
    """Normalize citation text before comparison."""
    return re.sub(
        r"\s+",
        " ",
        citation.strip(" []"),
    ).casefold()


def checker_sanity_tests():
    """Run checker sanity tests without calling the language model."""
    metadata_answer = (
        "Supply disruptions during FY2024–25 "
        "[tata_motors_fy2025.pdf, PDF page 75]."
    )
    metadata_evidence = (
        "Supplier disruptions can increase lead times."
    )

    metadata_pass = (
        unverified_numbers(metadata_answer, metadata_evidence) == []
    )

    invented_answer = "Raw-material costs increased by 18.5%."
    invented_evidence = (
        "Raw-material supply constraints remain a concern."
    )

    invented_pass = (
        18.5 in unverified_numbers(
            invented_answer,
            invented_evidence,
        )
    )

    return {
        "citation_and_year_handling": metadata_pass,
        "unsupported_percentage_caught": invented_pass,
    }


def is_api_failure(exc):
    """Identify API, network, timeout, authentication, or quota errors."""
    details = f"{type(exc).__name__}: {exc}".casefold()

    indicators = (
        "llm_api_key",
        "api key",
        "apitimeouterror",
        "apiconnectionerror",
        "internalservererror",
        "ratelimiterror",
        "authenticationerror",
        "permissiondeniederror",
        "request timed out",
        "timed out",
        "http 503",
        "http 429",
        "http 529",
        "503",
        "429",
        "529",
        "quota",
        "resource_exhausted",
        "unavailable",
        "service unavailable",
        "rate limit",
        "too many requests",
        "server requested retry",
    )

    return any(indicator in details for indicator in indicators)


def is_quota_exhaustion(exc):
    """Identify quota exhaustion that should stop the benchmark."""
    details = f"{type(exc).__name__}: {exc}".casefold()

    indicators = (
        "quota",
        "resource_exhausted",
        "quota exceeded",
        "http 429",
        "429",
        "rate limit",
        "ratelimiterror",
        "too many requests",
        "server requested retry after",
    )

    return any(indicator in details for indicator in indicators)


def rate_or_none(passed, denominator):
    """Return None instead of 0 when no questions were evaluated."""
    if denominator == 0:
        return None

    return passed / denominator


def format_rate(value):
    """Format an unavailable metric without presenting it as zero."""
    if value is None:
        return "N/A (no evaluated questions)"

    return f"{value:.1%}"


def build_summary(records, checker_results):
    """Calculate metrics using completed evaluations only."""
    total = len(records)

    completed = [
        record
        for record in records
        if record.get("status") == "completed"
    ]

    attempted = [
        record
        for record in records
        if record.get("status") in {
            "completed",
            "api_error",
            "evaluation_error",
        }
    ]

    sql_records = [
        record
        for record in completed
        if record.get("expected_route") == "sql"
    ]

    rag_records = [
        record
        for record in completed
        if record.get("expected_route") == "docs"
    ]

    api_failures = [
        record
        for record in records
        if record.get("status") == "api_error"
    ]

    evaluation_failures = [
        record
        for record in records
        if record.get("status") == "evaluation_error"
    ]

    skipped = [
        record
        for record in records
        if record.get("status") == "skipped"
    ]

    completed_count = len(completed)

    if total > 0 and completed_count == total:
        evaluation_status = "complete"
    elif completed_count == 0:
        evaluation_status = "blocked"
    else:
        evaluation_status = "incomplete"

    routing_passes = sum(
        record.get("route_pass") is True
        for record in completed
    )

    sql_passes = sum(
        record.get("answer_pass") is True
        for record in sql_records
    )

    rag_passes = sum(
        record.get("answer_pass") is True
        for record in rag_records
    )

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "evaluation_status": evaluation_status,
        "questions": total,
        "questions_attempted": len(attempted),
        "questions_completed": completed_count,
        "questions_failed": (
            len(api_failures) + len(evaluation_failures)
        ),
        "questions_skipped": len(skipped),
        "api_failures": len(api_failures),
        "evaluation_failures": len(evaluation_failures),
        "answer_failures": sum(
            record.get("answer_pass") is False
            for record in completed
        ),
        "routing_accuracy": rate_or_none(
            routing_passes,
            completed_count,
        ),
        "sql_answer_pass_rate": rate_or_none(
            sql_passes,
            len(sql_records),
        ),
        "rag_retrieval_and_citation_pass_rate": rate_or_none(
            rag_passes,
            len(rag_records),
        ),
        "checker_sanity_tests": checker_results,
        "failures": [
            {
                "name": record.get("name"),
                "status": record.get("status"),
                "error": record.get("error"),
                "reason": record.get("skip_reason"),
            }
            for record in records
            if record.get("status") != "completed"
        ],
        "results": records,
    }


def save_summary(records, checker_results):
    """Write the evaluation report and print its summary."""
    summary = build_summary(records, checker_results)
    output_path = RESULTS / "answer_eval_latest.json"

    output_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n" + "=" * 72)
    print("EVALUATION SUMMARY")
    print("Status:", summary["evaluation_status"].upper())
    print(
        "Questions completed:",
        f"{summary['questions_completed']}/"
        f"{summary['questions']}",
    )
    print("Questions attempted:", summary["questions_attempted"])
    print("Questions failed:", summary["questions_failed"])
    print("Questions skipped:", summary["questions_skipped"])
    print("API failures:", summary["api_failures"])
    print("Other evaluation failures:", summary["evaluation_failures"])
    print("Answer failures:", summary["answer_failures"])
    print("Routing accuracy:", format_rate(summary["routing_accuracy"]))
    print(
        "SQL answer pass rate:",
        format_rate(summary["sql_answer_pass_rate"]),
    )
    print(
        "RAG retrieval/citation pass rate:",
        format_rate(summary["rag_retrieval_and_citation_pass_rate"]),
    )
    print("Results saved to:", output_path)

    return summary


def append_skipped(records, cases, reason):
    """Record unevaluated cases without treating them as failed answers."""
    for case in cases:
        records.append({
            "name": case["name"],
            "question": case["question"],
            "expected_route": case["route"],
            "status": "skipped",
            "skip_reason": reason,
        })


def main():
    checker_results = checker_sanity_tests()

    print("NUMBER-CHECKER SANITY TESTS")

    for name, passed in checker_results.items():
        print(f"  {name}: {'PASS' if passed else 'FAIL'}")

    if not all(checker_results.values()):
        print("WARNING: Fix the number checker before trusting evaluation.")

    financial_csv = str(
        ROOT / "data" / "financials_tata_motors_v2.csv"
    )
    docs_dir = str(ROOT / "data" / "docs")

    records = []
    bot = None

    print("\nLoading FinSight...")

    # Handle initialization errors without a traceback or misleading scores.
    try:
        bot = FinSight(csv=financial_csv, docs=docs_dir)
    except Exception as exc:
        status = (
            "api_error"
            if is_api_failure(exc)
            else "evaluation_error"
        )

        print(
            "INITIALIZATION FAILURE:",
            type(exc).__name__,
            str(exc),
        )

        if CASES:
            records.append({
                "name": CASES[0]["name"],
                "question": CASES[0]["question"],
                "expected_route": CASES[0]["route"],
                "status": status,
                "error_type": type(exc).__name__,
                "error": str(exc),
            })

            append_skipped(
                records,
                CASES[1:],
                "FinSight initialization failed before evaluation began.",
            )

        save_summary(records, checker_results)
        return

    try:
        for case_index, case in enumerate(CASES):
            print("\n" + "=" * 72)
            print("QUESTION:", case["name"])
            print(case["question"])

            record = {
                "name": case["name"],
                "question": case["question"],
                "expected_route": case["route"],
                "status": "pending",
            }

            stop_for_quota = False

            try:
                output = bot.ask(
                    case["question"],
                    mode="hybrid",
                )

                answer = output.get("answer") or ""
                route = output.get("route")
                sql = output.get("sql")
                sources = output.get("sources") or []
                warnings = output.get("unverified") or []

                record.update({
                    "actual_route": route,
                    "route_pass": route == case["route"],
                    "answer": answer,
                    "sql": sql,
                    "sources": sources,
                    "unverified_numbers": warnings,
                })

                print("\nROUTE:", route)
                print("ANSWER:\n", answer)
                print("SQL:", sql)
                print("SOURCES:", sources)
                print("UNVERIFIED:", warnings)

                print(
                    "ROUTE CHECK:",
                    "PASS" if record["route_pass"] else "FAIL",
                )

                if case["route"] == "sql":
                    number_checks = {
                        str(value): contains_value(answer, value)
                        for value in case["expected_numbers"]
                    }

                    answer_pass = (
                        route == "sql"
                        and bool(sql)
                        and all(number_checks.values())
                        and not warnings
                    )

                    record["expected_number_checks"] = number_checks
                    record["answer_pass"] = answer_pass

                    print("EXPECTED NUMBER CHECKS:", number_checks)
                    print(
                        "SQL ANSWER CHECK:",
                        "PASS" if answer_pass else "FAIL",
                    )

                else:
                    retrieved_pages = page_pairs(sources)
                    expected_pages = case["expected_pages"]

                    cited = {
                        normalized_citation(item)
                        for item in CITATION_RE.findall(answer)
                    }

                    available = {
                        normalized_citation(item)
                        for item in sources
                    }

                    citation_present = bool(cited)
                    citations_grounded = (
                        citation_present
                        and cited.issubset(available)
                    )

                    expected_pages_found = expected_pages.issubset(
                        retrieved_pages
                    )

                    rag_pass = (
                        route == "docs"
                        and citations_grounded
                        and expected_pages_found
                    )

                    record.update({
                        "retrieved_pages": sorted(
                            [list(pair) for pair in retrieved_pages]
                        ),
                        "expected_pages": sorted(
                            [list(pair) for pair in expected_pages]
                        ),
                        "expected_pages_found": expected_pages_found,
                        "citations_present": citation_present,
                        "citations_grounded_in_retrieved_sources":
                            citations_grounded,
                        "answer_pass": rag_pass,
                    })

                    print("EXPECTED PAGES FOUND:", expected_pages_found)
                    print("CITATIONS PRESENT:", citation_present)
                    print(
                        "CITATIONS MATCH RETRIEVED SOURCES:",
                        citations_grounded,
                    )
                    print(
                        "RAG CHECK:",
                        "PASS" if rag_pass else "FAIL",
                    )

                # Only completed checks contribute to quality metrics.
                record["status"] = "completed"

            except Exception as exc:
                status = (
                    "api_error"
                    if is_api_failure(exc)
                    else "evaluation_error"
                )

                record.update({
                    "status": status,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                })

                print(
                    "API FAILURE:" if status == "api_error"
                    else "EVALUATION ERROR:",
                    type(exc).__name__,
                    str(exc),
                )

                stop_for_quota = (
                    status == "api_error"
                    and is_quota_exhaustion(exc)
                )

            records.append(record)

            if stop_for_quota:
                print(
                    "\nQuota exhaustion detected. "
                    "Skipping the remaining evaluation questions."
                )

                append_skipped(
                    records,
                    CASES[case_index + 1:],
                    "Skipped because an earlier request exhausted API quota.",
                )
                break

    finally:
        connection = getattr(bot, "conn", None)

        if connection is not None and hasattr(connection, "close"):
            connection.close()

    save_summary(records, checker_results)


if __name__ == "__main__":
    main()

