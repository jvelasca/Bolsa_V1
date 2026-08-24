# RELEVO / TRASPASO — OrderProposal + DecisionJournal · apertura Ciclo 1 (docs) → F1 código

> **Padre:** [ADR-029](../adr/029-order-proposal-decision-journal.md) · [plan-order-proposal-journal-2026-08-24.md](./plan-order-proposal-journal-2026-08-24.md).
> **Propósito:** handoff del subagente **docs-only Ciclo 1/5** al **subagente F1 implementación**.
> **AsOf:** 2026-08-24.

---

## 1. Estado verificado (firma — no adivinar)

| Campo                    | Valor                                                                                   |
| ------------------------ | --------------------------------------------------------------------------------------- |
| **HEAD**                 | `e3b943a9003074a4f5bdbf5790da6b651bffa691`                                              |
| **Tag**                  | `v1.7.0-beta` (exact match HEAD)                                                        |
| **Rama**                 | `main` == `origin/main`                                                                 |
| **Working tree**         | limpio (post docs Ciclo 1)                                                              |
| **Decisión propietario** | Abrir **5 ciclos en orden**; Ciclo 1 = OrderProposal/Journal — freeze levantado con ADR |

---

## 2. Qué se creó en Ciclo 1 (docs-only)

| Archivo                                                                          | Rol                                             |
| -------------------------------------------------------------------------------- | ----------------------------------------------- |
| `docs/adr/029-order-proposal-decision-journal.md`                                | Decisión: layering, alternativas, consecuencias |
| `docs/engineering/plan-order-proposal-journal-2026-08-24.md`                     | Fases F1–F3, NO TOUCH, call-sites, batería      |
| `docs/engineering/traspaso-relevo-order-proposal-journal-apertura-2026-08-24.md` | Este handoff                                    |

**Cero commits** · **cero push** · **cero código** (salvo estos 3 ficheros).

---

## 3. Decisiones de diseño clave (para no re-debatir en F1)

1. **OrderProposal = handle refs-only** — no duplica `RecommendationV1` (`recommendation.ts:16`) ni `OrderIntentV1` (`order-intent.ts:20`). Proyección desde `decision_sessions` `kind='propose'` (`decision-session.ts:24` · `tables.py:608`).

2. **DecisionJournal = tabla nueva append-only** — complementa, **no reemplaza**, `decision_sessions` (`decision-session.ts:3` · `tables.py:602`).

3. **Sin tabla `order_proposals` en F1** — adaptar sesión existente (mapping F0.3: reusar sessions).

4. **Fail-closed / paper-only / SEMI=AUTO risk** — heredar D1 (`CURRENT_SYSTEM.md:39`); journal observa, no relaja gates.

5. **H3 congelado** — orphan `contract=absent` sigue ejecutando (`confirm_recommendation.py:288`); journal solo audita.

6. **Hooks best-effort** — mismo patrón que persist sesión (`propose_recommendation.py:448` · `confirm_recommendation.py:406`).

---

## 4. Brief subagente F1 (implementación)

```
CONTEXTO (2026-08-24): repo Bolsa_V1, HEAD e3b943a, tag v1.7.0-beta, main==origin/main.
Ciclo 1/5 DOCS CERRADO. Tu misión: F1 DOMINIO + PERSISTENCIA (sin HTTP).

LEE PRIMERO:
- docs/adr/029-order-proposal-decision-journal.md
- docs/engineering/plan-order-proposal-journal-2026-08-24.md (§1 F1, §2 NO TOUCH, §3 call-sites, §4 hooks)
- docs/CURRENT_SYSTEM.md
- confirm_recommendation.py, propose_recommendation.py, execution_router.py (solo hooks)

TAREA F1:
1. OrderProposalV1 + DecisionJournalEntryV1 en packages/shared
2. Mapper session(propose) → OrderProposalV1
3. Alembic: decision_journal_entries + repo/writer append-only
4. JournalWriter hooks best-effort en propose/confirm/router (§4 plan)
5. Tests unitarios mapper + writer + hook smoke
6. NO endpoints HTTP, NO contract:gen, NO UI

NO TOCAR:
- ExecuteTrade internals (accounts/trade.py:17)
- Motor money / ledger
- H3 orphan (contract=absent behavior)
- Belief / gobernanza IA
- contract:gen
- Lab/Radar spine entry

BATERÍA (esperada VERDE):
- ruff 0 · mypy 0 ficheros tocados
- pytest nuevos journal + regresión propose/confirm
- pnpm --filter @bolsa/shared typecheck
- pnpm test:decision-spine → 53

PROTOCOLO:
- Subagente acotado + verificador read-only
- NO commit ni push sin aprobación coordinador
- Reporte con file:line de cada hook añadido
```

---

## 5. Qué sigue (coordinador)

| Paso                   | Responsable               | Notas                      |
| ---------------------- | ------------------------- | -------------------------- |
| Revisar ADR-029 + plan | Coordinador / propietario | OK explícito antes de F1   |
| Lanzar subagente F1    | Coordinador               | Brief §4                   |
| Verificar batería      | Coordinador               | plan §1 batería F1         |
| Commit + push          | Propietario               | Tras aprobación            |
| F2 API                 | Propietario               | Requiere OK `contract:gen` |
| F3 UI journal          | Tras F2 o mock local      | Read-only                  |

Ciclos 2–5 (resto del paquete aprobado): **fuera de este traspaso** — el coordinador los encadena tras F1–F3 según plan maestro.

---

## 6. Riesgos / bloqueantes para el coordinador

| Ítem                                             | Severidad | Nota                                        |
| ------------------------------------------------ | --------- | ------------------------------------------- |
| Confusión OrderProposal vs Recommendation        | Media     | Verificador debe rechazar campos duplicados |
| F2 bloqueado por contract:gen freeze             | Alta      | No abrir F2 sin decisión                    |
| Prisma espejo                                    | Baja      | Alembic primero; Prisma seed-only           |
| Test pre-existente `test_list_account_summaries` | Info      | Fail ajeno documentado en backlog           |

---

## 7. Enlaces

- Spine AS-IS NOT FOUND: `fase0-decision-spine-asis-2026-08-24.md` §7
- Mapping: `fase0-decision-spine-mapping-2026-08-24.md` (OrderProposal, Decision journal)
- Tag cierre beta: `traspaso-relevo-tag-v1-7-0-beta-cierre-ciclo-2026-08-24.md`
