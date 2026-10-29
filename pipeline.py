"""FinSight: SQL, RAG, combined routing, and answer verification."""

import os
import re

from llm import ask_llm
from sql_tool import load_db, sql_answer
from rag import Retriever, rag_answer
from checker import unverified_numbers, unverified_citations


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
        """Classify a question as SQL, DOCS, or BOTH."""

        response = ask_llm(
            f"""Reply with exactly one word: SQL, DOCS, or BOTH.

SQL = the question needs numerical data from the financials table,
including revenue, profit, debt, margins, employees, comparisons,
or calculations.

DOCS = the question needs narrative information from annual reports,
including risks, strategy, outlook, explanations, or disclosures.

BOTH = the question needs both financial-table data and information
from annual-report passages.

Question: {question}"""
        )

        response_text = str(response).strip()
        normalized = response_text.upper().strip(
            " \t\r\n`'\".,:;"
        )

        # Prefer an exact classification response.
        if normalized in {"SQL", "DOCS", "BOTH"}:
            return normalized.lower()

        # Fallback in case the model returns additional text.
        if re.search(r"\bBOTH\b", response_text, re.IGNORECASE):
            return "both"

        if re.search(r"\bSQL\b", response_text, re.IGNORECASE):
            return "sql"

        if re.search(r"\bDOCS\b", response_text, re.IGNORECASE):
            return "docs"

        # Conservative default for narrative questions.
        return "docs"

    def _both_answer(self, question, mode="hybrid"):
        """Combine SQL results and annual-report evidence."""

        # Retrieve structured financial evidence.
        _, sql, sql_evidence = sql_answer(
            question,
            self.conn,
            self.schema,
            self.sample,
        )

        # Retrieve page-aware report passages.
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
            chunk = self.retriever.chunks[idx]

            # Include the citation in the generation prompt.
            document_context_parts.append(
                f"{citation}\n{chunk}"
            )

            # Keep the citation metadata separate from the evidence
            # used by the numerical checker.
            document_evidence_parts.append(chunk)
            document_sources.append(citation)

        if document_context_parts:
            document_context = "\n\n".join(
                document_context_parts
            )
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

        sql_result_text = str(sql_evidence or "").strip()

        if not sql_result_text:
            sql_result_text = "No SQL result rows were returned."

        prompt = f"""You are FinSight, a financial research assistant.

Answer the user's question using only the supplied SQL result and
annual-report passages.

Rules:
1. Use SQL results for numerical financial metrics and calculations.
2. Use annual-report passages for narrative disclosures, risks,
   strategy, explanations, and outlook.
3. Do not invent financial figures, facts, or citations.
4. Cite report-based claims using the exact filename and PDF page
   citation supplied with the relevant passage.
5. Do not create citations for pages that were not supplied.
6. If the evidence does not answer part of the question, state this
   limitation clearly.
7. Distinguish reported EBIT margin from underlying EBIT margin
   excluding discontinued operations. Do not treat these metrics
   as interchangeable.
8. Do not derive reported EBIT margin by dividing operating profit
   by revenue unless that calculation is explicitly requested and
   the definitions support it.
9. Explain financial comparisons and percentage-point changes
   accurately.

User question:
{question}

SQL query:
{sql or "No SQL query available."}

SQL result:
{sql_result_text}

Retrieved annual-report passages:
{document_context}

Write a direct, evidence-based answer. Use report-page citations
where appropriate and explain any limitations in the evidence.
"""

        answer = ask_llm(prompt)

        # This evidence is used for numerical verification. Citation
        # labels are intentionally excluded from the report text.
        evidence_parts = []

        if str(sql_evidence or "").strip():
            evidence_parts.append(
                f"SQL result:\n{sql_evidence}"
            )

        if document_evidence:
            evidence_parts.append(
                f"Annual-report evidence:\n{document_evidence}"
            )

        combined_evidence = "\n\n".join(evidence_parts)

        sources = ["financials table"] + sorted(
            set(document_sources)
        )

        return answer, sql, sources, combined_evidence

    def ask(self, question, mode="hybrid"):
        """Route the question and verify the generated answer."""

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
                mode,
            )

        else:
            answer, sources, evidence = rag_answer(
                question,
                self.retriever,
                mode,
            )
            sql = None

        # Check numerical claims before adding any warning text.
        bad = unverified_numbers(answer, evidence)

        # Verify that PDF citations in the answer match the
        # sources returned by the retrieval and SQL paths.
        citation_warnings = unverified_citations(
            answer,
            sources,
        )

        if bad:
            answer += (
                "\n\n[WARNING] Unverified numbers "
                "(not found in the evidence): "
                f"{bad}"
            )

        if citation_warnings:
            answer += (
                "\n\n[WARNING] Citation verification warning: "
                "These citations were not among the retrieved "
                "sources: "
                + "; ".join(citation_warnings)
            )

        return {
            "route": route,
            "answer": answer,
            "sql": sql,
            "sources": sources,
            "unverified": bad,
            "unverified_citations": citation_warnings,
            "evidence": evidence,
        }