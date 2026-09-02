# RELEVO — tag v1.85-beta → auditoría externa (2026-09-02)

> **Padre:** [`traspaso-relevo-v1-85-lifecycle-integrity-2026-09-02.md`](./traspaso-relevo-v1-85-lifecycle-integrity-2026-09-02.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** **tag tip publicado** — tip `v1.85-beta` → `996c2f7d` · Release-tag CI en curso ([run 33663534894](https://github.com/jvelasca/Bolsa_V1/actions/runs/33663534894)) · **no declarar PASS** hasta GREEN + respuesta auditor.  
> **Arranque auditor externo:** [`arranque-auditor-v1-85-beta-2026-09-02.md`](./arranque-auditor-v1-85-beta-2026-09-02.md).  
> **Partida:** V1.84 PASS 9,5/10 · [`v1.84-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.84-beta) → [`504aa19d`](https://github.com/jvelasca/Bolsa_V1/commit/504aa19d) · [run 33659480690](https://github.com/jvelasca/Bolsa_V1/actions/runs/33659480690).  
> **Fuera:** LIVE · `PAPER_D_EXECUTE` default on · scheduler · bump package · Playwright en `frontend-ci` · integrated E2E obligatorio · event store FastAPI/PG.

---

## 0. Confirmación

Sobre tip `v1.85-beta` → `996c2f7d` (partida `v1.84-beta` → `504aa19d` PASS):

| Pieza                     | Entrega                                                                  |
| ------------------------- | ------------------------------------------------------------------------ |
| FSM validate              | `validateTransition` · `appendValidatedLifecycleEvent` fail-closed       |
| Tiempo + identidad        | `time_regression` · `eventId` · `fillId` · `positionId` · idempotent 200 |
| Accounting                | realized/unrealized/totalPnl · cash equity (path event-driven)           |
| HTTP mock                 | POST 409 reject / 400 invalid · log intacto                              |
| Vitest                    | `lifecycle-fsm.test.ts` (16) en frontend-ci                              |
| GP-V185                   | reject · idempotency · trail PnL equity única                            |
| Filtro CI playwright-mock | `gp-e2e\|gp-v173\|…\|gp-v184\|gp-v185`                                   |
| Pre-flight local          | 40 passed (3 integrated skipped) · tsc EXIT 0                            |

Freeze: Confirm = firma · `PAPER_D_EXECUTE` off · no LIVE · package `1.35.0-beta`.

## 1. Release

| Pieza       | Valor                                                                                                               |
| ----------- | ------------------------------------------------------------------------------------------------------------------- |
| Tag tip     | `v1.85-beta` → `996c2f7d`                                                                                           |
| Docs stamp  | (post-GREEN en `main`; no exige retag)                                                                              |
| Previo tip  | `v1.84-beta` → `504aa19d` (CI GREEN · run 33659480690 · PASS 9,5/10)                                                |
| CI tag      | **en curso** — [Release tag CI](https://github.com/jvelasca/Bolsa_V1/actions/runs/33663534894) · `headSha=996c2f7d` |
| Pre-release | https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.85-beta                                                        |

## 2. Pre-flight

```bash
pnpm --filter @bolsa/web exec vitest run e2e/helpers/lifecycle-fsm.test.ts
# → 16 passed

E2E_RUN=1 pnpm --filter @bolsa/web e2e -- "gp-e2e|gp-v173|gp-v174|gp-v175|gp-v176|gp-v177|gp-v178|gp-v179|gp-v181|gp-v183|gp-v184|gp-v185"
# → 40 passed (3 integrated skipped)

pnpm --filter @bolsa/web exec tsc --noEmit
# → EXIT 0
```

## 3. Auditoría

Abrir chat nuevo con el bloque de [`arranque-auditor-v1-85-beta-2026-09-02.md`](./arranque-auditor-v1-85-beta-2026-09-02.md) **después** de CI GREEN.  
**No** declarar PASS hasta respuesta del auditor. Guardar respuesta como `respuesta-auditor-v185-…` cuando exista.

## 4. Cadena tips CI GREEN recientes

```text
v1.80-beta → 7bd6ed81 · run 33644966298
v1.81-beta → 4fcfc9bb · run 33648642728
v1.82-beta → d0ccf235 · run 33651647262
v1.83-beta → dc596ee5 · run 33657045026
v1.84-beta → 504aa19d · run 33659480690
v1.85-beta → 996c2f7d · run 33663534894 (en curso)
```
