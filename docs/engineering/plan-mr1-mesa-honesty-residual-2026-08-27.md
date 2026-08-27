# Plan MR-1 — Honesty residual Mesa (2026-08-27)

> **Padre:** pack v1171 · relevo `v1.17.1-beta` · ADR-037/039.  
> **Estado:** implementación. **Freeze:** Confirm=firma · DEX intactos · `PAPER_D_EXECUTE` off · AUTO off · Ranking≠BUY · scenario≠permiso · BETA.  
> **No tocar:** lineage V1.18 · Stress · Opportunity · thaw · dry-run `check_opening`.

## Scope

1. **What-if** — copy + warning fijo: no evalúa `check_opening` / DS-05 / Fit de firma; `INSUFFICIENT_DATA` ámbar.
2. **Chip Datos** — sin verde por omisión; N>1 → label `muestra parcial (1/N)` (probe sigue en `positions[0]`); Régimen/Modo neutrales.
3. **Candidatos** — una Acción primaria (badge+CTA unificados); título sin «operables» (incluye WATCH/NO_OPERAR).

## DoD

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run portfolio-scenario mesa-next-action data-freshness operational-priority mesa-hoy-model
pnpm --filter @bolsa/web test -- mesa-hoy
```

Diff Confirm/DEX/SubmitIntent/persist_position/origin_decision_package = vacío.
