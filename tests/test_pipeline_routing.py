import pytest
import pipeline


@pytest.mark.parametrize(
    ("model_output", "expected_route"),
    [
        ("SQL", "sql"),
        ("DOCS", "docs"),
        ("BOTH", "both"),
    ],
)
def test_router_supports_three_routes(
    monkeypatch,
    model_output,
    expected_route,
):
    monkeypatch.setattr(
        pipeline,
        "ask_llm",
        lambda prompt: model_output,
    )

    bot = pipeline.FinSight.__new__(pipeline.FinSight)

    question = (
        "How did EBIT margin change, and what supply-chain risks "
        "could affect profitability?"
    )

    assert bot.route(question) == expected_route
