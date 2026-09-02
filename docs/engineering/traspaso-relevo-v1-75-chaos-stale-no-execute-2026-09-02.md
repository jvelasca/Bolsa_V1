# Relevo — V1.75 Chaos & stale → no-execute

> **AsOf:** 2026-09-02 · **Estado:** CERRADA (código + E2E mock locales) · **Auditor:** [`arranque-auditor-v1-75-chaos-stale-no-execute-2026-09-02.md`](./arranque-auditor-v1-75-chaos-stale-no-execute-2026-09-02.md) · **Partida:** V1.74 `67f922bf`

## Hecho

- Helpers: `staleNoExecuteAutoDesk` · `staleNoExecuteUnknownSubmitIntent` · `seedStaleNoExecuteBrowserState`
- Mock API **separado**: `installHoyStaleNoExecuteMocks` (`hoyStale` — no contaminar V1.74)
- E2E mock: `gp-v175-chaos-stale-no-execute-mock.spec.ts` (GP-V175-01..04)
- pytest: `test_v175_chaos_stale_no_execute.py` (GP-V175-05..07)
- Spec/plan/auditor V1.75

## Reservas

- Certificación cierre = **mock E2E** + pytest application
- **No** stamp CI GREEN · **No** `dryRun=false` browser
- Chaos money-path masivo / LIVE / bump package → **fuera**

## Next candidato

**Package bump** (solo con palabra explícita) · **NO LIVE**.
