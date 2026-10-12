from pathlib import Path
import pandas as pd
from pypdf import PdfReader
import math

DATA = Path("data")
FINANCIALS = DATA / "financials_tata_motors_v2.csv"
SOURCES = DATA / "financial_sources.csv"

METRICS = [
    "revenue_cr",
    "operating_profit_cr",
    "net_profit_cr",
    "ebit_margin_pct",
    "ebitda_margin_pct",
    "net_automotive_debt_cr",
    "underlying_ebit_margin_excl_discontinued_pct",
]

financials = pd.read_csv(FINANCIALS)
sources = pd.read_csv(SOURCES)

errors = []

# 1. Check unique company/year rows.
keys = ["company", "fiscal_year"]
if financials.duplicated(keys).any():
    errors.append("Duplicate company/year rows in financials CSV.")

# 2. Check source-register keys.
source_keys = keys + ["metric_key"]
if sources.duplicated(source_keys).any():
    errors.append("Duplicate company/year/metric source records.")

# 3. Build a lookup of financial values.
financial_lookup = financials.set_index(keys)

checked = 0

for row in sources.to_dict("records"):
    key = (row["company"], row["fiscal_year"])
    metric = row["metric_key"]
    value = row["value"]

    if key not in financial_lookup.index:
        errors.append(f"Missing financial row: {key}")
        continue

    if metric not in METRICS:
        errors.append(f"Unmapped metric: {metric}")
        continue

    actual = financial_lookup.loc[key, metric]

    if pd.isna(actual) or not math.isclose(
        float(actual), float(value), rel_tol=0, abs_tol=0.01
    ):
        errors.append(
            f"Value mismatch: {key}, {metric}; "
            f"financials={actual}, source_register={value}"
        )
    else:
        checked += 1

# 4. Check that cited reports and PDF pages exist.
page_counts = {}

for row in sources.to_dict("records"):
    filename = str(row["source_file"])
    pdf_path = DATA / "docs" / filename

    if not pdf_path.exists():
        errors.append(f"Source PDF missing: {pdf_path}")
        continue

    if filename not in page_counts:
        try:
            page_counts[filename] = len(PdfReader(str(pdf_path)).pages)
        except Exception as exc:
            errors.append(f"Cannot read {pdf_path}: {exc}")
            continue

    page = int(row["pdf_page"])
    if page < 1 or page > page_counts[filename]:
        errors.append(
            f"Invalid PDF page {page} in {filename}; "
            f"page count={page_counts[filename]}"
        )

print(f"Financial rows: {len(financials)}")
print(f"Source records: {len(sources)}")
print(f"Values matched: {checked}")
print(f"PDFs checked: {len(page_counts)}")

if errors:
    print(f"\nFAILED: {len(errors)} issue(s)")
    for error in errors:
        print("-", error)
    raise SystemExit(1)

print("\nPASSED: all automated consistency checks succeeded.")
