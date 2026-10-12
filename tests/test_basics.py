import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from checker import unverified_numbers, numbers_in
from sql_tool import is_safe, clean_sql
from evaluate import is_correct

def test_checker_accepts_supported_numbers():
    ev = "Revenue 1,190.0 crore in FY25; operating profit 221.0"
    assert unverified_numbers("Revenue was 1190 crore in FY25.", ev) == []

def test_checker_flags_invented_number():
    ev = "Revenue 412.5 crore in FY25"
    assert unverified_numbers("Revenue was 450.2 crore.", ev) == [450.2]

def test_checker_ignores_years_and_small_ints():
    assert unverified_numbers("Top 3 firms in 2025.", "nothing") == []

def test_numbers_parse_commas():
    assert numbers_in("INR 1,234.5 and 7") == [1234.5, 7.0]

def test_sql_guard():
    assert is_safe("SELECT * FROM financials;")
    assert not is_safe("DROP TABLE financials")
    assert not is_safe("SELECT 1; DELETE FROM financials")
    assert not is_safe("select * from financials where 1=1 union select 1 from (pragma x)")

def test_clean_sql_strips_fences():
    assert clean_sql("```sql\nSELECT 1\n```") == "SELECT 1"

def test_is_correct():
    assert is_correct("Revenue was 1,190 crore", ["1190.0"])
    assert is_correct("Risk: attrition among engineers", ["attrition"])
    assert not is_correct("Revenue was 900", ["1190.0"])
