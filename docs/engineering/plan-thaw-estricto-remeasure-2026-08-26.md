# Plan — Thaw estricto remasure W+2 (docs/ops)

> **Padre:** [`deuda-thaw-estricto-runbook-2026-08-25.md`](./deuda-thaw-estricto-runbook-2026-08-25.md) · ADR-023 Accepted BETA-D · relevo thaw stamp.
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO (remeasure docs/ops).** ≠ Accept estricto. Deuda abierta.
> **Relevo previo:** [`traspaso-relevo-thaw-paper-d-execute-2026-08-26.md`](./traspaso-relevo-thaw-paper-d-execute-2026-08-26.md).

---

## Objetivo

Registrar **W+2** en el runbook de deuda estricto P1–P5 con números **medidos** (o honestidad **not measured** si infra down). **No** Accept estricto. **No** feature code. **No** flip `PAPER_D_EXECUTE`.

## Decisiones

| ID  | Decisión                                                                                     |
| --- | -------------------------------------------------------------------------------------------- |
| D1  | Scope = remasure docs/ops (runbook fila W+2 + plan + relevo ± evidencia).                    |
| D2  | Método = `thaw_estricto_snapshot.mjs` y/o runbook §2; **nunca** inventar métricas.           |
| D3  | Remeasure **≠** Accept estricto; ADR-023 sigue **Accepted BETA-D**; W2–W4 intactos.          |
| D4  | **≠** inventar `stance=buy` · **≠** fills fake · **≠** contar `buys_testish`.                |
| D5  | **≠** flip `PAPER_D_EXECUTE` / `.env.example` on; stamp opt-in local intacto; default OFF.   |
| D6  | Freeze: LAB≠TRADING · LLM no ejecuta · broker no · I1/I3/RX1 · Confirm firma · mesa paper.   |
| D7  | Docs only; **no** mezclar per-account venue ni default-on.                                   |
| D8  | Si API/Docker down → fila **not measured**; reintentar cuando stack up; deuda sigue abierta. |

## Kernel

```text
BETA-D Accepted
→ measure P1–P5 (o not measured)
→ fill W+2
≠ Accept estricto ≠ env flip ≠ per-account
```

## Freeze

Thaw stamp cerrado · VS-1 · RV-1 · JP-1 · Confirm firma · `PAPER_D_EXECUTE` default off · Accept estricto parked · per-account parked · default-on parked.

## E1

Parked: Accept estricto (DoD runbook §4 + palabra owner) · per-account venue · default-on.
