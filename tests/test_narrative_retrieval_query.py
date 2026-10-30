from pipeline import narrative_retrieval_query


def test_mixed_question_extracts_narrative_clause():
    question = (
        "How did Tata Motors' reported EBIT margin change "
        "from FY2023 to FY2025, and what supply-chain risks "
        "could affect its future financial performance?"
    )

    query = narrative_retrieval_query(question)

    assert "supply-chain risks" in query
    assert "EBIT margin" not in query
    assert "semiconductor supply" in query
    assert "raw-material scarcity" in query
    assert "water scarcity" in query


def test_standalone_narrative_question_is_retained():
    question = (
        "What climate-related risks affect Tata Motors?"
    )

    query = narrative_retrieval_query(question)

    assert "climate-related risks" in query
    assert "climate change" in query


def test_question_without_narrative_clause_falls_back():
    question = "Compare revenue in FY2023 and FY2025."

    assert narrative_retrieval_query(question) == question
