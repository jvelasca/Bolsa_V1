# ADR-038 — Position as operational memory

> **Status:** Accepted (post AUDITORIA 1) · **AsOf:** 2026-08-27

## Context

V1.16 entregó Mesa desk con proyecciones UI. AUDITORIA 1 identifica que la **posición** debe ser la memoria operativa central, no un cálculo disperso en filas UI.

## Decision

1. **Position = memoria operativa** — agregado reconstruible `InvestmentPositionAggregate` (shared puro).
2. Separación de artefactos:
   - `DecisionPackage` → por qué
   - `TradePlan` → qué pensábamos hacer
   - `Position` → qué tenemos
   - `ExitPlan` → cómo salir
   - `Ledger` → qué ocurrió económicamente
   - `Journal` → qué aprendimos
3. **Next Action** se deriva del agregado (`mapPositionNextAction`), no de lógica UI ad-hoc.
4. **Ruta viva** en posición: precio actual, distancias, R relativos, TP alcanzado.
5. **Estado operativo Mesa** = proyección de dimensiones (`SystemHealth`, `DataHealth`, `RiskState`, `ExecutionReadiness`, `MarketState`, `SessionState`).

## Consequences

- Implementación en [`packages/shared/src/cognitive/investment-position-aggregate.ts`](../../packages/shared/src/cognitive/investment-position-aggregate.ts).
- Mesa consume agregado; Libro y SEMI 2.0 podrán reutilizar el mismo builder.
- No se persiste un mega-documento; el agregado es proyección read-only.
- **V1.17.1:** `originalPlan` (fill: `plannedEntry`/`initialStop`) ≠ `currentPlan` (stop/targets actuales). El study actual **no** pisa el original. `thesisSnapshot.direction` es `long`|`short` (autoridad post-fill). Reconstrucción Position→DecisionPackage durable queda V1.18.
- **V1.18 L1 (proyección):** `originDecisionId` = `operational.tradePlanId`. `resolvePositionOriginLineage` / `pickPositionStudies` — origen **solo** por `decisionId`; soft-join instrumento = evolución (Next Action), **no** tesis de nacimiento. Orphan fail-closed (`missing_decision_id` | `session_not_found` | `package_missing` | `instrument_mismatch`); no inventa BUY.
- **V1.18 L2a:** al fill AI, congela `originDecisionPackage` write-once en `position_state` JSONB (lookup sesión por `decisionId`); `operational.originThesis` en HTTP; protect/exit preservan snapshot. Sin Alembic. Manual sin Package. B-read Mesa / backfill legacy parked.

## Non-goals

- No modificar Confirm/DEX/SubmitIntent.
- No AUTO ni HTTP nuevo Mesa.
- L1 no añade Alembic ni `decision_package_snapshot`.
- L2a no backfill posiciones nacidas antes del snapshot.
