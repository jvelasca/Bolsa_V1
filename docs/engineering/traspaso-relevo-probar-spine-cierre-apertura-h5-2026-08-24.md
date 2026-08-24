# RELEVO — Prove Spine + H5 CERRADOS → apertura UX mesa

> **HISTÓRICO:** UX mesa U0–U5 entregada — arco cerrado en `04e441e`. Relevo vivo: `traspaso-relevo-ux-mesa-u5-cierre-apertura-ciclo-2026-08-24.md`.
> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (Product / Ops).
> **Propósito (histórico):** texto de paso post-H5. Prove Spine (S0–S3) + **H5** en `origin/main`. Apertura UX mesa (Ayuda / S/R / firma) — **no H5**.
> **AsOf cierre H5:** 2026-08-24. **`main` == `origin/main` == `76679d2`**. H5 **CERRADA y PUSHEADA**.
> **Verificación:** [Verify spine](c9c6e4ff-3f9e-4e8b-9505-e82bd124d0b8) **APROBADO_CON_DEUDA** (deuda stamp pre-push cerrada). H5 verificador RO **APROBADO**. Protocolo: máx. 1 writer + 1 verifier RO.

---

## 1. Qué quedó hecho (prove)

| Slice | Entrega                                                                       | SHA       |
| ----- | ----------------------------------------------------------------------------- | --------- |
| S0    | H1 `proposal_sector` SEMI + H2 fail-closed summary                            | `5e81350` |
| S1    | `docs/CURRENT_SYSTEM.md` + `decision-spine-cadena-2026-08-24.md` + README JWT | `5e81350` |
| S2    | `pnpm test:decision-spine` · DS-08 AUTO DENY → 0 ExecuteTrade                 | `5e81350` |
| S3    | Golden Scenario TA+cesta congelados                                           | `5e81350` |

Comando: `pnpm test:decision-spine` (32 pytest en prove; 34 tras H5).

## 2. Freeze (sigue)

OrderProposal · Journal · Attribution · orquestador · Daily Mission · Track B · Belief · `PAPER_D_EXECUTE` · Lab→spine · `contract:gen` · H3 orphan (solo doc).

## 3. H5 · CERRADA y PUSHEADA (`76679d2`)

Confirm SEMI resuelve `profile` vía `accounts.resolve_scope` → `active_profile_id` → `profile_store.get` → `check_opening`. Código H5 `f56af2f` · stamp docs `76679d2`. Tests: `test_confirm_apertura_profile_conservative_veto` · `…_profile_none_allows_same_basket`. Batería: `pnpm test:decision-spine` **34**. Verificador RO **APROBADO**.

## 4. Siguiente · UX mesa (histórico — entregada)

U0–U4 ancla previa `6f26f9d` · U5 + stamp en `04e441e`. Continuación viva: `traspaso-relevo-ux-mesa-u5-cierre-apertura-ciclo-2026-08-24.md` (**decisión de ciclo**).

## 5. Anti-sobrecarga

Máx. **2** subagentes (1 writer + 1 verifier RO). Coordinador re-lee file:line. Pre-commit: batería de la fase + update-last.
