

import os
import streamlit as st

from pipeline import FinSight


# ---------------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------------

st.set_page_config(
    page_title="FinSight | Financial Copilot",
    page_icon="📊",
    layout="wide",
)

st.title("📊 FinSight")
st.subheader("Financial Filings Q&A Copilot")

st.caption(
    "Ask questions about Tata Motors financials and annual reports. "
    "Answers are generated using SQL, retrieval-augmented generation, "
    "or a combination of both."
)


# ---------------------------------------------------------
# LOAD FINSIGHT
# ---------------------------------------------------------

@st.cache_resource(show_spinner="Loading FinSight and report index...")
def load_finsight():
    """Load the financial database and report retriever once."""
    return FinSight()


# ---------------------------------------------------------
# ANSWER DISPLAY
# ---------------------------------------------------------

def answer_without_checker_warnings(answer):
    """
    Remove warning text appended by pipeline.py.

    Warnings are displayed separately using Streamlit components.
    This also cleans up older conversation messages.
    """

    if not isinstance(answer, str):
        return str(answer or "")

    markers = (
        "\n\n[WARNING] Unverified numbers (not found in the evidence):",
        "\n\n[WARNING] Citation verification warning:",
    )

    positions = [
        answer.find(marker)
        for marker in markers
        if answer.find(marker) >= 0
    ]

    if positions:
        return answer[:min(positions)].rstrip()

    return answer


# ---------------------------------------------------------
# METADATA AND VALIDATION WARNINGS
# ---------------------------------------------------------

def show_metadata(metadata):
    """Display route, sources, SQL, evidence, and checker warnings."""

    # Answer route.
    route = metadata.get("route")

    route_labels = {
        "sql": "SQL / Financial data",
        "docs": "RAG / Annual reports",
        "both": "SQL + RAG / Financial data + annual reports",
    }

    if route:
        st.caption(
            f"Answer route: {route_labels.get(route, route)}"
        )

    # Retrieved sources and citations.
    sources = metadata.get("sources") or []

    if sources:
        with st.expander("📚 Sources and citations"):
            for source in sources:
                st.write(f"- {source}")

    # Numerical verification warning.
    flagged_numbers = metadata.get("unverified") or []

    if flagged_numbers:
        st.warning(
            "Numerical verification warning: The checker flagged "
            "claims it could not match to the supplied evidence: "
            f"{flagged_numbers}"
        )

        st.caption(
            "Review these numerical claims against the original "
            "financial data or annual-report passages."
        )

    # Citation verification warning.
    flagged_citations = (
        metadata.get("unverified_citations") or []
    )

    if flagged_citations:
        st.warning(
            "Citation verification warning: These PDF-page citations "
            "were not among the retrieved sources: "
            + "; ".join(flagged_citations)
        )

        st.caption(
            "This check verifies citation matching only. It does not "
            "prove that a cited passage supports the associated claim."
        )

    # Generated SQL.
    sql = metadata.get("sql")

    if sql:
        with st.expander("🔎 Inspect generated SQL"):
            st.code(sql, language="sql")

    # SQL result or combined evidence.
    evidence = metadata.get("evidence")

    if evidence and route in ("sql", "both"):

        if route == "sql":
            title = "📊 View SQL result"
        else:
            title = "📚 View combined SQL + report evidence"

        with st.expander(title):
            st.code(evidence)


# ---------------------------------------------------------
# SESSION STATE
# ---------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []


# ---------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------

with st.sidebar:

    st.header("About FinSight")

    st.write("Current dataset: Tata Motors")
    st.write("Financial years: FY2023–FY2025")

    st.write(
        "Methods: Gemini, hybrid RAG, SQLite, text-to-SQL "
        "and answer verification"
    )

    st.info(
        "This is a single-company prototype. "
        "Numerical checks and citation matching are automated "
        "heuristics; verify important claims against the original reports."
    )

    if not os.getenv("LLM_API_KEY"):
        st.warning(
            "Set LLM_API_KEY in PowerShell before asking questions."
        )

    if st.button("Clear conversation"):
        st.session_state.messages = []
        st.rerun()


# ---------------------------------------------------------
# DISPLAY PREVIOUS CONVERSATION
# ---------------------------------------------------------

for message in st.session_state.messages:

    with st.chat_message(message["role"]):

        if message["role"] == "assistant":

            # Display the answer without appended checker warnings.
            st.markdown(
                answer_without_checker_warnings(
                    message["content"]
                )
            )

            # Re-display route, sources, SQL, and warnings.
            if message.get("metadata"):
                show_metadata(message["metadata"])

        else:
            st.markdown(message["content"])


# ---------------------------------------------------------
# CHAT INPUT
# ---------------------------------------------------------

question = st.chat_input(
    "Ask about revenue, EBIT margin, supply-chain risks..."
)


# ---------------------------------------------------------
# PROCESS NEW QUESTION
# ---------------------------------------------------------

if question:

    # Store and display user question.
    st.session_state.messages.append(
        {
            "role": "user",
            "content": question,
        }
    )

    with st.chat_message("user"):
        st.markdown(question)

    # Generate assistant response.
    with st.chat_message("assistant"):

        try:

            with st.spinner(
                "Analysing the question and retrieving evidence..."
            ):

                bot = load_finsight()
                result = bot.ask(question)

            # Original answer may contain warning text appended
            # by the verification functions in pipeline.py.
            answer = result.get(
                "answer",
                "No answer was returned.",
            )

            # Separate answer text from checker warnings.
            display_answer = answer_without_checker_warnings(
                answer
            )

            # Preserve all relevant metadata.
            metadata = {
                "route": result.get("route"),
                "sources": result.get("sources", []),
                "sql": result.get("sql"),
                "unverified": result.get("unverified", []),
                "unverified_citations": result.get(
                    "unverified_citations",
                    [],
                ),
                "evidence": result.get("evidence"),
            }

            # Display answer.
            st.markdown(display_answer)

            # Display route, sources, evidence, and warnings.
            show_metadata(metadata)

            # Save assistant response and metadata.
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": display_answer,
                    "metadata": metadata,
                }
            )

        except Exception as exc:

            st.error(
                f"FinSight could not complete this request: {exc}"
            )
