# Spec — V1.71 Identity & Certification

> **AsOf:** 2026-09-02 · **Estado:** **CERRADA** (código + tests locales; **sin stamp CI GREEN**).  
> **Padre:** [`spec-v170-lista-grafico-accion-2026-09-02.md`](./spec-v170-lista-grafico-accion-2026-09-02.md) · partida **V1.70** (`960383d2`). **No** LIVE.

Cierra las reservas de certificación de V1.70: identidad DOM lista↔gráfico↔cockpit, POV con recon OI-6 en el wire, copy Decision Surface sin colapsar severidad, E2E SKIP solo de entorno, y paridad golden POV TS/Python.

```text
P0  GP-V171-01 — GET /portfolio adjunta POV con recon_status OI-6; live drift overlay sobre wire
P0  GP-V171-02 — unknown/failed/drift → REVISAR; T2_EXECUTED y DRIFT no se fusionan a «Protegida»
P0  GP-V171-03 — E2E integrado: skip solo entorno; fixture/producto ausente = FAIL
P1  GP-V171-04 — data-instrument-id/position-id/trade-plan-id/decision-id; GP-V170 aserta identidad + niveles
P1  GP-V171-05 — focusInstrumentInMercado único (open-hit, Asesor, Estilos, lista multi/search)
P1  GP-V171-06 — Golden POV TS/Python: T2_EXECUTED, DRIFT, stopHistory 5 orígenes, origin inválido drop
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` off · no LIVE · sin bump package · V1.70 journey intacto.

**V1.70 certificación:** aprobada **con reservas**. El job Playwright integrado es opt-in (`run_e2e_integration` default false). **No** se declara CI GREEN para `960383d2`.

## 1. IN

| ID         | Comportamiento                                                                                       |
| ---------- | ---------------------------------------------------------------------------------------------------- |
| GP-V171-01 | `attach_operational_positions(..., recon_status=)` · overlay live en `use-position-operational-view` |
| GP-V171-02 | `entryExecutionStateLabel` / `povExecutionStateLabel` · `assertNever` en Decision Surface + F2 copy  |
| GP-V171-03 | `gateIntegratedE2eEnvironment` vs throw en GP-V167 / V168 / V170; buy seed no silencioso             |
| GP-V171-04 | Atributos data-\* en lista, HUD, chart zone, cockpit; GP-V170-01/03 asertan IDs + stop/T1/T2         |
| GP-V171-05 | `openHitInTrading`, Asesor símbolo, instrument-detail Estilos, list multi-select/search → resolver   |
| GP-V171-06 | Goldens TS + pytest: T2_EXECUTED+MONITOR, drift+BLOQUEADO, 5 labels, parse drop origin inválido      |

## 2. OUT

- WHY rico (V1.72)
- Paper Autonomous Day (V1.74)
- Chaos / split `integration.ts`
- LIVE · bump package · scheduler
- Rediseño Paper Desk: `T2_READY` sigue `MONITOR` (heurística APPLIED en desk `reduced`; ahora igual en TS y Python)

## 3. Verificación

Ver [`arranque-auditor-v1-71-identity-certification-2026-09-02.md`](./arranque-auditor-v1-71-identity-certification-2026-09-02.md).
