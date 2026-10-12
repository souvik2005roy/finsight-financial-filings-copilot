import json
import re
from datetime import datetime
from pathlib import Path

from checker import unverified_numbers
from pipeline import FinSight

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)

# Fixed questions and expected facts, based on our current pilot dataset
# and the manually reviewed Tata Motors annual-report pages.
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
    values = []
    for item in NUMBER_RE.findall(text or ""):
        try:
            values.append(float(item.replace(",", "")))
        except ValueError:
            pass
    return values


def contains_value(text, target):
    return any(
        abs(value - target) <= 0.02
        for value in answer_numbers(text)
    )


def page_pairs(labels):
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
    return re.sub(r"\s+", " ", citation.strip(" []")).casefold()


def checker_sanity_tests():
    # Citation page numbers and fiscal-year labels must not trigger warnings.
    metadata_answer = (
        "Supply disruptions during FY2024–25 "
        "[tata_motors_fy2025.pdf, PDF page 75]."
    )
    metadata_evidence = "Supplier disruptions can increase lead times."
    metadata_pass = (
        unverified_numbers(metadata_answer, metadata_evidence) == []
    )

    # A deliberately unsupported financial percentage should be flagged.
    invented_answer = "Raw-material costs increased by 18.5%."
    invented_evidence = "Raw-material supply constraints remain a concern."
    invented_pass = (
        18.5 in unverified_numbers(invented_answer, invented_evidence)
    )

    return {
        "citation_and_year_handling": metadata_pass,
        "unsupported_percentage_caught": invented_pass,
    }


def main():
    checker_results = checker_sanity_tests()

    print("NUMBER-CHECKER SANITY TESTS")
    for name, passed in checker_results.items():
        print(f"  {name}: {'PASS' if passed else 'FAIL'}")

    if not all(checker_results.values()):
        print("Fix the number checker before trusting the evaluation.")

    financial_csv = "data/financials_tata_motors_v2.csv"
    docs_dir = "data/docs"

    print("\nLoading FinSight...")
    bot = FinSight(csv=financial_csv, docs=docs_dir)

    records = []

    try:
        for case in CASES:
            print("\n" + "=" * 72)
            print("QUESTION:", case["name"])
            print(case["question"])

            record = {
                "name": case["name"],
                "question": case["question"],
                "expected_route": case["route"],
            }

            try:
                output = bot.ask(case["question"], mode="hybrid")
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
                print("ROUTE CHECK:", "PASS" if record["route_pass"] else "FAIL")

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
                        citation_present and cited.issubset(available)
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
                    print("CITATIONS MATCH RETRIEVED SOURCES:", citations_grounded)
                    print(
                        "RAG CHECK:",
                        "PASS" if rag_pass else "FAIL",
                    )

            except Exception as exc:
                record.update({
                    "error": f"{type(exc).__name__}: {exc}",
                    "answer_pass": False,
                })
                print("ERROR:", type(exc).__name__, str(exc))

            records.append(record)

    finally:
        bot.conn.close()

    sql_records = [
        r for r, c in zip(records, CASES) if c["route"] == "sql"
    ]
    rag_records = [
        r for r, c in zip(records, CASES) if c["route"] == "docs"
    ]

    summary = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "questions": len(records),
        "routing_accuracy": (
            sum(r.get("route_pass", False) for r in records)
            / len(records)
            if records else 0
        ),
        "sql_answer_pass_rate": (
            sum(r.get("answer_pass", False) for r in sql_records)
            / len(sql_records)
            if sql_records else 0
        ),
        "rag_retrieval_and_citation_pass_rate": (
            sum(r.get("answer_pass", False) for r in rag_records)
            / len(rag_records)
            if rag_records else 0
        ),
        "checker_sanity_tests": checker_results,
        "results": records,
    }

    output_path = RESULTS / "answer_eval_latest.json"
    output_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n" + "=" * 72)
    print("EVALUATION SUMMARY")
    print("Routing accuracy:",
          f"{summary['routing_accuracy']:.1%}")
    print("SQL answer pass rate:",
          f"{summary['sql_answer_pass_rate']:.1%}")
    print("RAG retrieval/citation pass rate:",
          f"{summary['rag_retrieval_and_citation_pass_rate']:.1%}")
    print("Results saved to:", output_path)


if __name__ == "__main__":
    main()
