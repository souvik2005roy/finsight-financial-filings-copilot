
"""FinSight: SQL, RAG, combined routing, and answer verification."""

import os
import re

from llm import ask_llm
from sql_tool import load_db, sql_answer
from rag import Retriever, rag_answer
from checker import unverified_numbers, unverified_citations


# ---------------------------------------------------------
# FOCUSED NARRATIVE RETRIEVAL
# ---------------------------------------------------------

def narrative_retrieval_query(question):
    """
    Extract narrative clauses from a mixed SQL + RAG question.

    This prevents financial terminology from diluting retrieval
    of relevant annual-report passages.
    """

    question = str(question).strip()

    if not question:
        return question

    # Split the question into logical clauses.
    clauses = re.split(
        r"\b(?:as well as|and|also|while|whereas|plus)\b",
        question,
        flags=re.IGNORECASE,
    )

    narrative_pattern = re.compile(
        r"\b("
        r"supply|supplier|logistics|risk|risks|"
        r"climate|raw.material|semiconductor|component|"
        r"water scarcity|strategy|outlook|operations|"
        r"disruption|shortage|shortages"
        r")\b",
        re.IGNORECASE,
    )

    # Retain clauses that contain narrative/report-related terms.
    narrative_clauses = [
        clause.strip(" ,;:.?")
        for clause in clauses
        if narrative_pattern.search(clause)
    ]

    # If no narrative clause is detected, preserve the original query.
    if not narrative_clauses:
        return question

    focused_query = " ".join(narrative_clauses)

    # Expand supply-chain queries using terminology found in
    # the annual-report risk disclosures.
    supply_chain_pattern = re.compile(
        r"\b("
        r"supply|supplier|logistics|raw.material|"
        r"semiconductor|component|climate|water scarcity"
        r")\b",
        re.IGNORECASE,
    )

    if supply_chain_pattern.search(focused_query):
        focused_query += (
            " supplier disruptions "
            "logistics interruptions "
            "component shortages "
            "semiconductor supply "
            "raw-material scarcity "
            "climate change "
            "vulnerable suppliers "
            "water scarcity "
            "production delays "
            "cost increases"
        )

    return focused_query


# ---------------------------------------------------------
# FINSIGHT APPLICATION
# ---------------------------------------------------------

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

    # -----------------------------------------------------
    # QUESTION ROUTER
    # -----------------------------------------------------

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

        # Fallback when the model returns additional text.
        if re.search(r"\bBOTH\b", response_text, re.IGNORECASE):
            return "both"

        if re.search(r"\bSQL\b", response_text, re.IGNORECASE):
            return "sql"

        if re.search(r"\bDOCS\b", response_text, re.IGNORECASE):
            return "docs"

        # Conservative default for narrative questions.
        return "docs"

    # -----------------------------------------------------
    # COMBINED SQL + RAG ANSWER
    # -----------------------------------------------------

    def _both_answer(self, question, mode="hybrid"):
        """
        Combine structured SQL results with annual-report evidence.

        SQL uses the original question.
        RAG uses a focused narrative retrieval query.
        """

        # 1. Retrieve structured financial evidence.
        _, sql, sql_evidence = sql_answer(
            question,
            self.conn,
            self.schema,
            self.sample,
        )

        # 2. Create a focused query for narrative retrieval.
        retrieval_question = narrative_retrieval_query(question)

        # 3. Retrieve page-aware annual-report passages.
        indexes = self.retriever.search(
            retrieval_question,
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

            # Include citations in the generation prompt.
            document_context_parts.append(
                f"{citation}\n{chunk}"
            )

            # Keep citation metadata separate from numerical evidence.
            document_evidence_parts.append(chunk)

            document_sources.append(citation)

        # 4. Prepare retrieved report context.
        if document_context_parts:

            document_context = "\n\n".join(
                document_context_parts
            )

        else:

            document_context = (
                "No relevant annual-report passages were retrieved."
            )

        document_evidence = "\n\n".join(
            document_evidence_parts
        )

        # 5. Prepare SQL result.
        sql_result_text = str(sql_evidence or "").strip()

        if not sql_result_text:

            sql_result_text = (
                "No SQL result rows were returned."
            )

        # 6. Generate the combined answer.
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

        # 7. Combine evidence for numerical verification.
        # Citation labels are intentionally excluded from
        # report evidence to avoid treating page numbers as values.
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

        # 8. Collect source references.
        sources = ["financials table"] + sorted(
            set(document_sources)
        )

        return answer, sql, sources, combined_evidence

    # -----------------------------------------------------
    # MAIN QUESTION-ANSWERING FUNCTION
    # -----------------------------------------------------

    def ask(self, question, mode="hybrid"):
        """Route the question and verify the generated answer."""

        route = self.route(question)

        # SQL-only route.
        if route == "sql":

            answer, sql, evidence = sql_answer(
                question,
                self.conn,
                self.schema,
                self.sample,
            )

            sources = ["financials table"]

        # Combined SQL + RAG route.
        elif route == "both":

            answer, sql, sources, evidence = self._both_answer(
                question,
                mode,
            )

        # RAG-only route.
        else:

            answer, sources, evidence = rag_answer(
                question,
                self.retriever,
                mode,
            )

            sql = None

        # -------------------------------------------------
        # NUMERICAL VERIFICATION
        # -------------------------------------------------

        bad = unverified_numbers(
            answer,
            evidence,
        )

        # -------------------------------------------------
        # CITATION VERIFICATION
        # -------------------------------------------------

        citation_warnings = unverified_citations(
            answer,
            sources,
        )

        # -------------------------------------------------
        # WARNING MESSAGES
        # -------------------------------------------------

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

        # -------------------------------------------------
        # RETURN RESULT
        # -------------------------------------------------

        return {
            "route": route,
            "answer": answer,
            "sql": sql,
            "sources": sources,
            "unverified": bad,
            "unverified_citations": citation_warnings,
            "evidence": evidence,
        }
