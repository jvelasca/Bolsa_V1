# RELEVO — V1.50 Entry Decision Integrity (2026-09-01)

> **Padre:** [`spec-v150-entry-decision-integrity-2026-09-01.md`](./spec-v150-entry-decision-integrity-2026-09-01.md) · [ADR-043](../adr/043-position-automation.md) · [`plan-v150-entry-decision-integrity-2026-09-01.md`](./plan-v150-entry-decision-integrity-2026-09-01.md) · tip previo **`v1.49-beta` → `c8975c9d`**.  
> **Estado:** **CÓDIGO** — tip **`v1.50-beta` → `9e511715`** ([relevo tag](./traspaso-relevo-tag-v1-50-beta-2026-09-01.md)). Pre-flight local verde. Release-tag CI **pendiente push**. Product **`V1.50-beta`**. Package `1.35.0-beta` congelado. **No** LIVE.

---

## 0. Qué cierra

| Pieza                                                         | Estado  |
| ------------------------------------------------------------- | ------- |
| `CandidateSnapshot` en EntryTick (transporte `hits[]`)        | CÓDIGO  |
| `decisionId` + `reasonCode`/`humanMessage`                    | CÓDIGO  |
| `template_id` → OperatingPolicy + `policy_version` en propose | CÓDIGO  |
| Relojes analysis / market / execution                         | CÓDIGO  |
| Errores dominio vs infra (`unavailable`)                      | CÓDIGO  |
| GP-DESK-04 / 05 / 06                                          | CÓDIGO  |
| PositionTick / Event Continuity V1.48                         | intacto |
| EntryTick Estudio V1.49 (cableado)                            | intacto |

```text
Estudio → rank canónico → TradePlan TRIGGERED → Gate
  → CandidateSnapshot[] + counts (dry_run | execute)
PositionTick → Event Continuity (V1.48)
```

## 1. Pre-flight

Ver [`plan-v150-entry-decision-integrity-2026-09-01.md`](./plan-v150-entry-decision-integrity-2026-09-01.md).

## 2. Freeze (intactos)

Confirm = firma · `PAPER_D_EXECUTE` off · arm ≠ execute · no LIVE · Lab ≠ SoT · sin OCO · sin Alembic tabla nueva · sin bump package · sin nav L1 · sin scheduler · dry_run default true · BME/ES hardcode · **no** Fill→Position.

## 3. OUT / parked

- V1.51 Entry → Paper Fill → Position (snapshot viaja con la posición)
- V1.52 Golden Session completa
- UI Mesa EntryOpportunity
- Paper-D desk entry · scheduler · LIVE · package bump

## 4. Next

1. Tag `v1.50-beta` + Release-tag CI cuando el owner lo pida. **NO LIVE**.
2. **V1.51** Entry → Fill → Position.
