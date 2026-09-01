# Respuesta auditor — V1.49 Entry AUTO (2026-09-01)

> **Padre:** [`traspaso-relevo-tag-v1-49-beta-2026-09-01.md`](./traspaso-relevo-tag-v1-49-beta-2026-09-01.md) · [`spec-v149-paper-desk-entry-auto-2026-09-01.md`](./spec-v149-paper-desk-entry-auto-2026-09-01.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Tip auditado:** `v1.49-beta` → `c8975c9d`.  
> **Estado:** auditoría externa **recibida y contrastada con código**. Entry AUTO **no cerrado**. Siguiente sprint = [`spec-v150-entry-decision-integrity-2026-09-01.md`](./spec-v150-entry-decision-integrity-2026-09-01.md). **No** LIVE.

---

## 0. Acuerdo

V1.49 **sí** es un avance real: `EstudioPaperDeskEntry` sustituye el stub en el ciclo PAPER; el universo es la lista canónica `estudio`; se reutiliza `ProposeEstudioAutoOpenings` (ranking → TradePlan TRIGGERED → Router/`check_opening`). Empty ≠ unavailable. `PAPER_D_EXECUTE` off + `executionPolicyId` obligatorio en execute. GP-DESK-03 = **PASS de integración / cableado**, no de operativa completa.

Global 9,2–9,3/10 aceptado. Entry AUTO 8,2 y Entry→Position 7,5 marcan el cuello: **transportar la decisión completa**, no añadir inteligencia ni LIVE.

## 1. Contrastado (PASS)

| #     | Afirmación del auditor                             | Código                                                                     |
| ----- | -------------------------------------------------- | -------------------------------------------------------------------------- |
| 1     | Cadena Estudio → rank → TradePlan → Gate           | `paper_desk_entry.py` + `estudio_auto_hits.py`                             |
| 1     | Stub fuera del ciclo real                          | DI `EstudioPaperDeskEntry`; `HonestStubPaperDeskEntry` solo tests/fallback |
| 2     | empty ≠ unavailable                                | `resolve_estudio_universe`                                                 |
| 3     | dry_run=false + env off → `paper_auto_env_blocked` | `run_entry_tick`                                                           |
| 4     | execute sin policy → blocked                       | `execution_policy_required`                                                |
| 17–18 | No duplicar motor                                  | adapter, no segundo ranking/plan/gate                                      |

## 2. Contrastado (deuda / FAIL de integridad)

| #   | Hallazgo                          | Hecho en código                                                                                                    | Acción V1.50                                                                                            |
| --- | --------------------------------- | ------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| 5   | `max_candidates=25` ≠ max compras | cap de `select_estudio_opening_candidates`; `OperatingPolicy.sizing` ya tiene `max_open_positions` / concentración | documentar funnel ≠ execution limits; cablear perfil para que los límites apliquen **antes** de execute |
| 6   | `template_id` ignorado            | `_ = template_id` en EntryTick; PositionTick **sí** llama `resolve_operating_policy`                               | P0: perfil → policy en entry                                                                            |
| 7   | un solo as_of Daily               | `asOfBarDate = date.fromisoformat`; `signal.timestamp = now UTC`                                                   | clocks `analysisAsOf` / `marketAsOf` / `executionAsOf` (honestos, nullable)                             |
| 8–9 | snapshot pobre                    | **Propose ya devuelve `hits[]` con `tradePlan`**; el adapter los tira y deja contadores                            | `CandidateSnapshot` en `PaperDeskEntryTickResult`                                                       |
| 10  | GP-DESK-03 superficial            | `FakePropose` + `hitCount=2`                                                                                       | GP-DESK-04                                                                                              |
| 11  | falta top-N                       | ranking real = alarma > dictamen + stars (**no** score Composite 9.2)                                              | test sobre ranking **canónico**; no motor nuevo                                                         |
| 12  | falta Gate BLOCK                  | Router existe; no hay GP desk                                                                                      | GP-DESK-05: DENY → sin ExecutionIntent                                                                  |
| 13  | stop inválido ≠ BUY               | skip `no_tradeplan` si status ≠ TRIGGERED                                                                          | GP-DESK-06                                                                                              |
| 14  | `except ValueError`               | infra puede escapar                                                                                                | domain → blocked; infra → unavailable                                                                   |
| 15  | `notes` libres                    | `skipped.reason` ya existe en propose                                                                              | `reasonCode` + `humanMessage`                                                                           |

## 3. Ranking: no inventar score 9.2

El test pedido (A=9.2 … maxCandidates=2 → A,B) se implementa sobre el **orden canónico actual** (`estudio_alarma` antes que `estudio_dictamen`, luego `dictamenStars` desc). `CandidateSnapshot.score` es **proyección** de esa clave (p.ej. canal + estrellas), no un Composite paralelo ni ranking de UI.

## 4. Roadmap acordado

```text
V1.50  Entry Decision Integrity   (snapshot + IDs + profile + GPs 04–06)  ← ahora
V1.51  Entry → Fill → Position    (snapshot viaja con la posición)
V1.52  Golden Session completa    (09:00 Estudio → … → Journal)
luego  UI Mesa                    (EntryOpportunity, no hitCount)
```

Freeze intacto: Confirm = firma · `PAPER_D_EXECUTE` off · no LIVE · no scheduler · package `1.35.0-beta`.
