"""Offline FinSight checks: no Gemini/API calls are made."""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
from checker import unverified_numbers
from rag import Retriever
from sql_tool import load_db

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
FINANCIALS = DATA / "financials_tata_motors_v2.csv"
SOURCES = DATA / "financial_sources.csv"
DOCS = DATA / "docs"

# Manually labelled target pages from the current two-report pilot.
RETRIEVAL_CASES = [
    {
        "name": "Broad supply-chain risks",
        "question": (
            "What supply-chain risks does Tata Motors discuss, including "
            "supplier and logistics disruptions, raw-material shortages, "
            "and climate-related risks?"
        ),
        "gold": {
            ("tata_motors_fy2025.pdf", 75),
            ("tata_motors_fy2025.pdf", 194),
            ("tata_motors_fy2025.pdf", 195),
            ("tata_motors_fy2023.pdf", 243),
        },
    },
    {
        "name": "Climate and raw materials",
        "question": (
            "How could climate change cause shortages of essential "
            "automotive raw materials and affect vulnerable suppliers?"
        ),
        "gold": {("tata_motors_fy2025.pdf", 194)},
    },
    {
        "name": "Revenue and underlying EBIT margin",
        "question": (
            "Compare Tata Motors consolidated revenue from operations "
            "and underlying EBIT margin in FY2025 and FY2024."
        ),
        "gold": {("tata_motors_fy2025.pdf", 154)},
    },
    {
        "name": "Supplier disruption consequences",
        "question": (
            "How can supplier and logistics disruptions affect production "
            "costs, lead times, revenue, and profitability?"
        ),
        "gold": {("tata_motors_fy2025.pdf", 75)},
    },
]


def check_financial_data() -> bool:
    print("\n=== FINANCIAL CSV / SOURCE REGISTER ===")
    if not FINANCIALS.exists() or not SOURCES.exists():
        print(f"Missing required file: {FINANCIALS if not FINANCIALS.exists() else SOURCES}")
        return False

    financials = pd.read_csv(FINANCIALS)
    sources = pd.read_csv(SOURCES)
    errors: list[str] = []

    if financials.duplicated(["company", "fiscal_year"]).any():
        errors.append("Duplicate company/fiscal_year rows.")

    source_keys = ["company", "fiscal_year", "metric_key"]
    if sources.duplicated(source_keys).any():
        errors.append("Duplicate source-register keys.")

    checked = 0
    indexed = financials.set_index(["company", "fiscal_year"])
    for row in sources.to_dict("records"):
        key = (row["company"], row["fiscal_year"])
        metric = row["metric_key"]
        if key not in indexed.index:
            errors.append(f"Financial row missing for {key}.")
            continue
        if metric not in indexed.columns:
            errors.append(f"Metric column missing: {metric}.")
            continue
        value = indexed.loc[key, metric]
        if pd.isna(value) or not math.isclose(
            float(value), float(row["value"]), rel_tol=0, abs_tol=0.01
        ):
            errors.append(
                f"Value mismatch {key} / {metric}: data={value}, source={row['value']}"
            )
        else:
            checked += 1

    print(f"Financial rows: {len(financials)}")
    print(f"Source records: {len(sources)}")
    print(f"Values matched: {checked}/{len(sources)}")
    print(f"Duplicate company/year rows: {int(financials.duplicated(['company','fiscal_year']).sum())}")
    print(f"Duplicate source keys: {int(sources.duplicated(source_keys).sum())}")

    if errors:
        for error in errors:
            print("FAIL:", error)
        return False
    print("PASS: CSV and source register are internally consistent.")
    print("NOTE: consistency does not independently prove transcription accuracy.")
    return True


