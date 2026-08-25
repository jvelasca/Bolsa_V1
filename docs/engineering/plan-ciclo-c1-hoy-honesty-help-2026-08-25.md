# Plan — Ciclo C1 Hoy honesty + HELP (v1.8.1 P0)

> **Padre:** [`roadmap-v181-operational-consolidation-2026-08-25.md`](./roadmap-v181-operational-consolidation-2026-08-25.md) · ADR-031 §4 Daily Command.
> **AsOf:** 2026-08-25.
> **Estado:** **CÓDIGO LISTO** (commit pendiente) · D1–D8 OK · tests shared 68 + help C1.
> **Método:** rebanada P0 de auditoría v1.8; Ranking ≠ BUY; sin Alembic; sin `contract:gen`; sin LLM; **sin** ActionQueue plena; **sin** DTO canónico; **sin** thaw.

---

## 0. Objetivo

Hoy es proyección del Decision Board, no motor. Hoy **no** puede transformar la ausencia de `TradePlan` en BUY. El whyNot heurístico **no** puede fingir `fit`. La Ayuda debe describir v1.8 (AUTO BETA-D, TradePlan, Hoy, spine).

### Qué entra vs qué queda fuera

| Incluye (C1)                                                                   | Excluye                                      |
| ------------------------------------------------------------------------------ | -------------------------------------------- |
| F3/sesión **sin** TradePlan vivo → `WATCH` (nunca BUY / nunca ARMED inventado) | ActionQueue prioridad / top-N separado (C3)  |
| Heurística BLOCKED/WATCH → `whyNot: legacy_projection`                         | Prisma/Alembic (C2) · TradePlan DTO (C4)     |
| Label UI «proyección sin plan»                                                 | Target / PositionState / módulos thin nuevos |
| HELP_CONTENT_AS_OF = 2026-08-25 + copy AUTO BETA-D / Hoy / TradePlan           | Reescribir toda la Ayuda                     |
| Tests Hoy + stamp                                                              | thaw / `PAPER_D_EXECUTE` / broker            |

---

## 1. Decisiones (D1–D8)

| Id  | Decisión                                                                                                                                  |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Sin TradePlan vivo: `kind=WATCH`, `status=WATCH`. **Nunca** BUY/TRIGGERED por fallback de gate.                                           |
| D2  | Heurística no inventa ARMED (bucket auto/paper sin plan → WATCH). ARMED/BUY solo con plan vivo.                                           |
| D3  | VETO sin plan → BLOCKED con `whyNot: ["legacy_projection"]` (no `fit`). WATCH heurístico → mismo código. Plan vivo conserva sus `whyNot`. |
| D4  | `legacy_projection` entra en el union WhyNot (TS + Python Literal). El mapper TradePlan **no** lo emite.                                  |
| D5  | No nuevo kind `UNRESOLVED` en C1 (WATCH cubre «sin plan»). UI KIND_CLASS intacta.                                                         |
| D6  | `check_opening` / Confirm / Fill / Router / PAPER_D / 5.x / 8.x / I1–I3 / RX1 **intactos**.                                               |
| D7  | HELP: AUTO UI BETA-D (`ACTIVAR AUTO` + opt-in env) ≠ Lista AUTO Lab; Hoy ≠ motor; tesis ≠ plan ≠ permiso; advisory thin ≠ permiso.        |
| D8  | Stamp CURRENT_SYSTEM + ADR-031 nota C1 + CHANGELOG Unreleased + index. C2+ parked.                                                        |

Si D1 vuelve a emitir BUY sin plan, D3 usa `fit` ficticio, o C1 añade un mapper thin: **parar y replanificar**.

---

## 2. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · SETUP Wyckoff cerrada · Shadow AUTO off · 5.x + 8.0–8.2 + I1–I3 + RX1 intactos · advisory ≠ permiso · C2–C6 parked.
