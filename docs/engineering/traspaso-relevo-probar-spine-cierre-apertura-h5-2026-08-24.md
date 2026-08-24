# RELEVO — Probar Decision Spine CERRADO → apertura H5

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (Product / Ops).
> **Propósito:** texto de paso para el **NUEVO CHAT**. Prove Spine (S0–S3) está **en `origin/main`**. Siguiente E1 = **H5** (SEMI pasa `profile` a `check_opening`).
> **AsOf cierre prove:** 2026-08-24. **`main` == `origin/main` == `5e81350`**. Working tree limpio al push.
> **Verificación:** [Verify spine](c9c6e4ff-3f9e-4e8b-9505-e82bd124d0b8) **APROBADO_CON_DEUDA** (deuda = stamp docs pre-push; este relevo la cierra). Protocolo: máx. 1 writer + 1 verifier RO.

---

## 1. Qué quedó hecho (prove)

| Slice | Entrega                                                                       | SHA       |
| ----- | ----------------------------------------------------------------------------- | --------- |
| S0    | H1 `proposal_sector` SEMI + H2 fail-closed summary                            | `5e81350` |
| S1    | `docs/CURRENT_SYSTEM.md` + `decision-spine-cadena-2026-08-24.md` + README JWT | `5e81350` |
| S2    | `pnpm test:decision-spine` · DS-08 AUTO DENY → 0 ExecuteTrade                 | `5e81350` |
| S3    | Golden Scenario TA+cesta congelados                                           | `5e81350` |

Comando: `pnpm test:decision-spine` (32 pytest, sin API live).

## 2. Freeze (sigue)

OrderProposal · Journal · Attribution · orquestador · Daily Mission · Track B · Belief · `PAPER_D_EXECUTE` · Lab→spine · `contract:gen` · H3 orphan (solo doc).

## 3. Siguiente — H5 · CERRADA (working tree, pendiente commit)

Confirm SEMI resuelve `profile` vía `accounts.resolve_scope` → `active_profile_id` → `profile_store.get` y lo pasa a `check_opening` (`confirm_recommendation.py:_resolve_opening_profile`). Tests: `test_confirm_apertura_profile_conservative_veto` · `…_profile_none_allows_same_basket`. Batería: `pnpm test:decision-spine` **34 passed**.

## 4. Anti-sobrecarga

Máx. **2** subagentes (1 writer + 1 verifier RO). Coordinador re-lee file:line. Pre-commit: `pnpm test:decision-spine` + update-last.
