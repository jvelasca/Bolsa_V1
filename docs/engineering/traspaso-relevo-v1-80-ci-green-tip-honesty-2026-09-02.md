# Relevo — V1.80 CI GREEN Tip Honesty (mock certification gate)

> **AsOf:** 2026-09-02 · **Estado:** **CERRADA** · **stamp CI GREEN remoto** — tag [`v1.80-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.80-beta) → [`7bd6ed81`](https://github.com/jvelasca/Bolsa_V1/commit/7bd6ed81) · [run 33644966298](https://github.com/jvelasca/Bolsa_V1/actions/runs/33644966298) **success** · **Auditor:** [`arranque-auditor-v1-80-ci-green-tip-honesty-2026-09-02.md`](./arranque-auditor-v1-80-ci-green-tip-honesty-2026-09-02.md) · **Partida:** V1.79 [`8228d1c3`](https://github.com/jvelasca/Bolsa_V1/commit/8228d1c3) · **Tip:** `7bd6ed81` (ruff fix post-`aafdb5b9`)

## Hecho

- Workflow: `.github/workflows/release-tag-ci.yml` job `playwright-mock` →  
  `pnpm e2e -- "gp-e2e|gp-v173|gp-v174|gp-v175|gp-v176|gp-v177|gp-v178|gp-v179"`  
  (antes solo `gp-e2e`)
- `certify` sigue `needs: … playwright-mock` · `playwright-integrated` sigue opt-in
- `frontend-ci.yml` **sin** Playwright (by design · sin diff)
- Pre-flight local: **mismo filtro único** que CI → **32 passed** (3 integrated skipped)
- Spec/plan/auditor · CURRENT_SYSTEM · engineering-index
- **Stamp CI GREEN remoto:** jobs GREEN security · shared · spine · frontend · python · playwright-mock (gp-e2e+gp-v173…179) · certify; playwright-integrated skipped (opt-in). Nota: 1ª push tag falló ruff; fix `7bd6ed81` + retag; playwright-mock ya GREEN.

## Reservas (honestidad)

- Certificación = **mock E2E** en release-tag · **no** LIVE · **no** Playwright en cada PR · **no** integrated/PG obligatorio
- Pre-flight local del curado CI: **32 passed** (3 integrated skipped)

## OUT (intactos)

- LIVE · scheduler · bump package · `dryRun=false` browser · fills ledger
- T2 POV stages · split `fixtures.ts`
- Playwright en `frontend-ci`
- E2E integrado obligatorio en cada certify

## Next candidato

**V1.81** T2 POV Stages — **ABIERTA** ([relevo V1.81](./traspaso-relevo-v1-81-t2-pov-stages-2026-09-02.md) · [spec](./spec-v181-t2-pov-stages-2026-09-02.md)). Mock E2E `t2_ready`/`t2_executed` · GP-V181-01 · filtro `+gp-v181`. **NO LIVE**.
