# Spec — V1.50 Entry Decision Integrity

> **AsOf:** 2026-09-01 · **Estado:** **CÓDIGO**.  
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · [ADR-043](../adr/043-position-automation.md) · [`spec-v149-paper-desk-entry-auto-2026-09-01.md`](./spec-v149-paper-desk-entry-auto-2026-09-01.md) · [`respuesta-auditor-v149-entry-auto-2026-09-01.md`](./respuesta-auditor-v149-entry-auto-2026-09-01.md).  
> **Plan:** [`plan-v150-entry-decision-integrity-2026-09-01.md`](./plan-v150-entry-decision-integrity-2026-09-01.md).  
> **Tip certificado previo:** `v1.49-beta` → `c8975c9d` (Release-tag CI GREEN; auditoría externa recibida). **No** LIVE.

Cierra la integridad de la **decisión de entrada** en el ciclo PAPER: el EntryTick deja de devolver solo contadores. Transporta el candidato completo (ranking + TradePlan + razones estructuradas + perfil) hasta el borde del Intent. **No** duplica ranking / TradePlan / OpeningGate. **No** cierra Fill→Position (V1.51).

```text
PaperDeskCycle
  → EntryTick: EstudioPaperDeskEntry (adapter, un solo motor)
      → ProposeEstudioAutoOpenings
          → select_estudio_opening_candidates (rank canónico)
          → ProposeRecommendationFromTa (TradePlan TRIGGERED)
          → dry_run | ExecutionRouter (check_opening)
      → PaperDeskEntryTickResult
          proposedCount + candidates[CandidateSnapshot]
          skipped[reasonCode, humanMessage]
          decisionId por propuesta
  → PositionTick (V1.48 intacto)
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` off · arm ≠ execute · no LIVE · Lab ≠ SoT · sin OCO · sin Alembic tabla nueva · sin bump package · sin nav L1 · sin scheduler · dry_run default true · BME/ES hardcode · **no** Paper-D desk entry · **no** Fill→Position (V1.51) · **no** Golden Session birth+exit · **no** motor de ranking nuevo.

## 1. IN

### 1.1 CandidateSnapshot (transporte, no persistencia)

`ProposeEstudioAutoOpenings` **ya** devuelve `hits[]` con `tradePlan`, precio y `autoSource`. V1.50 deja de tirarlos en `map_estudio_propose_to_entry_tick`.

Campos mínimos (camelCase en dict / HTTP):

| Campo                                                                  | Origen (no inventar)                                                                          |
| ---------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `decisionId`                                                           | identidad por propuesta (hit `signal.id` o uuid estable por instrumento+asOf+plan)            |
| `instrumentId` / `symbol`                                              | hit                                                                                           |
| `rank`                                                                 | índice 1..N tras `select_estudio_opening_candidates`                                          |
| `score`                                                                | proyección de la clave canónica (canal alarma/dictamen + `dictamenStars`); **≠** Composite UI |
| `autoSource`                                                           | `estudio_alarma` \| `estudio_dictamen`                                                        |
| `profileId` / `templateId`                                             | `template_id` del ciclo (ya no `_ = template_id`)                                             |
| `analysisAsOf`                                                         | `asOfBarDate` Daily                                                                           |
| `marketAsOf`                                                           | `OperationalContext` / snapshot si existe; si no, `null` + honesty                            |
| `executionAsOf`                                                        | solo en camino execute; dry_run → `null`                                                      |
| `tradePlan`                                                            | dict intacto (entry, stop, T1, T2, risk, qty, status, whyNot)                                 |
| `entry` / `stop` / `target1` / `target2` / `riskAmount` / `expectedRR` | eco desde TradePlan (Mesa)                                                                    |
| `mandate` / `freshness` / `vetoes`                                     | del gate si se evaluó; dry_run honestamente `not_evaluated`                                   |
| `reasonCode` / `humanMessage`                                          | si skipped o blocked                                                                          |

Persistir el snapshot en BD / Position = **V1.51**.

### 1.2 `max_candidates` ≠ max compras

`max_candidates` (default 25) = **tope del embudo** hacia TradePlan. No autoriza 25 fills.

