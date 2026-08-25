# Plan — Ciclo C4 TradePlan shape canónico thin (v1.8.1)

> **Padre:** [`roadmap-v181-operational-consolidation-2026-08-25.md`](./roadmap-v181-operational-consolidation-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **CÓDIGO LISTO**.
> **Método:** reducir ambigüedad de shapes; **sin** `contract:gen`; sin Pydantic DTO nuevo; C1/C3/C5 intactos.

---

## 0. Objetivo

Documentar el camino canónico de TradePlan y unificar el reader de Hoy. No borrar fallbacks legacy todavía.

### Qué entra vs qué queda fuera

| Incluye (C4)                                                                 | Excluye                         |
| ---------------------------------------------------------------------------- | ------------------------------- |
| SoT: Board `session.tradePlan` ← `runtime.tradePlan`; F3 `payload.tradePlan` | OpenAPI / `contract:gen`        |
| `readCanonicalTradePlan` usado por Hoy; fallbacks marcados `legacy`          | Pydantic DTO / borrar fallbacks |
| `HoyQueueItem.planSource`: `live` \| `projection`                            | Confirm/propose/spine rewrite   |

---

## 1. Decisiones (D1–D8)

| Id  | Decisión                                                                                                |
| --- | ------------------------------------------------------------------------------------------------------- |
| D1  | Canónico: sesiones = `session.tradePlan`; F3 = `extra.payload.tradePlan`. Resto = legacy, no autoridad. |
| D2  | Extraer `readCanonicalTradePlan`; fallbacks con comentario `legacy`. No borrar.                         |
| D3  | `planSource: "live" \| "projection"` en HoyQueueItem.                                                   |
| D4  | **No** Pydantic DTO ni `contract:gen`. v1.9 contrato fuerte (ADR-032).                                  |
| D5  | Confirm / propose / spine / check_opening **intactos**.                                                 |
| D6  | Tests: payload anidado vivo; sin plan → WATCH (C1).                                                     |
| D7  | Sin Alembic.                                                                                            |
| D8  | Relevo C4. E1 = C6 coordinador.                                                                         |

Si D4 genera OpenAPI o D5 toca opening: **parar**.

---

## 2. Ficheros

- `packages/shared/src/cognitive/hoy-queue.ts` · `hoy-queue.test.ts`
- Stamp CURRENT_SYSTEM · ADR-031 nota C4 · CHANGELOG · relevo

## 3. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · C1/C3/C5 intactos · `PAPER_D_EXECUTE` off.
