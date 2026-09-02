# RELEVO — tag v1.87-beta → auditoría externa (2026-09-02)

> **Padre:** [`traspaso-relevo-v1-87-lifecycle-operational-2026-09-02.md`](./traspaso-relevo-v1-87-lifecycle-operational-2026-09-02.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** **CI GREEN** — tip `v1.87-beta` → `646b97ac` · Release-tag CI **GREEN** ([run 33689747400](https://github.com/jvelasca/Bolsa_V1/actions/runs/33689747400)) · **listo para auditoría externa**.  
> **Arranque auditor externo:** [`arranque-auditor-v1-87-beta-2026-09-02.md`](./arranque-auditor-v1-87-beta-2026-09-02.md).  
> **Partida:** V1.86 arquitectura 9,0/10 · explotable 7,5/10 · **NO** beta estable · [`v1.86-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.86-beta) → [`baaa7034`](https://github.com/jvelasca/Bolsa_V1/commit/baaa7034) · [`respuesta-auditor-v186`](./respuesta-auditor-v186-lifecycle-event-store-2026-09-02.md).  
> **Fuera:** LIVE · `PAPER_D_EXECUTE` default on · scheduler · bump package · Playwright en `frontend-ci` · integrated E2E obligatorio · V1.88.

---

## 0. Confirmación

Sobre tip `v1.87-beta` → `646b97ac` (partida `v1.86-beta` → `baaa7034`):

| Pieza               | Entrega                                                                    |
| ------------------- | -------------------------------------------------------------------------- |
| Auth lifecycle HTTP | JWT obligatorio · account/position ownership → 401/403/404                 |
| Serialización       | `sequence_no` · `lifecycle_aggregates` FOR UPDATE · UNIQUE(pos, seq)       |
| Alembic real        | 015 ensure-indexes · 016 · CI `alembic upgrade head` (sin metadata.create) |
| DTO / dinero        | `extra="forbid"` · Decimal domain→DB · IntegrityError clasificado          |
| Tests               | auth isolation · concurrent T1 · migration-from-zero · DTO forbid          |
| CI                  | python offline · **lifecycle-pg** (Alembic+auth) required · `+gp-v186`     |

Freeze: Confirm = firma · `PAPER_D_EXECUTE` off · no LIVE · package `1.35.0-beta`.

## 1. Release

| Pieza       | Valor                                                                                                            |
| ----------- | ---------------------------------------------------------------------------------------------------------------- |
| Tag tip     | `v1.87-beta` → `646b97ac`                                                                                        |
| Docs stamp  | `3cfc9739` (post-GREEN en `main`; no exige retag)                                                                |
| Previo tip  | `v1.86-beta` → `baaa7034` (CI GREEN · run 33686297402)                                                           |
| CI tag      | **GREEN** — [Release tag CI](https://github.com/jvelasca/Bolsa_V1/actions/runs/33689747400) · `headSha=646b97ac` |
| Pre-release | https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.87-beta                                                     |

Jobs del push `v1.87-beta` (2026-09-02), todos **success** salvo integrated **skipped**:

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

## 2. Pre-flight (local)

```bash
python -m pytest packages/py/domain/tests/test_lifecycle_events.py \
  packages/py/application/tests/test_lifecycle_event_store.py \
  packages/py/infrastructure/tests/test_lifecycle_event_store_pg.py \
  apps/api-python/tests/test_lifecycle_auth.py \
  apps/api-python/tests/test_lifecycle_dto.py -q
# → 34 passed
```

## 3. Auditoría

Abrir chat nuevo con el bloque de [`arranque-auditor-v1-87-beta-2026-09-02.md`](./arranque-auditor-v1-87-beta-2026-09-02.md).  
**No** declarar PASS hasta respuesta del auditor. Guardar respuesta como `respuesta-auditor-v187-…` cuando exista.

## 4. Cadena tips CI GREEN recientes

```text
v1.83-beta → dc596ee5 · run 33657045026
v1.84-beta → 504aa19d · run 33659480690
v1.85-beta → 665242a3 · run 33663836923
v1.86-beta → baaa7034 · run 33686297402
v1.87-beta → 646b97ac · run 33689747400
```
