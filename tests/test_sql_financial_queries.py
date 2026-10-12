from pathlib import Path

import pytest
from sql_tool import load_db

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data" / "financials_tata_motors_v2.csv"


@pytest.fixture
def conn():
    connection, _, _ = load_db(str(CSV))
    yield connection
    connection.close()


def test_revenue_by_year(conn):
    rows = conn.execute("""
        SELECT fiscal_year, revenue_cr
        FROM financials
        ORDER BY fiscal_year
    """).fetchall()

    assert [row[0] for row in rows] == [2023, 2024, 2025]
    assert [row[1] for row in rows] == pytest.approx(
        [345966.97, 434016, 439695]
    )


def test_reported_ebit_margin_change_in_percentage_points(conn):
    rows = conn.execute("""
        SELECT fiscal_year, ebit_margin_pct
        FROM financials
        WHERE fiscal_year IN (2023, 2025)
        ORDER BY fiscal_year
    """).fetchall()

    margins = {year: margin for year, margin in rows}

    change = margins[2025] - margins[2023]

    assert change == pytest.approx(4.3)


def test_underlying_ebit_margin_is_separate(conn):
    rows = conn.execute("""
        SELECT fiscal_year,
               ebit_margin_pct,
               underlying_ebit_margin_excl_discontinued_pct
        FROM financials
        ORDER BY fiscal_year
    """).fetchall()

    assert rows[0][2] is None
    assert rows[1][2] == pytest.approx(7.9)
    assert rows[2][2] == pytest.approx(7.9)


def test_net_automotive_cash_is_not_total_debt(conn):
    row = conn.execute("""
        SELECT total_debt_cr, net_automotive_debt_cr
        FROM financials
        WHERE fiscal_year = 2025
    """).fetchone()

    assert row[0] is None
    assert row[1] == pytest.approx(-1018)
