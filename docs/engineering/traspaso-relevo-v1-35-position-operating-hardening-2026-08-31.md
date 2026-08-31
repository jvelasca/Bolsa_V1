# RELEVO — V1.35 Position Operating Hardening (2026-08-31)

> **Padre:** [`plan-v135-position-operating-hardening-2026-08-31.md`](./plan-v135-position-operating-hardening-2026-08-31.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** **CÓDIGO** — post-auditorías externas v1.34.1-beta; sin tag nuevo aún.  
> **Certified product tip:** `v1.34.1-beta` → `4b2e3751`.

---

## 0. Qué cierra V1.35

Endurecimiento operativo acordado tras auditorías externas (no rediseño).

| Pieza                                                    | Estado                                  |
| -------------------------------------------------------- | --------------------------------------- |
| Prefill `signedStop` TTL 30s + invalidación contextual   | CÓDIGO + vitest                         |
| `sourcesShouldContract` A6 alert-only (reversión manual) | CÓDIGO + pytest + Consola/Asesor        |
| `PositionDecision.protection` vs `nextEvent`             | CÓDIGO py + shared                      |
| `confidence` / `urgency` / `evidenceStrength` semánticos | CÓDIGO py + shared                      |
| Journey tests J01–J06                                    | CÓDIGO + `pnpm test:operative-journeys` |
| Contrato B-γ worsening-stop backend                      | `test_chart_drag_protect_contract.py`   |
| `OperatingPolicyV1` esqueleto                            | shared + py                             |

**Decisión A6:** `sourcesShouldContract=true` → alerta veto visual; **no** revierte fuentes AUTO automáticamente.

**Decisión B-γ:** `allowPendingOverride` en frontend **no** relaja backend; empeorar stop sin motivo auditado → DENY.

## 1. Pre-flight

```bash
pnpm test:operative-journeys
pnpm test:decision-spine
pnpm test:daily-ops:offline
pnpm --filter @bolsa/web exec tsc --noEmit
python -m pytest packages/py/application/tests/test_chart_drag_protect_contract.py -q
```

## 2. Freeze

Backend operativo **congelado** para V1.36 UI. Fuera: entry drag · OCO · nav L1 · thaw · AUTO execute.

## 3. Next

**V1.36 — Daily Operating UI:** layout Mercado cockpit (próximo evento / protección / frase humana). Ver roadmap.
