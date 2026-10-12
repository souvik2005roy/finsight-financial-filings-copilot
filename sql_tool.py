"""Text-to-SQL: question -> SQL -> SQLite -> result table."""
import re
import sqlite3
import pandas as pd
from llm import ask_llm

def load_db(csv_path="data/financials_tata_motors_v2.csv"):
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    df = pd.read_csv(csv_path)
    df.to_sql("financials", conn, index=False)
    schema = "financials(" + ", ".join(df.columns) + ")"
    sample = df.head(3).to_string(index=False)
    return conn, schema, sample

def is_safe(sql: str) -> bool:
    """Read-only guard: one SELECT statement, no write/DDL keywords."""
    s = sql.strip().rstrip(";")
    if not s.lower().startswith("select") or ";" in s:
        return False
    return not re.search(r"\b(insert|update|delete|drop|alter|attach|pragma|create|replace)\b", s, re.I)

def clean_sql(text: str) -> str:
    return re.sub(r"```(sql)?", "", text).strip()

def sql_answer(question, conn, schema, sample):
    """Returns (answer_text, sql, result_table_as_text)."""
    prompt = f"""Table: {schema}
Amounts are in INR crore. fiscal_year is an integer (2025 means FY25).
Sample rows:
{sample}

Write ONE SQLite SELECT query that answers the question.
If the question needs a ratio or percentage, compute it inside the SQL (round to 2 decimals).
Return only the SQL.
Question: {question}"""
    sql, error = clean_sql(ask_llm(prompt)), None
    for _ in range(2):                                   # one retry, feeding back the error
        if not is_safe(sql):
            return "I can only run read-only SELECT queries.", sql, ""
        try:
            table = pd.read_sql(sql, conn)
            break
        except Exception as e:
            error = str(e)
            sql = clean_sql(ask_llm(prompt + f"\nYour previous SQL failed: {error}\nFix it."))
    else:
        return f"SQL failed: {error}", sql, ""
    table_text = table.head(30).to_string(index=False)
    answer = ask_llm(f"""Question: {question}
SQL result:
{table_text}
Answer in one or two sentences using ONLY the numbers in the result.""")
    return answer, sql, table_text
