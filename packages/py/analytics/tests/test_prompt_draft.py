import pytest

from bolsa_analytics.research.prompt_draft import draft_strategy_from_prompt
from bolsa_analytics.research.strategy_definition_validator import validate_strategy_definition


def test_draft_sma_crossover_daily() -> None:

    result = draft_strategy_from_prompt("Quiero un cruce SMA en diario para tendencia")

    assert result.draft_kind == "classic"

    assert result.preset_key == "sma_crossover"

    assert result.timeframe == "1d"

    assert result.definition["origin"] == "assisted"

    assert result.definition["sourcePrompt"] == "Quiero un cruce SMA en diario para tendencia"

    assert result.confidence >= 0.5

    assert result.validated is True

    assert validate_strategy_definition(result.definition) == []





def test_draft_rsi_oversold_maps_to_bounce_preset() -> None:

    result = draft_strategy_from_prompt("RSI en sobreventa diario")

    assert result.preset_key in {"rsi_mean_reversion", "rsi_oversold_bounce"}

    assert result.timeframe == "1d"





def test_draft_hybrid_with_min_score() -> None:

    result = draft_strategy_from_prompt(

        "Rastreador híbrido: precio sobre SMA200 con rating mínimo 70"

    )

    assert result.draft_kind == "hybrid"

    assert result.definition["kind"] == "hybrid"

    assert result.min_score == 70.0

    assert result.gate_preset_key == "price_above_sma200"

    assert result.definition["hybrid"]["aiScorer"]["minScore"] == 70





def test_draft_golden_cross_weekly() -> None:

    result = draft_strategy_from_prompt("Golden cross semanal")

    assert result.preset_key == "golden_cross"

    assert result.timeframe == "1wk"





def test_draft_hybrid_with_fundamentals() -> None:
    result = draft_strategy_from_prompt(
        "Híbrido con PER máximo 20 y capitalización mínima 500M en tendencia SMA200 rating 65"
    )
    assert result.draft_kind == "hybrid"
    hybrid = result.definition.get("hybrid") or {}
    fundamental_gate = hybrid.get("fundamentalGate") or {}
    assert len(fundamental_gate.get("conditions") or []) >= 1
    preview = (result.feedback or {}).get("fundamentalPreview")
    assert preview and preview.get("enabled") is True
    assert len(preview.get("conditions") or []) >= 1


def test_draft_rejects_unknown_prompt() -> None:

    with pytest.raises(ValueError, match="No reconozco"):

        draft_strategy_from_prompt("comprar acciones baratas sin indicador")





def test_draft_rejects_short_prompt() -> None:

    with pytest.raises(ValueError, match="4 caracteres"):

        draft_strategy_from_prompt("rsi")


def test_draft_includes_feedback() -> None:
    result = draft_strategy_from_prompt(
        "Rastreador híbrido: precio sobre SMA200 con rating mínimo 70"
    )
    assert result.feedback is not None
    assert result.feedback.get("summary")
    assert len(result.feedback.get("detectedSignals") or []) >= 3
    assert len(result.feedback.get("scanSteps") or []) >= 2
    assert result.feedback.get("engineLabel")


def test_draft_daily_intent_beats_parenthetical_weekly() -> None:
    """«periodo DIARIO» + «pivote (Semanal)» no debe forzar 1wk."""
    result = draft_strategy_from_prompt(
        "Operativa diaria periodo DIARIO con Ichimoku y Punto pivote (Semanal) "
        "y Curso > Punto pivote (Mensual) y RSI"
    )
    assert result.timeframe == "1d"
    assert result.definition["timeframe"] == "1d"


def test_draft_parenthetical_weekly_alone_defaults_daily() -> None:
    """Solo etiquetas entre paréntesis no cambian el TF por defecto."""
    result = draft_strategy_from_prompt(
        "Cruce SMA con pivote (Semanal) y pivote (Mensual)"
    )
    assert result.timeframe == "1d"

