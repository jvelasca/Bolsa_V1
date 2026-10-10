# Gate F0 — viabilidad de identidad de estrategia y P&L realizado

> **AsOf:** 2026-10-10 · **Base:** `v2.88.104-beta` (commit `4cdaffc8`, HEAD `5c70e596`) · **Naturaleza:** medición read-only, sin cambio de código de producción.
> **Origen:** plan «Auditoría AUTO multi-fase». Desbloquea las fases `F3` (identidad de la estrategia ejecutada) y `F4`/`F5` (deuda PARKED FASE 2).

## 1. Pregunta 1 — ¿el ciclo conserva una identidad de estrategia enlazable?

**Hallazgo (verificado en código).** El read-model del ciclo expone **`strategyVersion`**, y ese valor es
`portfolio_reservations.strategy_version_id` (`packages/py/application/src/bolsa_application/auto_operational_monitor.py:862`).
Su origen es el `source` del `DecisionPackage`:

- `auto-2.0:<signal.strategy_version>` (pipeline V2, `packages/py/application/src/bolsa_application/auto_v2_entry.py:1417`).
- `active-strategy:<active.version_id>` (decider directo, `packages/py/application/src/bolsa_application/auto_orchestrator.py:765`).

En ambos casos, `<v>` es una **identidad de versión de estrategia** (`ActiveStrategy.version_id`, importe de la
promoción de un finalista del laboratorio; `packages/py/domain/src/bolsa_domain/entities/strategy_lifecycle.py:484`).

**La identidad que expone el ciclo NO es el `strategyDefinitionId` del slot #1 del TOP de Finalistas**
(ese es el UUID de definición de estrategia del laboratorio que consume `getInstrumentStrategyTop`).
`ActiveStrategy` porta `version_id`, `candidate_id`, `instrument_id`, `name` y `definition: dict` — no un
`strategyDefinitionId` de primera clase (`strategy_lifecycle.py:484-495`). El `definition` podría contener un
`id` interno, pero **no se publica** en el read-model del ciclo: el ciclo solo viaja `strategyVersion`.

**Consecuencia para `F3`.** El emparejamiento `strategyVersion ↔ TOP #1` que hoy hace
`resolveAutoOperationStrategyMatch` es, y seguirá siendo, **heurístico** (igualdad por token completo). Una
**igualdad exacta** exige motor: exponer la identidad de definición de la estrategia EJECUTADA
(`ActiveStrategy.definition`/`version_id` enlazado al ciclo) o el `templateId` del `trade_plan_snapshot`
(hoy presente en `enrich_opening_trade_plan_for_position`, `packages/py/application/src/bolsa_application/execution_router.py:94-140`, pero **no publicado** a la UI).

**Decisión `F3` (UI-only).** No se toca el motor. `F3` separa en la superficie lo que HOY se mezcla:
- «Mejor estrategia del valor (Finalistas TOP #1)» = lo disponible/mejor, con indicadores y razón.
- «Estrategia ejecutada declarada por el ciclo» = la identidad que el motor sí publica (`strategyVersion`).
La coincidencia exacta se declara **pendiente de materializar** (gap declarado, no fabricado). Esto respeta
`UNKNOWN ≠ 0` y no promete una trazabilidad que el read-model no puede sostener. Motorizar la igualdad
exacta queda como remediación declarada.

## 2. Pregunta 2 — ¿dónde vive el P&L realizado y cuánto cuesta publicarlo?

**Hallazgo (verificado en código).** El P&L realizado existe en dominio pero **no se publica** a la capa de
cuenta que consume AUTO:

- Dominio: `LifecycleAccounting.realized_pnl` (`packages/py/domain/src/bolsa_domain/lifecycle/__init__.py:254-260`,
  calculado en `account_lifecycle_fills`, `:938-967`).
- Resumen de cuenta consumido por AUTO: `PortfolioSummary` solo porta `total_unrealized_pnl`
  (`packages/py/domain/src/bolsa_domain/entities/portfolio.py:29-36`; mapeado en
  `packages/py/application/src/bolsa_application/accounts/summary.py:48`).
- UI: `buildAutoAccountFigures` pinta «Resultado de la cuenta» con `totalUnrealizedPnl`
  (`apps/web/src/features/auto/auto-account-figures.ts`).

**Consecuencia para `F4`.** Publicar el realizado agregado requiere **motor + contrato** (agregarlo por cuenta
desde el lifecycle/posiciones cerradas y añadirlo al read-model de resumen). **No requiere migración Alembic**
si se deriva de hechos ya persistidos; exige `contract:gen`/`contract:check`. La UI añade la cifra y declara
«Sin dato todavía» cuando falte.

## 3. Semáforo F0

| Pregunta | Veredicto | Fase | Naturaleza |
| --- | --- | --- | --- |
| Identidad de estrategia ejecutada | **Heurística** (no enlazable de forma exacta) | `F3` | **UI-only** (separar y declarar); igualdad exacta = remediación declarada |
| P&L realizado agregado | **Existe en dominio, no publicado** | `F4` | **Motor + contrato** (sin Alembic) |
| Motivo de ranking por ciclo | **`null` declarado** | `F5` | **Motor** |
| DÍA-D en vivo (no artefacto CLI) | **Artefacto read-only** | `F6` | **Motor/rutas** |

**Regla que no se rompe:** ninguna fase fabrica el hueco. `UNKNOWN ≠ 0`, `ranking ≠ decisión`,
`propuesta ≠ posición materializada` y la separación SIM/XTB se conservan.
