# Entrega — `v2.88.106-beta` · **Integridad de AUTO: ciclo de vida E2E, política de P&L y etiquetas** (**`Δ motor = 0`** · **`Δ decisión = 0`** · contrato **sin cambio** · sin migración)

> **Fecha:** 2026-10-10 · **Producto:** `V2.88.106-beta` · **Package:** `2.11.106-beta` · **Alembic head:** `052_top3_opportunities` (**sin migración**).
> **Base:** `v2.88.105-beta` (tag anotado objeto `0ba42c1a` → commit `c28b49f1`; `Release tag CI` [`38074199301`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38074199301) **VERDE**).
> **Unidad de esta entrega:** cerrar los hallazgos **`H2`**, **`H3`** y **`H4`** de la auditoría externa de `v2.88.105-beta`: (1) el **ciclo de vida** del E2E integrado `S5` no puede dejar residuo ni destruir datos previos; (2) el `S5` integrado se **corre de verdad** en el CI del tag; (3) **política explícita** del P&L realizado en la lista de cuentas (`detail-only`); y (4) **etiquetas económicas inequívocas** en AUTO. **`H1`** (identidad **exacta** de la estrategia ejecutada por ciclo) se declara como la **versión dedicada siguiente**.
> **Regla del hueco:** una afirmación que no se puede sostener se declara **abierta** con su remediación, **nunca** se silencia. Un dato ausente se rotula «Sin dato todavía»; **jamás** se rellena con `0` ni con verde; y **carga ≠ hueco**. La separación SIM/dinero real se conserva.
> **`Δ motor = 0` y `Δ decisión = 0`.** El diff **no** toca umbrales, reparto de capital, `TOP_N`/régimen/selección/protección ni ninguna superficie de decisión/ejecución. El único cambio fuera de `apps/web`/config/docs es una **docstring** en `packages/py/application` que **declara** una política ya vigente y una **nota** en el DTO; **no** cambia cálculo. **Contrato HTTP sin cambio** (`totalRealizedPnl` ya era nullable; sin `contract:gen`).
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.106/README.md`](./evidence/v2.88.106/README.md).
> **Cita POST-TAG:** pendiente; se añadirá tras sellar el tag `v2.88.106-beta` y verificar el `Release tag CI` (que ahora incluye el job **obligatorio** `playwright-integrated-auto-s5`).

---

## 1. Qué se entrega (y qué NO)

**Se entrega**, en un único commit:

1. **`H2` Ciclo de vida seguro del E2E integrado `S5`.** (a) registro de recursos **desde el primer momento** (la cuenta efímera justo tras su `POST`), de modo que una petición intermedia que falle **no** impide la limpieza; (b) **snapshot/restore VERIFICADO** del TOP de Finalistas (tabla **global por instrumento**; el CLI de seed también lo escribe); (c) limpieza que corre **siempre**, con `close` + `DELETE` de la cuenta y **aserción de 0 ciclos residuales**; (d) gate **`E2E_S5_REQUIRED=1`** que convierte una precondición ausente en **FALLO**, no en `skipped`.
2. **`H2` CI — `S5` integrado obligatorio.** Nuevo job `playwright-integrated-auto-s5` en `release-tag-ci.yml` (PostgreSQL + API reales, `E2E_S5_REQUIRED=1`, guardia anti-skip), **añadido a `certify.needs`** y al summary del tag.
3. **`H3` Política `detail-only` del P&L realizado.** `ListAccountSummaries` **declara** que la lista deja `total_realized_pnl = None` deliberadamente (con motivo de coste **O(N)** y ausencia de consumidor); nota en `AccountSummaryDto.total_realized_pnl`; test que **fija la asimetría** (lista `None`, detalle con valor).
4. **`H4` Etiquetas económicas inequívocas.** «Resultado de posiciones abiertas» (no realizado) · «Resultado de operaciones cerradas» (realizado) · «Efectivo simulado»; la tarjeta de operación **prefija** el P&L con su rótulo; el valor lleva el calificador de cuenta simulada.

**NO se entrega**, y se declara:

- **NO** se toca el **motor de decisión/ejecución**, el reparto, los umbrales, ni `TOP_N`/régimen/selección/protección (`Δ decisión = 0`).
- **NO** hay migración (head Alembic intacto `052_top3_opportunities`) ni cambio de contrato HTTP.
- **NO** se cierra **`H1`**: la identidad **exacta** de la estrategia ejecutada por ciclo sigue siendo **heurística textual** (exige motor + contrato; versión dedicada siguiente).
- **NO** se cierran la validación por valor fuera de muestra ni las deudas PARKED `F2-1`/`F2-2`.

---

## 2. Cambios verificables (todo con gate)

| Hallazgo | Fichero(s) | Qué hace |
| --- | --- | --- |
| `H2` | `apps/web/e2e/gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts` | Registro progresivo de recursos; snapshot/restore verificado del TOP; `close` + `DELETE`; assert sin residuo; gate `E2E_S5_REQUIRED`. |
| `H2` (CI) | `.github/workflows/release-tag-ci.yml` | Job `playwright-integrated-auto-s5` (PG + API reales, `E2E_S5_REQUIRED=1`, anti-skip) en `certify.needs`. |
| `H3` | `packages/py/application/src/bolsa_application/accounts/summary.py`, `apps/api-python/src/bolsa_api/schemas/accounts.py`, `packages/py/application/tests/test_list_account_summaries.py` | Docstring/nota de la política `detail-only`; test que fija `total_realized_pnl is None` en la lista. |
| `H4` | `apps/web/src/features/auto/auto-account-figures.ts`, `auto-operation-card.ts` (+ tests) | Rótulos desambiguados; la tarjeta prefija el P&L con «Resultado de posiciones abiertas». |
| Bump | `package.json` + `apps/api-python/scripts/v2_89`…`v2_97` | `2.11.106-beta` + `meta.bump` (guardián `test_dia_d_bump_guard.py`). |

---

## 3. Medición

- **Frontend:** `tsc --noEmit` **OK**; `eslint src` **0 errores** (23 avisos `react-hooks/exhaustive-deps` preexistentes); `vitest run` **294 ficheros / 2075 tests verdes**; `build` **OK**; `contract:check` **OK**.
- **Python:** `ruff` **All checks passed**; `lint-imports` **4 kept, 0 broken**; `mypy` **544 source files, no issues**; `pytest domain+application` **2708 passed** (incluye el guardián de bump).
- **E2E `S5` integrado:** **3/3 verdes** contra **stack real** (FastAPI + PostgreSQL) en modo **`E2E_S5_REQUIRED=1`**, con teardown **completo** (TOP global restaurado y verificado, **0 ciclos residuales**, cuenta efímera cerrada y borrada; **0 cuentas `e2e-*`** al terminar). Hermano **mock** **2/2**.
- **Bump guard:** `pytest apps/api-python/tests/test_dia_d_bump_guard.py` **1 passed** (`2.11.106-beta`).

---

## 4. Hallazgos y estado tras esta entrega

- **`H2` ciclo de vida del E2E — cerrado.** El journey registra recursos desde el primer momento, restaura y **verifica** el TOP global, limpia siempre y **asserta** no-residuo.
- **`H2` `S5` en CI — cerrado.** El `S5` integrado pasa a ser un job **obligatorio** del tag (fail-if-skipped), ya no opt-in.
- **`H3` política del P&L — declarada.** `detail-only` explícita + tests que fijan la asimetría; sin coste **O(N)** en la lista.
- **`H4` etiquetas — cerrado.** Rótulos abierto/cerrado inequívocos; se conserva la separación SIM/real.
- **`H1` (identidad exacta de la estrategia ejecutada) — abierto (declarado).** Versión dedicada siguiente (motor + contrato).

---

## 5. Gates

| Gate | Resultado (local) |
| --- | --- |
| `pnpm --filter @bolsa/web run typecheck` | **OK** |
| `pnpm --filter @bolsa/web run lint` | **0 errores** (23 avisos preexistentes) |
| `pnpm --filter @bolsa/web run test` | **294 ficheros / 2075 passed** |
| `pnpm --filter @bolsa/web run build` | **OK** |
| `pnpm --filter @bolsa/web run contract:check` | **OK** |
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed** |
| `uv run lint-imports --config packages/py/.importlinter` | **4 kept, 0 broken** |
| `uv run mypy … --follow-imports=silent` | **544 source files, no issues** |
| `uv run pytest packages/py/domain packages/py/application …/test_dia_d_bump_guard.py -q` | **2708 passed** |
| E2E `S5` integrado (`E2E_S5_REQUIRED=1`) / mock | **3/3** / **2/2** |

---

## 6. Sello

- **Producto:** `V2.88.106-beta`. **Package:** `2.11.106-beta`. **Sin migración** (Alembic head `052_top3_opportunities`). **Contrato HTTP sin cambio.** **`Δ motor = 0` · `Δ decisión = 0`.**
- **Añadidos:** `docs/engineering/evidence/v2.88.106/README.md`, este documento.
- **Modificados:** `.github/workflows/release-tag-ci.yml`; `apps/web/e2e/gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts`; `apps/web/src/features/auto/{auto-account-figures.ts,auto-account-figures.test.ts,auto-operation-card.ts,auto-operation-card.test.ts}`; `packages/py/application/src/bolsa_application/accounts/summary.py`; `packages/py/application/tests/test_list_account_summaries.py`; `apps/api-python/src/bolsa_api/schemas/accounts.py`; `CHANGELOG.md`; `package.json` + `apps/api-python/scripts/v2_89`…`v2_97` (`meta.bump`).
- **Tag anotado `v2.88.106-beta`:** **pendiente de cita POST-TAG.** El `Release tag CI` ahora **incluye** el job obligatorio `playwright-integrated-auto-s5` (con `E2E_S5_REQUIRED=1` y guardia anti-skip), de forma que el puente AUTO → estrategia → `POST /api/backtests/run` queda certificado en cada push de tag. El tag se emite **unsigned**.
