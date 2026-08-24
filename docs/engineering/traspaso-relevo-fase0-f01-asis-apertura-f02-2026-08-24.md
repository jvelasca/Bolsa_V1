# RELEVO / TRASPASO — Fase 0 Decision Spine · cierre F0.1 AS-IS → apertura F0.2 TO-BE

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (Product / Ops).
> **Propósito:** texto de paso para el **NUEVO CHAT** (mañana). Read-first antes de escribir.
> **AsOf cierre:** 2026-08-24 (noche). **Siguiente trabajo:** 2026-08-25 · **F0.2 TO-BE docs-only**.
> **SHA al cerrar este hilo:** verificar con `git fetch; git rev-parse origin/main` (no incrustar como verdad absoluta). Working tree puede tener **docs Fase 0 sin commit**.

---

## 1. Qué está hecho (no reabrir)

- **Track B split backtests B0–B12 CERRADO.** No reabrir `backtests-page` split. Relevo histórico: `traspaso-relevo-track-b-b12-cierre-split-siguiente-2026-08-24.md`.
- **Identidad de producto CONGELADA:** doble cara. QROS en Lab + Investment OS en la mesa, unidos por Decision Spine. No rebrand que mate ADR-011.
- **F0.1 AS-IS HECHO (docs, cero código de producto):** [`fase0-decision-spine-asis-2026-08-24.md`](./fase0-decision-spine-asis-2026-08-24.md).
- Inventario contrastado (subagente explore + coordinador, 12 citas re-leídas). Hallazgo: **motores sí, columna no**; IO en cliente; Fit stub; dos entradas a `ExecuteTrade`.

## 2. Qué NO tocar (freeze)

- Motor money / ledger / `ExecuteTrade` internals.
- Gobernanza IA / Belief.
- `contract:gen` salvo fase pactada.
- Purge storage E8 N.
- Código de spine (F0.2 es **solo documento TO-BE**).

## 3. Tarea de mañana (una rebanada)

**Solo F0.2 TO-BE.** Un markdown. Coordinador redacta (sin explore masivo). Input obligatorio: el AS-IS F0.1 + tesis competitiva ya pactada (no copiar TV/IBKR/QC; Decision Package + tres colas + SEMI paper).

**No abrir F0.3 mapping** en el mismo chat si el contexto se satura.

**Criterio de parada:** TO-BE cabe en una lectura; no inventa módulos que el AS-IS no haya marcado NOT FOUND o stub; Daily es vista; Fit es el único create neto a medio plazo.

## 4. Protocolo anti-fallo

- Una rebanada = un artefacto.
- Toda afirmación de código en F0.2 que cite AS-IS debe llevar `path:line` del inventario, no memoria.
- Coordinador no se fía de subagentes: relee citas.
- Cero commits salvo que el propietario los pida.

## 5. Texto de arranque (pegar en el chat nuevo)

```
CONTEXTO (2026-08-25): Fase 0 Decision Spine. F0.1 AS-IS CERRADO.
LEE: docs/engineering/traspaso-relevo-fase0-f01-asis-apertura-f02-2026-08-24.md
+ docs/engineering/fase0-decision-spine-asis-2026-08-24.md
+ backlog §0 + PROJECT_PREMISES ⭐§0 + PROJECT_STATE §2b.

Identidad: QROS (Lab) + Investment OS (mesa) + Decision Spine. No reconstruir.

TAREA: solo F0.2 TO-BE (un markdown, cero código). No mapping, no Daily UI, no Fit code.
NO TOCAR: money, IA, contract:gen, split B1–B12.
Protocolo: una rebanada, citas file:line del AS-IS, sin alucinar tipos que F0.1 marcó NOT FOUND.
```
