# Spec — V1.62 Entry Decision Surface

> **AsOf:** 2026-09-02 · **Estado:** **CERRADA** (pre-flight local 2026-09-02).  
> **Padre:** [`spec-v161-market-decision-surface-2026-09-02.md`](./spec-v161-market-decision-surface-2026-09-02.md) · tip certificado previo **V1.61** (partida `v1.60-beta`). **No** LIVE.

Simetría V1.61 para **entrada**: una **Entry Decision Surface** en Mercado DECISIÓN (pre-posición), usando `EntryOperatingTruth` como proyección canónica. **No** motores nuevos · **no** unificar LISTA→GRÁFICO.

```text
P0  GP-V162-01 — Entry Decision Surface en Mercado (fases entrada)
P0  GP-V162-02 — tono visual según fase (sky/ámbar/teal/rosa)
P0  GP-V162-03 — una superficie (sin Summary + Plan apilados)
P1  GP-V162-04 — Primary Action Honesty (ninguna → COMPRAR)
P1  GP-V162-05 — DECISIÓN vs EJECUCIÓN copy
P1  GP-V162-06 — cross-surface EntryOperatingTruth facts
```

## 0. Freeze

Igual V1.61: Confirm SEMI · `PAPER_D_EXECUTE` off · no LIVE · sin bump package.

## 1. IN

| ID         | Comportamiento                                                                                              |
| ---------- | ----------------------------------------------------------------------------------------------------------- |
| GP-V162-01 | `EntryDecisionSurface` muestra trigger · entry · stop · T1/T2 · riesgo · tamaño desde `EntryOperatingTruth` |
| GP-V162-02 | `data-tone` por fase: preparada→sky · disparada/propuesta→ámbar · confirmada→teal · bloqueada→rosa          |
| GP-V162-03 | Sin `entry-operating-summary` ni `OperationalPlanView` en ESTADO entrada Mercado                            |
| GP-V162-04 | preparada→Preparar · disparada→Revisar · confirmada→Ver operaciones · ninguna→COMPRAR                       |
| GP-V162-05 | DECISIÓN + EJECUCIÓN (ESPERAR TRIGGER/NO REQUERIDA · CONFIRM/PENDIENTE)                                     |
| GP-V162-06 | Misma fixture → mismo snapshot en builders cross-surface                                                    |

`EntryOperatingSummary` **sigue** en Hoy/Journal/opportunity drawer.

## 2. OUT

LISTA→GRÁFICO→ACCIÓN unificado · Browser E2E · DTO HTTP · LIVE.

## 3. Pre-flight

```bash
pnpm --filter @bolsa/shared exec vitest run src/cognitive/entry-operating-truth.test.ts src/cognitive/same-entry-operating-truth-across-surfaces.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/trading/operativa-cockpit-card.test.tsx src/features/trading/entry-decision-surface.test.ts
python -m pytest apps/api-python/tests/integration/test_v159_e2e_paper_desk.py apps/api-python/tests/integration/test_v159_e2e_operational_wire.py -m integration -q
python -m pytest packages/py/application/tests/test_paper_desk_golden_day_adversarial.py packages/py/application/tests/test_inv_operational_truth.py -q
pnpm --filter @bolsa/web exec tsc --noEmit
```
