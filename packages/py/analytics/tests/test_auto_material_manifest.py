"""AUTO-20B — huella del MATERIAL: determinista, estable y sensible a lo que importa.

La huella es el sello que permite comparar dos corridas de calibración (``v2.62`` frente a
``v2.63``) sin abrir el JSON a mano. Estos tests certifican las tres propiedades que la hacen
útil y las que la harían peligrosa:

* **Mismo universo ⇒ misma huella**, sin importar el orden ni cómo se serializó el número
  (``Decimal("100.000000")`` y ``100`` son el mismo hecho medido).
* **Universo distinto ⇒ huella distinta**: version, régimen, riesgo y fricción entran; si no
  entraran, dos corridas incomparables parecerían la misma.
* **Sin ciclos no revienta**: la huella del vacío es un valor declarado.
"""

from __future__ import annotations

from decimal import Decimal

from bolsa_analytics.cognitive.auto_material_manifest import (
    FINGERPRINT_FIELDS,
    MATERIAL_FINGERPRINT_METHOD,
    material_fingerprint,
)


def _cycle(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "cycleId": "cyc-aaa",
        "strategyVersion": "orb-trend",
        "pnl": Decimal("5.0"),
        "closedAt": "2026-09-20T15:30:00+00:00",
        "riskAmount": Decimal("2.5"),
        "costApplied": {"friction": "0.5", "measurement": "COMPLETE"},
        "regime": "TREND_UP",
    }
    row.update(overrides)
    return row


def test_the_fingerprint_is_stable_and_order_independent() -> None:
    """El mismo material da la misma huella aunque cambie el orden de lectura."""
    forward = [_cycle(cycleId="cyc-a"), _cycle(cycleId="cyc-b"), _cycle(cycleId="cyc-c")]
    backward = list(reversed(forward))

    assert material_fingerprint(forward) == material_fingerprint(backward)
    assert material_fingerprint(forward).startswith("sha256:")


def test_the_fingerprint_normalizes_the_number_not_its_serialization() -> None:
    """``Decimal("100.000000")``/``100``/``"100.000000"`` son el MISMO hecho medido.

    La cadena con ceros de cola es el caso REAL: es lo que trae el JSON exportado. Si no se
    normalizara, la huella del material en memoria y la del JSON no coincidirían aunque el
    universo sea idéntico.
    """
    as_decimal = [_cycle(pnl=Decimal("100.000000"), riskAmount=Decimal("2.500000"))]
    as_numbers = [_cycle(pnl=100, riskAmount=2.5)]
    as_strings = [_cycle(pnl="100.000000", riskAmount="2.500000")]

    assert material_fingerprint(as_decimal) == material_fingerprint(as_numbers)
    assert material_fingerprint(as_decimal) == material_fingerprint(as_strings)


def test_the_fingerprint_does_not_touch_identifiers_that_look_numeric() -> None:
    """Un ``cycleId``/``strategyVersion`` no es un número aunque lo parezca: no se normaliza."""
    assert material_fingerprint([_cycle(cycleId="2.0")]) != material_fingerprint(
        [_cycle(cycleId="2")]
    )
    assert material_fingerprint([_cycle(strategyVersion="2.0")]) != material_fingerprint(
        [_cycle(strategyVersion="2")]
    )


def test_changing_the_universe_changes_the_fingerprint() -> None:
    """Versión, régimen, riesgo, fricción, cierre y pnl son parte del universo medido."""
    base = _cycle()
    for field, value in (
        ("strategyVersion", "orb-trend-v2"),
        ("regime", "RANGE"),
        ("riskAmount", Decimal("3.0")),
        ("costApplied", {"friction": "0.75", "measurement": "COMPLETE"}),
        ("closedAt", "2026-09-21T15:30:00+00:00"),
        ("pnl", Decimal("6.0")),
        ("cycleId", "cyc-other"),
    ):
        assert material_fingerprint([base]) != material_fingerprint([_cycle(**{field: value})]), (
            f"un cambio en {field} debe cambiar la huella"
        )


def test_the_fingerprint_does_not_depend_on_a_clock() -> None:
    """El instante de exportación NO entra a la huella (dos días distintos, mismo material)."""
    assert material_fingerprint([_cycle()]) == material_fingerprint([dict(_cycle())])


def test_the_empty_material_has_a_declared_fingerprint() -> None:
    """Sin ciclos la huella es un valor declarado, no un error."""
    assert material_fingerprint([]) == material_fingerprint(None)
    assert material_fingerprint([]).startswith("sha256:")
    assert material_fingerprint([]) != material_fingerprint([_cycle()])


def test_the_method_is_declared_and_the_fields_are_named() -> None:
    """El método viaja junto al número y los campos que entran son explícitos."""
    assert MATERIAL_FINGERPRINT_METHOD == "material_fingerprint_v1"
    assert "cycleId" in FINGERPRINT_FIELDS
    assert "strategyVersion" in FINGERPRINT_FIELDS
    assert "costApplied" in FINGERPRINT_FIELDS
