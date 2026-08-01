"""F1+ — golden JSON offline + live Ollama opcional."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from bolsa_ai.adapters.ollama_adapter import OllamaAdapter
from bolsa_ai.proxy import AIGovernanceProxy
from bolsa_ai.schemas import validate_indicator_hint, validate_strategy_hint

GOLDEN_DIR = Path(__file__).parent / "golden"


def _load_golden(name: str) -> dict[str, Any]:
    return json.loads((GOLDEN_DIR / name).read_text(encoding="utf-8"))


def test_golden_strategy_hint_schema() -> None:
    payload = _load_golden("strategy_hint_sma_cross.json")
    assert validate_strategy_hint(payload) == []
    assert payload["presetKey"] == "sma_cross"


def test_golden_indicator_hint_schema() -> None:
    payload = _load_golden("indicator_hint_rsi.json")
    assert validate_indicator_hint(payload) == []
    assert payload["definitionId"] == "rsi"
    assert payload["period"] == 14


def test_strategy_hint_rejects_bad_timeframe() -> None:
    errors = validate_strategy_hint({"presetKey": "x", "timeframe": "1y"})
    assert any("timeframe" in e for e in errors)


class _FakeOllama:
    provider = "ollama"

    def is_available(self) -> bool:
        return True

    def complete_json(self, **kwargs: Any) -> dict[str, Any]:
        return _load_golden("strategy_hint_sma_cross.json")


def test_proxy_success_with_fake_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOLSA_LLM_PROVIDER", "ollama")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    proxy = AIGovernanceProxy(ollama=_FakeOllama())  # type: ignore[arg-type]
    result = proxy.complete_structured(
        prompt_template_id="prompt_strategy_authoring_v1",
        variables={"user_input": "cruce SMA"},
    )
    assert result is not None
    assert result.provider == "ollama"
    assert result.payload["presetKey"] == "sma_cross"
    assert proxy.audit_log[-1].status == "success"
    assert validate_strategy_hint(result.payload) == []


@pytest.mark.ollama
def test_ollama_live_strategy_authoring(monkeypatch: pytest.MonkeyPatch) -> None:
    """Requiere Ollama en OLLAMA_BASE_URL y modelo descargado."""
    monkeypatch.setenv("BOLSA_LLM_PROVIDER", "ollama")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    adapter = OllamaAdapter()
    if not adapter.is_available():
        pytest.skip("Ollama no disponible")

    proxy = AIGovernanceProxy(ollama=adapter)
    result = proxy.complete_structured(
        prompt_template_id="prompt_strategy_authoring_v1",
        variables={"user_input": "estrategia cruce de medias SMA corto plazo"},
        allow_cloud=False,
    )
    if result is None:
        pytest.skip("Ollama respondió vacío o modelo ausente")
    assert result.provider == "ollama"
    # Soft check: al menos un campo útil del hint
    assert isinstance(result.payload, dict)
    assert result.payload
