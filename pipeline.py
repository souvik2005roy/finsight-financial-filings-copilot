
"""FinSight router: SQL, RAG, and combined SQL + RAG answering."""

import os
import re

from llm import ask_llm
from sql_tool import load_db, sql_answer
from rag import Retriever, rag_answer
from checker import unverified_numbers


class FinSight:
    def __init__(self, csv=None, docs=None):
        csv = csv or os.getenv(
            "FINSIGHT_FINANCIALS_CSV",
            "data/financials_tata_motors_v2.csv",
        )
        docs = docs or os.getenv(
            "FINSIGHT_DOCS_DIR",
            "data/docs",
        )

        self.financials_path = csv
        self.docs_path = docs

        self.conn, self.schema, self.sample = load_db(csv)
        self.retriever = Retriever(docs)

    def route(self, question):
        """Route a question to SQL, documents, or both."""
        response = ask_llm(
            f"""Classify the question using exactly ONE word.

SQL = The question needs structured financial data, such as revenue,
profit, debt, employee counts, ratios, or numerical comparisons.

DOCS = The question needs narrative information from annual reports,
such as risks, strategy, outlook, explanations, or disclosures.

BOTH = The question requires BOTH a structured financial result
AND narrative evidence from annual reports.

Return exactly one of: SQL, DOCS, BOTH.

Question: {question}"""
        )

        response = (response or "").strip().upper()
        response = response.strip("`*. :\t\r\n")

        # Handle the intended one-word response first.
        if response in {"SQL", "DOCS", "BOTH"}:
            return response.lower()

        # Be tolerant of a model that returns an explanatory sentence.
        if re.search(r"\bBOTH\b", response):
            return "both"

        if re.search(r"\bSQL\b", response):
            return "sql"

        if re.search(r"\bDOCS\b", response):
            return "docs"

        # Conservative fallback when the classification is unclear.
        return "docs"

    def _both_answer(self, question, mode="hybrid"):
        """Combine SQL financial results with annual-report evidence."""

        # Run the existing SQL path to obtain a read-only query and result.
        _, sql, sql_evidence = sql_answer(
            question,
            self.conn,
            self.schema,
            self.sample,
        )

        # Retrieve report passages, preserving their PDF-page citations.
        indexes = self.retriever.search(
            question,
            k=4,
            mode=mode,
            diversify_pages=True,
        )

        document_context_parts = []
        document_evidence_parts = []
        document_sources = []

        for idx in indexes:
            citation = self.retriever.citation_for(idx)
            content = self.retriever.chunks[idx]

            document_context_parts.append(
                f"{citation}\n{content}"
            )
            document_evidence_parts.append(content)
            document_sources.append(citation)

        if document_context_parts:
            document_context = "\n\n".join(document_context_parts)
        else:
            document_context = (
                "No relevant annual-report passages were retrieved."
            )

        if document_evidence_parts:
            document_evidence = "\n\n".join(
                document_evidence_parts
            )
        else:
            document_evidence = ""

        # Use both evidence sources to generate one final answer.
        prompt = f"""Answer the user's question using BOTH evidence
sources below.

Rules:
- Use the SQL result for structured financial figures and calculations.
- Use annual-report passages for narrative claims and risk explanations.
- Cite each material report-based factual claim using the exact
  source label supplied with the passage.
- Never invent figures, years, report pages, or citations.
- Do not interchange reported EBIT margin, underlying EBIT margin,
  and operating profit divided by revenue.
- If either evidence source is insufficient, explain the limitation.
- Distinguish calculated changes from reported figures.
- Answer clearly and concisely.

Question:
{question}

SQL query:
{sql}

SQL result:
{sql_evidence or "No SQL result was returned."}

Annual-report passages:
{document_context}

Provide one integrated answer grounded in the supplied evidence.
"""

        answer = ask_llm(prompt)

        combined_evidence = (
            "SQL result:\n"
            + (sql_evidence or "")
            + "\n\nAnnual-report evidence:\n"
            + document_evidence
        )

        sources = ["financials table"] + sorted(
            set(document_sources)
        )

        return answer, sql, sources, combined_evidence

    def ask(self, question, mode="hybrid"):
        """Answer using SQL, RAG, or combined SQL + RAG."""
        route = self.route(question)

        if route == "sql":
            answer, sql, evidence = sql_answer(
                question,
                self.conn,
                self.schema,
                self.sample,
            )
            sources = ["financials table"]

        elif route == "both":
            answer, sql, sources, evidence = self._both_answer(
                question,
                mode=mode,
            )

        else:
            route = "docs"
            answer, sources, evidence = rag_answer(
                question,
                self.retriever,
                mode,
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