Límites de ejecución (ya en `OperatingPolicy` + `check_opening`): `max_open_positions`, concentración, `max_sector_exposure`, kill, mandate, freshness, recon OR-4. V1.50 **cablea** `template_id` → `resolve_operating_policy` en el camino de entry para que Conservador ≠ Agresivo. No añade un segundo motor `MAX_NEW_POSITIONS` si el policy/gate ya lo cubre.

`MAX_DAILY_ENTRIES` como contador diario dedicado queda **parked** si no existe ya en policy.

### 1.3 Profile → policy

Eliminar `_ = template_id`. El ciclo pasa `template_id` al propose / sizing / gate (mismo SoT que PositionTick: `conservative` \| `moderate` \| `aggressive_swing`). Execute sigue exigiendo `executionPolicyId` (AUTO ≠ autorización).

### 1.4 Reason codes

`notes` humanas se conservan. Además, códigos estables para UI/auditoría (lista inicial, extensible):

`ENTRY_NO_TRIGGER` · `ENTRY_INVALID_STOP` · `ENTRY_RISK_LIMIT` · `ENTRY_STALE_DATA` · `ENTRY_MANDATE_BLOCK` · `ENTRY_POLICY_MISSING` · `ENTRY_MARKET_CLOSED` · `ENTRY_DUPLICATE` · `ENTRY_ENV_BLOCKED` · `ENTRY_UNIVERSE_EMPTY` · `ENTRY_UNIVERSE_UNAVAILABLE` · `ENTRY_INFRA_UNAVAILABLE`

Cada bloqueo: `reasonCode` + `humanMessage`. Mapear `skipped.reason` existente (`no_tradeplan`, `sin_precio`, `propose_error:…`) a este vocabulario; no perder el detalle.

### 1.5 Errores

| Clase                                                           | Resultado EntryTick                                                                                                 |
| --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| Dominio / negocio (policy, trigger, risk, stop)                 | `blocked` + reasonCode                                                                                              |
| Universo Estudio no determinable                                | `skipped` + `ENTRY_UNIVERSE_UNAVAILABLE` (ya V1.49)                                                                 |
| Infra (timeout, DB, conexión, excepción inesperada del propose) | `unavailable` (status nuevo o `skipped` + `ENTRY_INFRA_UNAVAILABLE`) — **no** disfrazar como «no hay oportunidades» |

No convertir todo en `blocked`.

### 1.6 Relojes

Tres instantes, nunca fusionados:

- `analysisAsOf` — barra Daily del dictamen / plan.
- `marketAsOf` — instante de mercado del contexto operativo (nullable + honesty).
- `executionAsOf` — instante del Intent/fill (nullable en dry_run).

## 2. OUT / parked

- Fill PAPER → Position con `trade_plan_snapshot` (**V1.51**).
- Golden Session 09:00 Estudio→…→Journal (**V1.52**).
- UI Mesa `EntryOpportunity` cards (después de V1.51).
- Paper-D desk entry · scheduler · LIVE · `PAPER_D_EXECUTE` default on · package bump.
- Ranking Composite / IO como score de AUTO.
- Segunda capa de ranking o OpeningGate dentro de PaperDesk.

## 3. Golden Paths

| ID             | Comportamiento                                                                                                                                                         |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GP-DESK-03     | Intacta (cableado dry_run propone hits)                                                                                                                                |
| GP-DESK-04     | Estudio A,B,C,D ordenados; `maxCandidates=2` → solo A,B en `candidates[]` con TradePlan (entry/stop/T1/T2/risk) intacto. Ranking canónico, no Composite 9.2 inventado. |
| GP-DESK-05     | Candidato TRIGGERED + `check_opening` DENY (p.ej. portfolio risk / concentración) → **BLOCK**, **sin** ExecutionIntent.                                                |
| GP-DESK-06     | Score/rank alto + stop inválido → skip/blocked `ENTRY_INVALID_STOP` / `ENTRY_NO_TRIGGER`. Nunca BUY. Ranking ≠ autorización.                                           |
| GP-DESK-01..02 | Intactos                                                                                                                                                               |

## 4. Pre-flight

Mismo bloque V1.49 + tests nuevos GP-DESK-04/05/06 en `test_paper_desk_entry.py` (y helpers de propose/ranking existentes, sin duplicar motor).