def check_sql_results() -> bool:
    print("\n=== SQLITE FINANCIAL QUERY CHECKS ===")
    conn, schema, _sample = load_db(str(FINANCIALS))
    passed = True
    try:
        print("Schema:", schema)
        rows = conn.execute(
            "SELECT fiscal_year, revenue_cr, ebit_margin_pct "
            "FROM financials ORDER BY fiscal_year"
        ).fetchall()
        print("Rows:", rows)
        expected = [
            (2023, 345966.97, 3.6),
            (2024, 434016.0, 8.0),
            (2025, 439695.0, 7.9),
        ]
        if len(rows) != 3:
            passed = False
        else:
            for actual, wanted in zip(rows, expected):
                if actual[0] != wanted[0] or not math.isclose(actual[1], wanted[1], abs_tol=0.01) or not math.isclose(actual[2], wanted[2], abs_tol=0.01):
                    passed = False

        # Reported EBIT-margin percentage-point change, not an operating-profit ratio.
        change = conn.execute(
            "SELECT MAX(CASE WHEN fiscal_year=2025 THEN ebit_margin_pct END) - "
            "MAX(CASE WHEN fiscal_year=2023 THEN ebit_margin_pct END) "
            "FROM financials WHERE company='Tata Motors'"
        ).fetchone()[0]
        print("Reported EBIT margin change FY2023→FY2025 (percentage points):", change)
        if change is None or not math.isclose(float(change), 4.3, abs_tol=0.01):
            passed = False
    finally:
        conn.close()

    print("SQL checks:", "PASS" if passed else "FAIL")
    return passed


def check_retrieval() -> bool:
    print("\n=== RETRIEVAL RECALL@4 (OFFLINE) ===")
    if not DOCS.exists():
        print("Document directory missing:", DOCS)
        return False

    retriever = Retriever(str(DOCS))
    print("Indexed chunks:", len(retriever.chunks))

    methods = [
        ("BM25", "bm25", False),
        ("Vector", "vector", False),
        ("Hybrid", "hybrid", False),
        ("Hybrid-diverse", "hybrid", True),
    ]
    values: dict[str, list[float]] = {label: [] for label, _, _ in methods}

    for case in RETRIEVAL_CASES:
        print(f"\n{case['name']}")
        for label, mode, diverse in methods:
            hits = retriever.search(
                case["question"], k=4, mode=mode, diversify_pages=diverse
            )
            retrieved = {
                (retriever.sources[i], retriever.pages[i]) for i in hits
            }
            relevant = retrieved.intersection(case["gold"])
            recall = len(relevant) / len(case["gold"])
            values[label].append(recall)
            pages = ", ".join(
                f"{source}:p{page}" for source, page in sorted(retrieved)
            )
            print(f"  {label:16} recall={recall:.2f} ({len(relevant)}/{len(case['gold'])}) | {pages}")

    print("\nAverage recall@4 (manual labels; not answer accuracy):")
    for label, _, _ in methods:
        average = sum(values[label]) / len(values[label])
        print(f"  {label:16} {average:.3f}")
    return True


def check_number_checker() -> bool:
    print("\n=== NUMBER CHECKER ===")
    meta_answer = "Supply disruptions during FY2024–25 [tata_motors_fy2025.pdf, PDF page 75]."
    meta_evidence = "Supplier disruptions can increase lead times."
    meta_ok = unverified_numbers(meta_answer, meta_evidence) == []

    invented = unverified_numbers(
        "Raw-material costs increased by 18.5%.",
        "Raw-material supply constraints remain a concern.",
    )
    invented_ok = 18.5 in invented
    print("Citation/year metadata ignored:", "PASS" if meta_ok else "FAIL")
    print("Unsupported percentage detected:", "PASS" if invented_ok else "FAIL")
    return meta_ok and invented_ok


def main() -> int:
    checks = {
        "financial data consistency": check_financial_data(),
        "SQLite values and calculation": check_sql_results(),
        "retrieval benchmark ran": check_retrieval(),
        "number checker sanity": check_number_checker(),
    }
    print("\n=== LOCAL SUMMARY ===")
    for name, ok in checks.items():
        print(f"{name}: {'PASS' if ok else 'FAIL'}")
    print("Live Gemini calls made: 0")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
