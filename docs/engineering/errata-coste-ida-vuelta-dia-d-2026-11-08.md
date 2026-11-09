# ERRATA · Coste realizado del DÍA-D: el umbral se comparaba en unidades distintas

**Fecha:** 2026-11-08
**Afecta a:** [`dia-d-evidencia-monetaria-2026-11-05.md`](./dia-d-evidencia-monetaria-2026-11-05.md) §1 y §2.
**Tipo:** error de unidades en el evaluador. **No cambia el veredicto global.**

## Qué pasaba

`realized_cost_bps()` mide `|price/reference_mid − 1| × 10000` sobre cada fill: eso es coste
**por lado**. `AccountEvidencePolicy.min_round_trip_cost_bps` (22 bps) exige coste de **ida y
vuelta**. El evaluador comparaba 12,71 bps (por lado) contra 22 bps (ida+vuelta), exigiendo de
facto el doble de fricción de la que la política pide.

## Qué se corrige

- `dia_d_equity_evidence.py` separa `realizedCostBpsPerSide` de `realizedCostRoundTripBps`.
- La conversión declara su base (`realizedCostBasis`):
  - `price_friction_only_commission_not_declared`: `2 × per_side`, y se publica una advertencia
    de que es un **suelo**.
  - `price_friction_plus_commission_per_side`: `2 × per_side + 2 × commission_bps`.
  - `price_friction_and_commission_in_price`: `2 × per_side` (la comisión ya viaja en el precio).
- `evaluate_evidence_policy()` recibe `realized_cost_round_trip_bps`, la misma unidad que el umbral.
- `v2_93_dia_d_multi.py` declara la comisión del `TradingCostModel` del replay (10 bps por lado
  por defecto) y `commission_in_price=False`, porque el libro carga la comisión aparte
  (`TradingCostModel.commission_for`/`calculate_trade_fees`).

## Efecto sobre el artefacto de 2026-11-05

Con 12,71 bps por lado y 10 bps de comisión por lado, el ida+vuelta es
`2 × 12,71 + 2 × 10 = 45,42 bps`, por encima de los 22 bps exigidos: **`minRoundTripCostBps`
pasaría a PASS**. El veredicto global sigue **`REFUTED`** porque incumplen
`minPositiveWindowPct`, `minNetReturnPct`, `maxDrawdownPct` y `minExcessVsBuyHoldPct`.

No se reescribe el informe histórico: se deja como se emitió y esta errata fija la lectura
correcta. El artefacto JSON se regenera con el comando de la §0 del informe; el nuevo campo
`equityEvidence.realizedCostRoundTripBps` es el que debe citarse en adelante.

## Verificación

`packages/py/application/tests/test_dia_d_equity_evidence.py` cubre:

- 12,71 bps por lado ⇒ 25,42 ida+vuelta (sin comisión declarada).
- 10 bps de fricción + 10 bps de comisión por lado ⇒ 40 bps ida+vuelta.
- `commission_in_price=True` no vuelve a sumar la comisión.
- Sin `reference_mid` el coste sigue `None` (nunca 0).
