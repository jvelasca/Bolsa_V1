# Spec — V1.74 Paper Autonomous Day

> **AsOf:** 2026-09-02 · **Estado:** **CERRADA** (código + E2E mock locales + pytest integration opt-in).  
> **Padre:** [`spec-v173-multi-instrument-integrity-2026-09-02.md`](./spec-v173-multi-instrument-integrity-2026-09-02.md) · partida **V1.73** (`4b0e80f5`). **No** LIVE.

Certifica la cadena diaria Paper Autonomous **visible y honesta** (dryRun / `PAPER_D_EXECUTE` off):

```text
Estudio → ranking → TradePlan → OpeningGate → AUTO PAPER (dryRun)
  → Fill (simulado/mock) → Position → Protect → T1 → Mercado identity
  → Reconciliation → Journal → Daily Report (autoDesk sections)
```

```text
P0  GP-V174-01 — Hoy inbox: T1 position + entry opportunity (autoDesk wire)
P0  GP-V174-02 — AUTO armado · ejecución off · sin COMPRAR
P1  GP-V174-03 — Journal deep-link ?view=journal
P1  GP-V174-04 — Hoy→Mercado: misma identidad positionId/instrumentId
P1  GP-V174-05 — recon ok — sin drift Cartera en inbox
P1  GP-V174-06..08 — pytest: multi-tick dryRun + sections + journal + recon
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` off · no LIVE · sin scheduler · sin bump `1.35.0-beta` · sin `dryRun=false` en browser E2E · V1.73 multi-instrument intacto.

## 1. IN

| ID         | Comportamiento                                                                                  |
| ---------- | ----------------------------------------------------------------------------------------------- |
| GP-V174-01 | Mock: `/mesa` carga inbox con T1 «Reducir» (AAPL) + oportunidad MSFT (autoDesk candidates)      |
| GP-V174-02 | Badge «AUTO armado · ejecución off» · 0 botones COMPRAR                                         |
| GP-V174-03 | `/mesa?view=journal` → `hoy-view-journal` visible                                               |
| GP-V174-04 | Tras Hoy, `/trading` conserva `data-position-id` / `data-instrument-id` del slice día           |
| GP-V174-05 | ops-self-eval mock `portfolioReconciliation.status=ok` · inbox sin frase drift Cartera          |
| GP-V174-06 | pytest: 2× POST `/paper-desk/cycle` dryRun → `autoDesk.sections` decisiones/operativa/resultado |
| GP-V174-07 | pytest: GET `/decision-journal` envelope válido tras ticks                                      |
| GP-V174-08 | pytest: GET `/risk/ops-self-eval` recon ≠ drift tras ticks                                      |

### Invariantes

```
autoDesk.dryRun === true
autoDesk.paperDExecute === false
ranking ≠ COMPRAR
AUTO armado ≠ execute ledger
```

## 2. OUT

- Chaos / stale→no-execute E2E (**V1.75**)
- `dryRun=false` browser execute · LIVE fills
- bump package · scheduler producción
- Rediseño Paper Desk UI

## 3. Pre-flight

```bash
# Mock (certificación cierre)
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v174

# pytest integration (PG opt-in)
pnpm --filter @bolsa/api-python test -- tests/integration/test_v174_paper_autonomous_day.py -m integration

pnpm --filter @bolsa/web exec tsc --noEmit
```
