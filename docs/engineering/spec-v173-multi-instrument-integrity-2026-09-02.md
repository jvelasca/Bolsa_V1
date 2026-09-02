# Spec — V1.73 Multi-instrument integrity

> **AsOf:** 2026-09-02 · **Estado:** **CERRADA** (código + E2E mock locales).  
> **Padre:** [`spec-v172-decision-explainability-top-2026-09-02.md`](./spec-v172-decision-explainability-top-2026-09-02.md) · partida **V1.72** (local post-`b70849bd`). **No** LIVE.

Certifica que el cambio de instrumento en Mercado **no contamina** identidad ni superficie operativa.

```text
P0  GP-V173-01 — A→B→C→A: chart + cockpit IDs/niveles rematch sin residual
P0  GP-V173-02 — Refresh integrity: tras reload, foco conserva identidad
P1  GP-V173-03 — Entry↔Position: superficie y data-position-id cambian al cambiar foco
P1  GP-V173-04 — Fixture multi-instrumento (3 buys PAPER) + helpers assert
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` off · no LIVE · sin scheduler · sin bump `1.35.0-beta` · sin tocar Decision Engine · V1.72 WHY intacto · `focusInstrumentInMercado` sigue UX-only.

## 1. IN

| ID         | Comportamiento                                                                                                                                  |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| GP-V173-01 | E2E integrado: 3 posiciones PAPER · click A→B→C→A · `data-instrument-id` / `data-position-id` / symbol / stop en chart+cockpit = fixture activa |
| GP-V173-02 | Tras foco en B · `page.reload()` + re-seed storage con chart B · cockpit/chart siguen en B (sin residual de A)                                  |
| GP-V173-03 | Mock o integrado: foco Entry (sin qty) → `entry-decision-surface` sin `data-position-id` · click posición → star card + `data-position-id`      |
| GP-V173-04 | `ensureMultiInstrumentMercadoFixture` · ≥3 instrumentos · mandatos + buys idempotentes · FAIL si faltan instrumentos                            |

### Invariantes (por foco)

```
activeChart.instrumentId
  == listRow.data-instrument-id
  == chart-indicators-zone.data-instrument-id
  == operativa-cockpit.data-instrument-id
  == operativa-cockpit.data-symbol (fixture)
```

Si hay posición abierta:

```
cockpit.data-position-id == fixture.positionId
(opcional) trade-plan-id / decision-id
stop/T1/T2 visibles y stop ≈ fixture.levels.currentStop
```

Si Entry (sin qty):

```
entry-decision-surface visible
cockpit sin data-position-id (o vacío)
phase ≠ posicion
```

## 2. OUT

- Paper Autonomous Day (**V1.74**)
- Stale → no execute E2E (**V1.75**)
- Chaos / split `integration.ts`
- LIVE · bump package · scheduler
- Rediseño Paper Desk / T2_READY CTA
- WHY rico (cerrado V1.72)
- Ideal/Máxima geométrica

## 3. Pre-flight

```bash
# Mock (siempre)
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v173

# Integrado (API :8000 + PG)
E2E_INTEGRATION=1 E2E_RUN=1 E2E_ALLOW_DEV_DB=1 pnpm --filter @bolsa/web e2e -- gp-v173

pnpm --filter @bolsa/web exec tsc --noEmit
```
