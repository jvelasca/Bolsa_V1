# Respuesta auditor — V1.94 (Financial Integrity) (2026-09-03)

> **Padre:** auditoría tip `v1.94-beta` → [`363984d2`](https://github.com/jvelasca/Bolsa_V1/commit/363984d2) (GitHub, vs `v1.93-beta`).  
> **Spec V1.94:** [`spec-v194-financial-integrity-2026-09-03.md`](./spec-v194-financial-integrity-2026-09-03.md).  
> **Cierre:** V1.95 certificación — [`spec-v195-beta-certification-2026-09-03.md`](./spec-v195-beta-certification-2026-09-03.md).

## Veredicto (auditor)

**V1.94 ≠ BETA estable.** Arquitectura correcta (recon bidireccional, OR-4 en Confirm/Execute/Router/Fill, `/lifecycle/integrity`, `operationalState` ≠ SLA). **P0 = 0.** CI rojo + tres P1 fail-closed.

## Hallazgos aceptados

### P1

| ID    | Hallazgo                                              | Cierre V1.95                                                  |
| ----- | ----------------------------------------------------- | ------------------------------------------------------------- |
| P1-01 | Python Ruff + Frontend Typecheck RED (pytest skipped) | Ruff + `contract:gen` OpenAPI/`schema.d.ts`                   |
| P1-02 | `dead_non_head` + `status=clean`; gate no veta        | Nunca clean; compose `lag` → ops **DEGRADED**; DENY aperturas |
| P1-03 | `lag` ALLOW en opening gate                           | `lag` → `reconciliation:lifecycle_lag` DENY                   |
| P1-04 | Fill chain solo `POSITION_OPENED`                     | OPEN + T1 + T2 + EXIT vs ledger; gate usa **compose**         |

### AUDITORIA 2 (borde; aceptados en V1.95)

| ID   | Hallazgo                                                               | Cierre V1.95                                              |
| ---- | ---------------------------------------------------------------------- | --------------------------------------------------------- |
| P1-A | `assert report is not None` en GET integrity/reconciliation → 500      | JSON nombrado `blocked`/`BLOCKED`; lookup → `unavailable` |
| P1-B | `_outbox_sort_key` usa `datetime.min` naive → TypeError vs TIMESTAMPTZ | Fallback UTC aware + promote naive→UTC                    |

### P2 (registrados; no bloquean certificación pequeña)

P2-01 coste recon en opening path (deuda post-beta; no materializar). P2-02 doble `PositionState` — reuso desde lifecycle report. P2-03 Golden HTTP — `test_lifecycle_golden_v195.py`. P2-04 Consola: `operationalState` dominante vs SLA ok.

## Freeze verificado

NO LIVE · no bump `1.35.0-beta` · `PAPER_D_EXECUTE` off · no auto-heal · no unificar ledger · no `queue_sequence`.

## Next

**V1.95 — certificación / cierre de BETA.** No nueva arquitectura. Tag `v1.95-beta` solo con Release-tag CI GREEN.
