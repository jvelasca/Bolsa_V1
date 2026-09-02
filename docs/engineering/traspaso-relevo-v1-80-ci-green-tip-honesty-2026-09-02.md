# Relevo — V1.80 CI GREEN Tip Honesty (mock certification gate)

> **AsOf:** 2026-09-02 · **Estado:** **CERRADA** (código + pre-flight local; **sin stamp CI GREEN remoto** until Actions — tag `v*` / `workflow_dispatch`) · **Auditor:** [`arranque-auditor-v1-80-ci-green-tip-honesty-2026-09-02.md`](./arranque-auditor-v1-80-ci-green-tip-honesty-2026-09-02.md) · **Partida:** V1.79 [`8228d1c3`](https://github.com/jvelasca/Bolsa_V1/commit/8228d1c3) · **Commit:** TBD (parent)

## Hecho

- Workflow: `.github/workflows/release-tag-ci.yml` job `playwright-mock` →  
  `pnpm e2e -- "gp-e2e|gp-v173|gp-v174|gp-v175|gp-v176|gp-v177|gp-v178|gp-v179"`  
  (antes solo `gp-e2e`)
- `certify` sigue `needs: … playwright-mock` · `playwright-integrated` sigue opt-in
- `frontend-ci.yml` **sin** Playwright (by design · sin diff)
- Pre-flight local: **mismo filtro único** que CI (gp-e2e + gp-v173..179) · esperado EXIT 0
- Spec/plan/auditor · CURRENT_SYSTEM · engineering-index

## Reservas (honestidad)

- **Gate expandido ≠ stamp CI GREEN remoto.** El tip honesty del mock gate está listo en YAML; el stamp remoto GREEN es follow-up cuando Actions corra (tag `v*` o `workflow_dispatch`) con éxito.
- Pre-flight local puede aún estar en curso al cerrar docs; expectativa = mismo curado que CI.
- Certificación = **mock E2E** en release-tag · **no** LIVE · **no** Playwright en cada PR · **no** integrated/PG obligatorio

## OUT (intactos)

- LIVE · scheduler · bump package · `dryRun=false` browser · fills ledger
- T2 POV stages · split `fixtures.ts`
- Playwright en `frontend-ci`
- E2E integrado obligatorio en cada certify

## Next candidato

Stamp remoto GREEN (opcional follow-up) vía tag/`workflow_dispatch` **o** siguiente producto a decidir (T2 POV · fixtures split · etc.). **NO LIVE**.
