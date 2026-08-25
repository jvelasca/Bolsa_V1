"""Ciclo I2 — paridad con operativa-index.test.ts (computeIndiceOperativo)."""

from bolsa_analytics.knowledge.indice_operativo import compute_indice_operativo


def test_compute_indice_operativo_clamps_and_distress_floor():
    assert compute_indice_operativo(72) == 72
    assert compute_indice_operativo(80, distress=True) == 40
    assert compute_indice_operativo(None) is None
    assert compute_indice_operativo(float("nan")) is None
    assert compute_indice_operativo(120) == 100
    assert compute_indice_operativo(-5) == 0
    assert compute_indice_operativo(30, distress=True) == 30
