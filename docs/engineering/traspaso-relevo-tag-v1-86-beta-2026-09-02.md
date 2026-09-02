# RELEVO — tag v1.86-beta → auditoría externa (2026-09-02)

> **Padre:** [`traspaso-relevo-v1-86-lifecycle-event-store-2026-09-02.md`](./traspaso-relevo-v1-86-lifecycle-event-store-2026-09-02.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** **CI GREEN** — tip `v1.86-beta` → `baaa7034` · Release-tag CI **GREEN** ([run 33686297402](https://github.com/jvelasca/Bolsa_V1/actions/runs/33686297402)) · **listo para auditoría externa**.  
> **Arranque auditor externo:** [`arranque-auditor-v1-86-beta-2026-09-02.md`](./arranque-auditor-v1-86-beta-2026-09-02.md).  
> **Partida:** V1.85 PASS modelo mock 9,25/10 · **NO** beta estable · [`v1.85-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.85-beta) → [`665242a3`](https://github.com/jvelasca/Bolsa_V1/commit/665242a3) · [run 33663836923](https://github.com/jvelasca/Bolsa_V1/actions/runs/33663836923) · [`respuesta-auditor-v185`](./respuesta-auditor-v185-lifecycle-integrity-2026-09-02.md).  
> **Fuera:** LIVE · `PAPER_D_EXECUTE` default on · scheduler · bump package · Playwright en `frontend-ci` · integrated E2E obligatorio · V1.87.

---

## 0. Confirmación

Sobre tip `v1.86-beta` → `baaa7034` (partida `v1.85-beta` → `665242a3`):

| Pieza                      | Entrega                                                                              |
| -------------------------- | ------------------------------------------------------------------------------------ |
| ENTRY accounting           | `POSITION_OPENED` debita caja · CLOSED trail cash/equity **100055**                  |
| Idempotencia estricta      | mismo eventId+hash → 200 · distinto → `event_id_conflict` 409 · CLOSE replay estable |
| Identity / payload / trail | envelope inmutable · qty/price/fees/CLOSE · LONG no-relajación                       |
| PG event store             | Alembic `015` · append-only · POST/GET `/api/lifecycle/*`                            |
| Domain + mock              | `bolsa_domain.lifecycle` · espejo TS · Vitest · GP-V186                              |
| CI                         | python offline + domain · **lifecycle-pg** required · filtro `+gp-v186`              |

Freeze: Confirm = firma · `PAPER_D_EXECUTE` off · no LIVE · package `1.35.0-beta`.

## 1. Release

| Pieza       | Valor                                                                                                            |
| ----------- | ---------------------------------------------------------------------------------------------------------------- |
| Tag tip     | `v1.86-beta` → `baaa7034`                                                                                        |
| Docs stamp  | `a8867559` (post-GREEN en `main`; no exige retag)                                                                |
| Previo tip  | `v1.85-beta` → `665242a3` (CI GREEN · run 33663836923)                                                           |
| CI tag      | **GREEN** — [Release tag CI](https://github.com/jvelasca/Bolsa_V1/actions/runs/33686297402) · `headSha=baaa7034` |
| Pre-release | https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.86-beta                                                     |

Jobs del push `v1.86-beta` (2026-09-02), todos **success** salvo integrated **skipped**:

| Job                   | Resultado |
| --------------------- | --------- |
| security (gitleaks)   | success   |
| shared                | success   |
| decision-spine        | success   |
| frontend              | success   |
| python                | success   |
| lifecycle-pg          | success   |
| playwright-mock       | success   |
| playwright-integrated | skipped   |
| certify               | success   |

## 2. Pre-flight

```bash
pnpm --filter @bolsa/web exec vitest run e2e/helpers/lifecycle-fsm.test.ts
# → 23 passed

uv run python -m pytest packages/py/domain/tests/test_lifecycle_events.py -q
# → 21 passed

pnpm --filter @bolsa/web exec tsc --noEmit
# → EXIT 0
```

## 3. Auditoría

Abrir chat nuevo con el bloque de [`arranque-auditor-v1-86-beta-2026-09-02.md`](./arranque-auditor-v1-86-beta-2026-09-02.md).  
**No** declarar PASS hasta respuesta del auditor. Guardar respuesta como `respuesta-auditor-v186-…` cuando exista.

## 4. Cadena tips CI GREEN recientes

```text
v1.82-beta → d0ccf235 · run 33651647262
v1.83-beta → dc596ee5 · run 33657045026
v1.84-beta → 504aa19d · run 33659480690
v1.85-beta → 665242a3 · run 33663836923
v1.86-beta → baaa7034 · run 33686297402
```
