# Plan — F2.1 PositionState transitions (Operational Core)

> **Padre:** [`plan-f2-position-state-2026-08-25.md`](./plan-f2-position-state-2026-08-25.md) · roadmap [`roadmap-v19-operational-core-2026-08-25.md`](./roadmap-v19-operational-core-2026-08-25.md) · ADR-032 §3 · gap [`adr-032-audit-gap-2026-08-25.md`](./adr-032-audit-gap-2026-08-25.md) §2 · relevo F2 [`traspaso-relevo-f2-position-state-2026-08-25.md`](./traspaso-relevo-f2-position-state-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **CERRADO** (D1–D8 OK) · batería spine **180**.
> **Método:** ciclo de vida **mecánico** sobre PositionState F2. Sin ExitPlan. Sin promocionar thin 5.x/8.x. Sin wire Confirm/opening. Sin `contract:gen`. Sin Alembic.

---

## 0. Objetivo

Hacer que PositionState **envejezca** tras `OPEN`: mark → `unrealizedR`, reduce → `PARTIAL`/`CLOSED`, stop geométrico → `PROTECTED`. Responde al hueco auditor («qué ocurre ya abierta») sin abrir política de salida (eso es F3).

### Qué entra vs qué queda fuera

| Incluye (F2.1)                                                                  | Excluye                                                            |
| ------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| Funciones puras sobre `PositionState` (TS + Py)                                 | ExitPlan · ExitPermission · ExecutionPlan                          |
| `applyMark` → `unrealizedR` (+ picos MFE/MAE honestos)                          | Promover `protectPlan` / `trailPlan` / `exitRadar` / `mfeMae` thin |
| `applyReduce` → `remainingQuantity` · `realizedR` · `PARTIAL`/`CLOSED`          | Wire Confirm / opening / Hoy CTA                                   |
| `applyCurrentStop` → `currentStop` · `PROTECTED` **solo** hecho geométrico (BE) | Razones canónicas de salida (F3)                                   |
| Tests familia **C** (lifecycle) + **E** (accounting)                            | Auto-exit · broker · `PAPER_D_EXECUTE` on                          |
| Stamp CURRENT_SYSTEM + HELP si concepto de usuario                              | `contract:gen` · Alembic · ActionabilityScore                      |

---

## 1. Decisiones (D1–D8) — OK

| Id     | Decisión                                                                                                                                                                                                                                                                                                                                                                                 |
| ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **D1** | Crecimiento **dentro** de PositionState F2. API pura: `applyMark` / `applyReduce` / `applyCurrentStop`. Factory `from_fill` **intacta** (sigue emitiendo `OPEN`). Thin 5.x/8.x **congelados** — no se copian a stubs.                                                                                                                                                                    |
| **D2** | **`applyMark(position, markPrice, at?)`:** requiere `initialRisk > 0` y `actualEntry`. `unrealizedR` = R firmado (long: `(mark−entry)/risk`; short: `(entry−mark)/risk`). Sin risk → no inventa R (`unrealizedR` queda). Actualiza `updatedAt`. **No** cambia `status` por mark solo.                                                                                                    |
| **D3** | **MFE/MAE en mark (C5):** si hay `unrealizedR` finito, picos: `mfeR = max(prev, unrealizedR)`, `maeR = min(prev, unrealizedR)` (mae más negativo). `source`: si prev era `none` → `close_proxy`; si ya `bars`/`close_proxy` → se conserva (no mezclar inventando `bars`). Mark **no** es peak de barras.                                                                                 |
| **D4** | **`applyReduce(position, qty, exitPrice?, at?)`:** `qty` en (0, remaining]. Baja `remainingQuantity`. `realizedR` acumula R del tramo si hay `exitPrice` + `initialRisk` + entry. Status: `remaining > 0` → `PARTIAL` (salvo ya `CLOSED`); `remaining = 0` → `CLOSED` + `exitStatus: done`. `CLOSED` es **terminal** (reduce/mark/stop posteriores → no-op / null). Qty inválida → null. |
| **D5** | **`PROTECTED` geométrico — no política:** `applyCurrentStop(position, stop, at?)` setea `currentStop` y re-evalúa status por precedencia (§ abajo). BE = long `stop >= actualEntry` · short `stop <= actualEntry`. **No** lee thin protect/trail. **No** razones F3. Sin `actualEntry` → no marca PROTECTED.                                                                             |
| **D6** | Stubs `thesisHealth` / `protectionState` / `trailing` siguen `{status:none}`. `exitStatus`: `none` hasta reduce-a-cero (`done`). Nada de `hint`/`armed` sin ExitPlan. PositionState ≠ permiso de salida.                                                                                                                                                                                 |
| **D7** | Paridad **shared TS + Python**. Sin Alembic · sin `contract:gen` · sin HTTP · sin Confirm/opening/Hoy. HELP: PositionState puede estar OPEN/PARTIAL/PROTECTED/CLOSED; mark/reduce ≠ orden broker.                                                                                                                                                                                        |
| **D8** | Tests invariante (C+E) en shared + py · stamp `CURRENT_SYSTEM` / CHANGELOG / roadmap · relevo F2.1. **E1** siguiente: **F3 ExitPlan** (razones) **o** INFRA CI-by-tag. **No** ExecutionPlan→broker.                                                                                                                                                                                      |

### Precedencia de status (resumen)

```text
CLOSED      → terminal (gana siempre)
else remaining == 0 → CLOSED   (vía reduce)
else BE stop        → PROTECTED
else remaining < quantity → PARTIAL
else                → OPEN
```

Mark **no** participa en esta precedencia.

---

## 2. Ficheros previstos

- `packages/shared/src/cognitive/position-state.ts` · `position-state.test.ts`
- `packages/py/analytics/.../position_state.py` · `packages/py/application/tests/test_position_state.py`
- HELP (`hoy-en-la-mesa` / as-of) si hace falta
- Stamp: `CURRENT_SYSTEM.md` · CHANGELOG · roadmap v1.9 · relevo F2.1

## 3. Freeze (intactos)

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · TradePlan ≠ permiso · PositionState ≠ permiso de salida · SETUP Wyckoff cerrada · 5.x + 8.0–8.2 thin **congelados** · I1–I3 + RX1 · `PAPER_D_EXECUTE` **off** · C1 Hoy honesty · dedup Hoy por símbolo · F1 / factory F2 / opening **intactos**.
