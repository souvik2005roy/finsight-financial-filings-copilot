
import os
import streamlit as st
from websockets import route
from pipeline import FinSight


st.set_page_config(
    page_title="FinSight | Financial Copilot",
    page_icon="📊",
    layout="wide",
)

st.title("📊 FinSight")
st.subheader("Financial Filings Q&A Copilot")
st.caption(
    "Ask questions about Tata Motors financials and annual reports. "
    "Answers are generated using SQL or retrieval-augmented generation."
)


@st.cache_resource(show_spinner="Loading FinSight and report index...")
def load_finsight():
    """Load the financial database and report retriever once."""
    return FinSight()


def show_metadata(metadata):
    """Display the route, sources, SQL, and checker warnings."""
    route = metadata.get("route")

    route_labels = {
        "sql": "SQL / Financial data",
        "docs": "RAG / Annual reports",
        "both": "SQL + RAG / Financial data + annual reports",
    }

    if route:
        st.caption(f"Answer route: {route_labels.get(route, route)}")

    sources = metadata.get("sources") or []
    if sources:
        with st.expander("📚 Sources and citations"):
            for source in sources:
                st.write(f"- {source}")

    sql = metadata.get("sql")
    if sql:
        with st.expander("🔎 Inspect generated SQL"):
            st.code(sql, language="sql")

    flagged = metadata.get("unverified")
    if flagged:
        st.warning(
            "The numerical checker flagged claims that it could not "
            f"match to the supplied evidence: {flagged}"
        )
    if metadata.get("route") == "sql" and metadata.get("evidence"):
        with st.expander("📊 View SQL result"):
            st.code(metadata["evidence"])


with st.sidebar:
    st.header("About FinSight")
    st.write("Current dataset: Tata Motors")
    st.write("Financial years: FY2023–FY2025")
    st.write("Methods: Gemini, hybrid RAG, SQLite and text-to-SQL")

    st.info(
        "This is a single-company prototype. "
        "Citations and numerical checks should be verified against the reports."
    )

    if not os.getenv("LLM_API_KEY"):
        st.warning("Set LLM_API_KEY in PowerShell before asking questions.")

    if st.button("Clear conversation"):
        st.session_state.messages = []
        st.rerun()


if "messages" not in st.session_state:
    st.session_state.messages = []


# Re-display previous messages.
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        if message["role"] == "assistant" and message.get("metadata"):
            show_metadata(message["metadata"])


question = st.chat_input(
    "Ask about revenue, EBIT margin, supply-chain risks..."
)

if question:
    st.session_state.messages.append(
        {"role": "user", "content": question}
    )

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        try:
            with st.spinner("Analysing the question and retrieving evidence..."):
                bot = load_finsight()
                result = bot.ask(question)

            answer = result.get("answer", "No answer was returned.")
            metadata = {
                "route": result.get("route"),
                "sources": result.get("sources", []),
                "sql": result.get("sql"),
                "unverified": result.get("unverified"),
                "evidence": result.get("evidence"),
            }

            st.markdown(answer)
            show_metadata(metadata)

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": answer,
                    "metadata": metadata,
                }
            )

        except Exception as exc:
            st.error(
                f"FinSight could not complete this request: {exc}"
            )
