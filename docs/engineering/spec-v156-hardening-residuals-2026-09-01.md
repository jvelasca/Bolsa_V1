# Spec — V1.56 Hardening Residuals

> **AsOf:** 2026-09-01 · **Estado:** **CERRADO** (tag **`v1.56-beta`** · [relevo](./traspaso-relevo-tag-v1-56-beta-2026-09-01.md)).  
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · [ADR-043](../adr/043-position-automation.md) · [`spec-v155-operational-hardening-2026-09-01.md`](./spec-v155-operational-hardening-2026-09-01.md) · tip certificado previo **`v1.55-beta` → `c23091d9`**. **No** LIVE.

Cierra observaciones menores de auditoría V1.55 y deuda aparcada §4: endurecer GP-SESSION-07, pytest RESOLVED en GP-SESSION-10, smoke browser Journal/Consola. **No** motores nuevos · **no** LIVE · **no** reabrir stack V1.55 salvo los slices abajo.

```text
P0  GP-SESSION-07e + GP-SESSION-10r
P1  GP-E2E-01..02 Playwright smoke Journal + Consola
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` off · no LIVE · sin Alembic · sin bump package (`1.35.0-beta`) · sin scheduler · V1.54/V1.55 intactos salvo asserts/tests/E2E mínimo.

Regla global: `Ranking ≠ Signal ≠ Proposal ≠ Authorization ≠ Order ≠ Fill`.

## 1. IN — P0 Golden Session residuals

| ID             | Comportamiento                                                                                                         |
| -------------- | ---------------------------------------------------------------------------------------------------------------------- |
| GP-SESSION-07e | Tras T1 parcial → T2 → posición **CLOSED** qty=0 · `target2Leg.status == executed` (no admitir `triggered` alone)      |
| GP-SESSION-10r | Drift → `exceptionFacts` → humano `resolve_incident` (nota) → `resolved`; `clear` solo si recon `clean`; sin auto-heal |

GP-SESSION-07e corrige observación auditor B. Si el ciclo cierra vía exit agregado y deja `triggered`, el camino de fill T2 debe promover a `executed` — no bajar el assert.

GP-SESSION-10r extiende GP-SESSION-10 (facts fail-closed ya certificado) con transición DEX-3 humana ya existente en `operational_incident.py` / `operational_incident_store.py`.

## 2. IN — P1 Browser E2E smoke

| ID        | Comportamiento                                                                                        |
| --------- | ----------------------------------------------------------------------------------------------------- |
| GP-E2E-01 | Playwright: `/decision-journal` carga · `data-testid="decision-journal"` · solo lectura · sin COMPRAR |
| GP-E2E-02 | Playwright: `/operational-console` excepciones-only · no inbox Mesa duplicado · enlace a Libro        |

Playwright = dev dep + script `pnpm --filter @bolsa/web e2e`. **No** job nuevo en Release-tag CI en esta rebanada (opt-in local).

Auth: reutilizar overlay JWT dev / seed existente; no flujo Confirm live.

## 3. OUT / parked

LIVE · scheduler · bump package · `PAPER_D_EXECUTE` default on · Alembic tabla nueva · segundo motor ranking · redesign Daily Desk · thaw Accept estricto · auditoría adversarial post-V1.56 · CI Playwright obligatorio en tag.

## 4. Pre-flight

Bloque V1.55 + tests nuevos GP-SESSION-07e/10r + `pnpm --filter @bolsa/web e2e` (si stack up) + ruff + tsc.
