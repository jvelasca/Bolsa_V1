# RELEVO — Ciclo 4.2 `EntrySetup` (2026-08-25)

> **Padre:** [`traspaso-relevo-ciclo-41-no-new-longs-2026-08-25.md`](./traspaso-relevo-ciclo-41-no-new-longs-2026-08-25.md).
> **Plan:** [`plan-ciclo-42-entrysetup-2026-08-25.md`](./plan-ciclo-42-entrysetup-2026-08-25.md) (D1–D6 OK).
> **AsOf:** 2026-08-25.
> **HEAD previo:** `f646d2a` = `origin/main`. Working tree **pendiente commit**.
> **Chat:** contexto largo (4.0→4.1→4.2). Tras commit/push, preferir **chat nuevo** con este relevo.

---

## 1. Qué se cerró

`EntrySetup` `breakout|pullback|wyckoff|none` + clasificador barras; `entry_ready` = bias TA **y** setup≠none; JSON `entrySetup`. Prioridad breakout > pullback > wyckoff. **Sin** `ARMED`. **Sin** `contract:gen`. `check_opening` intacto. 4.0 stop/size y 4.1 régimen intactos.

## 2. Batería

- ruff touched Python: limpio
- `pnpm test:decision-spine` → **81 passed** (antes 79)

## 3. Siguiente (E1)

1. **Commit** WT. **No auto-commit.**
2. Push solo si el propietario lo pide.
3. `ARMED` / Wyckoff formal — **prohibido** sin plan 4.3+.

## 4. No tocado

`ARMED` · F9-B · purge · `PAPER_D_EXECUTE` · broker · `contract:gen` · thesis health · qty Confirm · `check_opening`.
