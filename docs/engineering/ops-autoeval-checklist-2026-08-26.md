# Checklist — OE-1 Autoevaluación operativa (SEMI + AUTO)

> **AsOf:** 2026-08-26  
> **Padre:** ADR-034 · plan [`plan-oe1-ops-autoeval-2026-08-26.md`](./plan-oe1-ops-autoeval-2026-08-26.md).  
> **Regla:** measure ≠ Accept estricto · ≠ flip `PAPER_D_EXECUTE` · rojo ≠ permiso thaw.

---

## Comando

```bash
node scripts/ops_operativa_self_eval.mjs
node scripts/ops_operativa_self_eval.mjs --json
node scripts/ops_operativa_self_eval.mjs --account=default-account-seed
```

API: `GET /api/risk/ops-self-eval?accountId=…&lookbackDays=120`  
UI: barra operativa «Autoeval SEMI · AUTO» (`/operations`, Trading).

Thaw P1–P5 solo: `node scripts/thaw_estricto_snapshot.mjs`.

---

## Carril SEMI / MANUAL

1. Cuenta activa `default-account-seed` (o DEMO canónica).
2. Libro SEMI (no MANUAL para encolar desriesgo).
3. Camino: TradePlan TRIGGERED → Proponer F3 → **Confirmar + ejecutar** (paper).
4. Opcional protect: CTA Proteger → Confirm (persist stop; PH-1 honesty).
5. Refs: [`checklist-semi-e2e-triggered-confirm-protect-2026-08-26.md`](./checklist-semi-e2e-triggered-confirm-protect-2026-08-26.md) · [`operar-semi-p4-consola-mesa-2026-08-25.md`](./operar-semi-p4-consola-mesa-2026-08-25.md).
6. Scorecard: `confirmSeed` / `journalSeed` / `buysSeed` — **no** contar `buys_testish`.

| Mark               | Significado                                  |
| ------------------ | -------------------------------------------- |
| PASS               | Path medible + al menos 1 confirm o buy seed |
| WARN               | Path OK pero 0 evidencia fills seed          |
| FAIL / UNAVAILABLE | Counts o API down                            |

---

## Carril AUTO / Camino D

1. Repo default: `PAPER_D_EXECUTE` **off**.
2. Opt-in local DEMO only: `PAPER_D_EXECUTE=1` + armado UI — **≠** Accept estricto.
3. Gates P1–P5: ver [`deuda-thaw-estricto-runbook-2026-08-25.md`](./deuda-thaw-estricto-runbook-2026-08-25.md).
4. Kill switch: bloquea aperturas/AUTO; desriesgo SEMI permitido.
5. `strictAcceptReady=true` solo si P1–P5 PASS + palabra **thaw** (DoD §4) — fuera de este checklist.

| Mark        | Significado                                  |
| ----------- | -------------------------------------------- |
| PASS        | P1–P5 verdes (raro hoy)                      |
| FAIL        | Algún Pn rojo (estado esperado pre-estricto) |
| WARN        | Solo MaxDD inválido / parcial                |
| UNAVAILABLE | Telemetría/API down                          |

---

## Honesty

- OI-6 en informe: `portfolioReconciliation.status=not_wired` hasta wire HTTP (detect/report; no heal).
- Preferencia cuenta `brokerVenue` ≠ override mesa global.
- Snapshot / Autoeval **no** autorizan execute ni Accept.
