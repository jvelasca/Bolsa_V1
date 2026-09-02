"""V1.72 — DecisionExplainView Python goldens (espejo TS)."""

from bolsa_analytics.cognitive.decision_explain_view import (
    build_decision_explain_view,
)


def _study(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "symbol": "NVDA",
        "opinion": "bullish",
        "strength": 8.7,
        "action": "recommend_long",
        "entry": 421.5,
        "stop": 408.0,
        "target1": 448.0,
        "target2": 470.0,
        "expectedRR": 2.0,
        "riskAmount": 250.0,
        "trends": [
            {
                "key": "short_term",
                "label": "Corto plazo",
                "value": "up",
                "display": "Tendencia alcista CP",
            }
        ],
    }
    base.update(overrides)
    return base


def test_score_long_not_comprar_unknown_not_pass() -> None:
    view = build_decision_explain_view(_study())
    assert view["schemaVersion"] == "1.1.0"
    assert view["score"] == {"value": 8.7, "label": "8,7/10"}
    assert view["thesisDirection"] == {
        "action": "recommend_long",
        "label": "LONG",
    }
    assert "COMPRAR" not in (view["thesisDirection"]["label"] or "")
    assert "BUY" not in (view["thesisDirection"]["label"] or "")
    assert "no es autorización" in view["authorization"]["copy"]

    by_id = {f["id"]: f for f in view["factors"]}
    assert by_id["tendencia"]["state"] == "pass"
    assert by_id["momentum"]["state"] == "unknown"
    assert by_id["volumen"]["state"] == "unknown"
    assert by_id["regimen"]["state"] == "unknown"
    assert by_id["perfil"]["state"] == "unknown"
    unknowns = [f for f in view["factors"] if f["state"] == "unknown"]
    assert unknowns
    assert all(f["state"] != "pass" for f in unknowns)
    assert all(f["detail"] in ("sin dato", "neutro") for f in unknowns)

    assert view["entryGeometry"]["currentPrice"] is None
    assert view["entryGeometry"]["distanceAbs"] is None
    assert view["levels"]["stop"] == 408.0


def test_mark_distance_and_ta_components() -> None:
    view = build_decision_explain_view(
        _study(),
        mark_price=425.0,
        ta_components={"momentum": 0.4, "volume": 0.2},
        regime_hint="Régimen alcista",
    )
    assert view["entryGeometry"]["currentPrice"] == 425.0
    assert abs(view["entryGeometry"]["distanceAbs"] - 3.5) < 1e-9
    by_id = {f["id"]: f for f in view["factors"]}
    assert by_id["momentum"]["state"] == "pass"
    assert by_id["volumen"]["state"] == "pass"
    assert by_id["regimen"]["state"] == "pass"
    assert by_id["rr"]["state"] == "pass"
    assert by_id["riesgo"]["state"] == "pass"


def test_whynot_fail_closed_and_esperar_not_comprar() -> None:
    view = build_decision_explain_view(
        _study(action="wait"),
        why_not=["rr", "fit"],
        entries_blocked=True,
        action="wait",
    )
    assert view["thesisDirection"]["label"] == "ESPERAR"
    assert "COMPRAR" not in view["thesisDirection"]["label"]
    by_id = {f["id"]: f for f in view["factors"]}
    assert by_id["rr"]["state"] == "fail"
    assert by_id["perfil"]["state"] == "fail"
    assert by_id["riesgo"]["state"] == "fail"
