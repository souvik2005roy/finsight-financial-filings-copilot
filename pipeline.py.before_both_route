"""Router + SQL path + RAG path + number checker."""
import os

from llm import ask_llm
from sql_tool import load_db, sql_answer
from rag import Retriever, rag_answer
from checker import unverified_numbers


class FinSight:
    def __init__(self, csv=None, docs=None):
        csv = csv or os.getenv(
            "FINSIGHT_FINANCIALS_CSV",
            "data/financials_tata_motors_v2.csv"
        )
        docs = docs or os.getenv(
            "FINSIGHT_DOCS_DIR",
            "data/docs"
        )

        self.financials_path = csv
        self.docs_path = docs

        self.conn, self.schema, self.sample = load_db(csv)
        self.retriever = Retriever(docs)

    def route(self, question):
        r = ask_llm(f"""Reply with exactly one word.
SQL  = needs numbers from the financials table (revenue, profit, debt, employees, comparisons, totals).
DOCS = needs text from the annual reports (risks, strategy, outlook, explanations).
Question: {question}""")
        return "sql" if "SQL" in r.upper() else "docs"

    def ask(self, question, mode="hybrid"):
        route = self.route(question)

        if route == "sql":
            answer, sql, evidence = sql_answer(
                question, self.conn, self.schema, self.sample
            )
            sources = ["financials table"]
        else:
            answer, sources, evidence = rag_answer(
                question, self.retriever, mode
            )
            sql = None

        bad = unverified_numbers(answer, evidence)
        if bad:
            answer += (
                "\n\n[WARNING] Unverified numbers "
                f"(not found in the evidence): {bad}"
            )

        return {
            "route": route,
            "answer": answer,
            "sql": sql,
            "sources": sources,
            "unverified": bad,
            "evidence": evidence,
        }
