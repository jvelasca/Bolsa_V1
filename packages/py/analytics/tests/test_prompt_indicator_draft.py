from bolsa_analytics.research.prompt_indicator_draft import draft_indicator_from_prompt


def test_draft_rsi_from_prompt() -> None:
    result = draft_indicator_from_prompt("RSI 14 en panel inferior")
    assert result.definition_id == "rsi"
    assert result.preset["parameters"]["period"] == 14
    assert result.validated


def test_draft_rating_from_prompt() -> None:
    result = draft_indicator_from_prompt("rating técnico con componentes")
    assert result.definition_id == "technical_rating_v1"
    assert result.preset["parameters"]["showComponents"] is True


def test_draft_global_score_weights() -> None:
    result = draft_indicator_from_prompt("score global 80% setup 20% datos")
    assert result.definition_id == "ai_global_score_v1"
    assert result.preset["parameters"]["setupWeight"] == 80
    assert result.preset["parameters"]["dataWeight"] == 20


def test_llm_indicator_draft_matches_heuristic_without_key(monkeypatch) -> None:
    from bolsa_ai import reset_default_proxy
    from bolsa_analytics.research.llm_indicator_draft import draft_indicator_from_prompt_with_llm

    monkeypatch.setenv("BOLSA_LLM_PROVIDER", "none")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    reset_default_proxy()
    result = draft_indicator_from_prompt_with_llm("rating técnico")
    assert result.definition_id == "technical_rating_v1"
    assert result.engine == "indicator_prompt_catalog_v1"
