# RELEVO — Ciclo 4.1 `NO_NEW_LONGS` (2026-08-25)

> **Padre:** [`traspaso-relevo-ciclo-40-stop-entry-size-2026-08-25.md`](./traspaso-relevo-ciclo-40-stop-entry-size-2026-08-25.md).
> **Plan:** [`plan-ciclo-41-no-new-longs-entrysetup-2026-08-25.md`](./plan-ciclo-41-no-new-longs-entrysetup-2026-08-25.md) (D1–D6 OK).
> **Política:** [`docs/adr/031-operational-model-tesis-plan-permiso.md`](../adr/031-operational-model-tesis-plan-permiso.md) Golden G · §6 nota 4.1.
> **AsOf:** 2026-08-25.
> **HEAD:** `97f4862` = `origin/main`. **PUSHEADO.**

---

## 1. Qué se cerró

Golden G en capa **Plan**: long + `risk_off`/`crisis` → `BLOCKED` + `whyNot: regime`. Shorts OK. Confirm sin régimen no inventa veto. Propose pasa `macro_assess.regime`. **No** EntrySetup. **No** `check_opening`.

| Pieza           | Regla                                        |
| --------------- | -------------------------------------------- |
| Regímenes veto  | `risk_off`, `crisis`                         |
| Dirección       | solo `long` (`NO_NEW_LONGS`)                 |
| Acumulación     | `whyNot` puede ser `regime` + `fit` juntos   |
| Confirm rebuild | `market_regime=None` → no veta (D6)          |
| Fuente propose  | `macro_assess.regime` (fallback `"neutral"`) |

## 2. Batería

- ruff touched Python: limpio
- `pnpm test:decision-spine` → **79 passed** (antes 75)

## 3. Commits

| SHA       | Mensaje                                                                |
| --------- | ---------------------------------------------------------------------- |
| `97f4862` | feat(spine): ADR-031 Ciclo 4.1 NO_NEW_LONGS via TradePlan regime veto. |

Push: `f02ff1a..97f4862` → `origin/main`.

## 4. Siguiente (E1)

1. ~~Commit~~ · ~~Push~~.
2. EntrySetup (Ciclo 4.2) — **prohibido** sin plan E1 propio.

## 5. No tocado

EntrySetup · F9-B · purge · `PAPER_D_EXECUTE` · broker · `contract:gen` · thesis health / MFE · qty del ticket Confirm · `check_opening`.
