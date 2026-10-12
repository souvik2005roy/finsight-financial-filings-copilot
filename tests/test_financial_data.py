from pathlib import Path

import pandas as pd
import pytest

from sql_tool import load_db

ROOT = Path(__file__).resolve().parents[1]
FINANCIALS = ROOT / "data" / "financials_tata_motors_v2.csv"
SOURCES = ROOT / "data" / "financial_sources.csv"


def test_pilot_contains_three_unique_financial_years():
    df = pd.read_csv(FINANCIALS)

    assert sorted(df["fiscal_year"].tolist()) == [2023, 2024, 2025]
    assert not df.duplicated(["company", "fiscal_year"]).any()


def test_sqlite_preserves_reported_margin_definitions():
    conn, _, _ = load_db(str(FINANCIALS))

    try:
        rows = conn.execute("""
            SELECT fiscal_year,
                   ebit_margin_pct,
                   underlying_ebit_margin_excl_discontinued_pct
            FROM financials
            ORDER BY fiscal_year
        """).fetchall()
    finally:
        conn.close()

    assert len(rows) == 3
    assert [row[0] for row in rows] == [2023, 2024, 2025]

    assert [row[1] for row in rows] == pytest.approx([3.6, 8.0, 7.9])
    assert pd.isna(rows[0][2])
    assert [row[2] for row in rows[1:]] == pytest.approx([7.9, 7.9])


def test_source_register_values_match_financials():
    df = pd.read_csv(FINANCIALS).set_index(
        ["company", "fiscal_year"]
    )
    sources = pd.read_csv(SOURCES)

    for record in sources.to_dict("records"):
        key = (record["company"], record["fiscal_year"])
        metric = record["metric_key"]

        assert key in df.index, f"Missing financial row: {key}"
        assert metric in df.columns, f"Missing metric column: {metric}"

        actual = df.loc[key, metric]
        expected = record["value"]

        assert pd.notna(actual)
        assert actual == pytest.approx(expected, abs=0.01), (
            f"Mismatch for {key}, {metric}: "
            f"financials={actual}, source register={expected}"
        )
