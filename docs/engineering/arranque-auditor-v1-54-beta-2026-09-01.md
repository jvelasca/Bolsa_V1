# Arranque auditor externo — V1.52→V1.54 stack (Operating Desk) (2026-09-01)

Copia este bloque en un **chat nuevo** (auditor):

---

Eres auditor externo de Bolsa V1 **stack V1.52 Position Lifecycle → V1.53 Golden Session → V1.54 Operating Desk (UI + wire)**. Producto bajo revisión **`V1.54-beta`** tip funcional **`e057a8cc`** (wire `autoDesk` + `exceptionFacts`; UI en `bf115767`). Partida certificada **`v1.51-beta` → `5eb8e6de`** (auditoría externa **PASS 9,1**; V1.50 `96623755` PASS previo). El stack **no** abre LIVE ni cambia Confirm SEMI. `PAPER_D_EXECUTE` default **off**.

**Alcance:** V1.52 TargetLeg + revisiones + Lab execute **DENY** + GP-EXIT/CRASH · V1.53 pytest **GP-SESSION-01..04** (Estudio 09:00 → birth → protect → T1 → TRAIL×2 → exit → `PaperDailyReport`) · V1.54 proyección **autoDesk → Daily Desk inbox** (`EntryOpportunity` thin, cubo ⚠ excepciones, **GP-DESK-UI-01..09**). **No** segundo motor de ranking · **no** CTA COMPRAR desde filas AUTO.

**Contexto CI (2026-09-01):** tag `v1.54-beta` → `e057a8cc` → Release-tag CI **pending** (stamp/merge en curso; actualizar a **GREEN** cuando termine). Tips previos: `v1.52-beta` → `9725e9e7` (**GREEN**), `v1.53-beta` → `9725e9e7` (**GREEN**). Pre-flight local post close-out: shared + web vitest, pytest desk-block, ruff, tsc **OK**.

**GitHub (auditor):**

- Código tip: [`v1.54-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.54-beta) → commit `e057a8cc`
- Rama integración: [`stage/v151-entry-fill-position-2026-09-01`](https://github.com/jvelasca/Bolsa_V1/tree/stage/v151-entry-fill-position-2026-09-01)
- `main` debe contener el merge del stack + docs arranque (post-stamp)
- Partida certificada: [`v1.51-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.51-beta) → `5eb8e6de` (PASS 9,1)

Lee en este orden:

1. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)
2. [`docs/engineering/spec-v152-position-lifecycle-2026-09-01.md`](./spec-v152-position-lifecycle-2026-09-01.md)
3. [`docs/engineering/spec-v153-golden-session-2026-09-01.md`](./spec-v153-golden-session-2026-09-01.md)
4. [`docs/engineering/spec-v154-operating-desk-2026-09-01.md`](./spec-v154-operating-desk-2026-09-01.md)
5. [ADR-043](../adr/043-position-automation.md)
6. Tags relevo: [`traspaso-relevo-tag-v1-52-beta-2026-09-01.md`](./traspaso-relevo-tag-v1-52-beta-2026-09-01.md) · [`traspaso-relevo-tag-v1-53-beta-2026-09-01.md`](./traspaso-relevo-tag-v1-53-beta-2026-09-01.md) · [`traspaso-relevo-tag-v1-54-beta-2026-09-01.md`](./traspaso-relevo-tag-v1-54-beta-2026-09-01.md)

**Preguntas de foco:**

1. ¿V1.52 **Lab execute** con env on → **DENY** (sin bypass paper / sin segundo executor)?
2. ¿**TargetLeg** JSONB (`pending|triggered|executed|failed`) + enrich revision **decisionId/policyId** sin romper identidades V1.51 (`decisionId` TradePlan ≠ `candidateDecisionId` ≠ `fillId`)?
3. ¿**GP-SESSION-01..04**: sesión golden pytest reutiliza V1.48 tick + V1.51 birth + V1.52 legs; cierre `PaperDailyReport` coherente (`position_exited`, store `CLOSED`)?
4. ¿Wire backend `paper_daily_report`: **`autoDesk.candidates`** + **`exceptionFacts`** alineados con V1.50 `CandidateSnapshot` (sin recomputar ranking)?
5. ¿Compositor inbox (**`buildDailyDeskInbox` / overlay autoDesk**): sin `autoDesk` → inbox legacy intacto (**GP-DESK-UI-01**)?
6. ¿Filas **`EntryOpportunity` thin**: proyección read-only — **AUTO ≠ COMPRAR** (sin permiso, sin `rankingEngineId`, sin CTA BUY)?
7. ¿**GP-DESK-UI-02..03**: proposed → fila ⚡; skipped/denied → sin fila engañosa; notes honestos?
8. ¿**GP-DESK-UI-04..06**: cubo ⚠ — `position_birth_failed`, recon `drift|unavailable`, execution `UNKNOWN` (fail-closed OR-2/OR-4)?
9. ¿**GP-DESK-UI-07..09**: `mesa-hoy-page` → `daily-desk-inbox`; misma verdad shared ↔ web (vitest P1-P2)?
10. ¿V1.48 **PositionTick** / GP-DESK-03..08 / Confirm SEMI / package **`1.35.0-beta`** / freeze decision **intactos** tras UI?
11. ¿GP-EXIT/CRASH V1.52 + Golden Session V1.53 **sin regresión** tras wire V1.54?
12. ¿Sin LIVE · sin scheduler nuevo · `PAPER_D_EXECUTE` default off · sin bump package?

**Deuda aparcada:** LIVE · scheduler · browser E2E Journal · package bump · redesign Daily Desk · `PAPER_D_EXECUTE` default on.

**No pedir:** nav L1 · LIVE · bump package · segundo motor ranking · Alembic TargetLeg · thaw freeze Confirm.

---
