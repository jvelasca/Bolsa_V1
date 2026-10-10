# Evidencia `v2.88.106-beta` — **Integridad de AUTO: ciclo de vida E2E, política de P&L y etiquetas** (UI + config + docstring · **`Δ motor = 0`** · **`Δ decisión = 0`** · contrato **sin cambio** · sin migración)

**Producto:** `V2.88.106-beta` · **Package:** `2.11.106-beta` · **AsOf:** 2026-10-10. **Sin migración** (Alembic head sigue `052_top3_opportunities`). Los 9 CLIs DÍA-D `v2_89`…`v2_97` sellan `2.11.106-beta` junto al `package.json` (guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py)).

> **Naturaleza (honesta).** Sello **sin código de motor**: el único cambio fuera de `apps/web`/**config/docs** es una **docstring** en `packages/py/application` (`ListAccountSummaries`) que **declara** una política ya vigente (`total_realized_pnl = None` en la lista) y una **nota** en el DTO; **no** cambia cálculo. `git diff --name-only -- packages/py/**` toca solo esa docstring + un test. **`Δ motor = 0`** y **`Δ decisión = 0`**. **Sin `contract:gen`** (el contrato HTTP no cambia: el campo ya era nullable).
> **Origen.** Auditoría externa de `v2.88.105-beta` con cuatro hallazgos (`H1`–`H4`). Esta versión cierra **`H2`**, **`H3`** y **`H4`** y corre el E2E integrado `S5` **de verdad** en el CI del tag. **`H1`** (identidad **exacta** de la estrategia ejecutada por ciclo) se declara como la **versión dedicada siguiente** (requiere motor + contrato).

**Base:** [`evidence/v2.88.105/README.md`](../v2.88.105/README.md) (cierre de auditoría AUTO `F1`–`F7`; puente `S5` probado con un ciclo AUTO durable pero **opt-in** en CI).

## 1. Cambios (por hallazgo)

| Hallazgo | Bloque | Qué demuestra | Implementación |
| --- | --- | --- | --- |
| `H2` | **Ciclo de vida seguro del E2E integrado `S5`** | El journey **deja de poder dejar residuo**: (1) cada recurso se **registra en cuanto existe** (la cuenta efímera justo tras su `POST`, antes de cualquier petición que pueda fallar), así el `afterAll` limpia aunque el seed falle a mitad; (2) el TOP de Finalistas es una tabla **GLOBAL por instrumento**: se **guarda** el TOP previo antes de tocarlo (el CLI de seed también hace `PUT`) y se **restaura + VERIFICA** al terminar (deja de ser «best-effort»); (3) la limpieza corre **siempre** (equivale a `finally`), termina con **`close` + `DELETE` de la cuenta** (el borrado exige la cuenta cerrada) y **asserta 0 ciclos residuales**; (4) gate **`E2E_S5_REQUIRED=1`**: una precondición ausente **FALLA**, no se `skip`ea; (5) el cierre+borrado **sondea y verifica** cada paso (lee el estado real de la cuenta, reintenta el cierre, adjunta el **cuerpo** del `DELETE` fallido junto al `status`/`type` observados) y **confirma** al final que la cuenta no sobrevive (un `400` con la cuenta ya borrada es OK, un residuo no). | [`gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts`](../../../../apps/web/e2e/gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts) |
| `H2` (CI) | **Job dedicado y siempre activo del `S5` integrado** | El `playwright-integrated` era **opt-in** (`workflow_dispatch`) y **no** estaba en `certify.needs`. Se añade `playwright-integrated-auto-s5`: servicio `postgres:16-alpine`, migración (`alembic upgrade head`), seed de instrumentos (`pnpm db:seed`), API real (`uvicorn` + health), Playwright Chromium y `pnpm exec playwright test gp-v288-s5` con `E2E_S5_REQUIRED=1` + **guardia anti-skip** (`if: always()` que falla si el log trae `skipped`). **Bloquea el tag** (está en `certify.needs` y en el summary). | [`.github/workflows/release-tag-ci.yml`](../../../../.github/workflows/release-tag-ci.yml) |
| `H3` | **Política declarada del P&L realizado: `detail-only`** | La lista `GET /accounts/summaries` **no** calcula el realizado y lo **declara**: `total_realized_pnl = None` de forma deliberada. Motivo: el realizado agregado exige recorrer **todo** el historial por cuenta (`collect_report_inputs` + FIFO/avg), la lista solo alimenta equity/posiciones y se refresca con `staleTime 30s`, y **ningún consumidor lee `totalRealizedPnl`** de la lista ⇒ calcularlo sería una regresión **O(N)** sin beneficio. La cifra realizada **solo** se publica en el detalle (`GET /accounts/{id}/summary`). Un test fija la **asimetría** (la lista `None`, el detalle sí calcula). | [`summary.py`](../../../../packages/py/application/src/bolsa_application/accounts/summary.py), [`accounts.py`](../../../../apps/api-python/src/bolsa_api/schemas/accounts.py), [`test_list_account_summaries.py`](../../../../packages/py/application/tests/test_list_account_summaries.py) |
| `H4` | **Etiquetas económicas inequívocas en AUTO** | Se desambigua el P&L: el **rótulo** dice **qué** es y el **valor** lleva la cifra con el calificador SIM (para no duplicar la frase): «Resultado de **posiciones abiertas**» (no realizado) · «Resultado de **operaciones cerradas**» (realizado) · «Efectivo simulado». La tarjeta de operación prefija el P&L con «Resultado de posiciones abiertas …» en vez de la frase-completa antigua. Se conserva «Sin dato todavía» y la mención a «cuenta simulada» (separación SIM/dinero real). | [`auto-account-figures.ts`](../../../../apps/web/src/features/auto/auto-account-figures.ts), [`auto-operation-card.ts`](../../../../apps/web/src/features/auto/auto-operation-card.ts) |
| Bump | — | `package.json` (`2.11.106-beta`) + `meta.bump` de `v2_89`…`v2_97`. | [`test_dia_d_bump_guard.py`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) |

## 2. Reglas que NO cambian

- **`Δ motor = 0` / `Δ decisión = 0`.** No se toca motor, umbrales, reparto, `TOP_N`/régimen/selección/protección. `H3` **no** cambia cálculo (solo declara la política vigente); `H4` es copy; `H2` es test/CI.
- **Sin migración.** Alembic head sigue `052_top3_opportunities`.
- **Contrato HTTP sin cambio.** `totalRealizedPnl` ya era nullable; no hay `contract:gen` (solo se documenta la asimetría lista/detalle).
- **`UNKNOWN ≠ 0` y carga ≠ hueco.** Un dato ausente se rotula «Sin dato todavía»; jamás se colapsa a `0`.
- **Separación SIM/real** y la mención «en la cuenta simulada»: intactas.
- **`H1` fuera de alcance (declarado).** La identidad **exacta** de la estrategia ejecutada por ciclo sigue siendo **heurística textual**; materializarla exige motor + contrato (versión dedicada siguiente).

## 3. Verificación (local)

- `pnpm --filter @bolsa/web run typecheck` (`tsc -b --noEmit`) → **OK**.
- `pnpm --filter @bolsa/web run lint` (`eslint src/`) → **0 errores** (23 avisos `react-hooks/exhaustive-deps` preexistentes).
- `pnpm --filter @bolsa/web run test` (`vitest run`) → **294 ficheros / 2075 tests verdes**.
- `pnpm --filter @bolsa/web run build` → **OK**.
- `pnpm --filter @bolsa/web run contract:check` → **OK**.
- `uv run ruff check packages/py apps/api-python --config pyproject.toml` → **All checks passed**.
- `uv run lint-imports --config packages/py/.importlinter` → **4 kept, 0 broken**.
- `uv run mypy … --follow-imports=silent` → **Success: no issues found in 544 source files**.
- `uv run pytest packages/py/domain packages/py/application …/test_dia_d_bump_guard.py -q` → **2708 passed**.
- **E2E `S5` integrado** (`gp-v288-s5-…-integrated.spec.ts`) con `E2E_INTEGRATION=1 E2E_ALLOW_DEV_DB=1 E2E_S5_REQUIRED=1` contra **stack real** (FastAPI :8000 + PostgreSQL): **3/3 passed**, con **teardown completo** (TOP global restaurado y verificado, **0 ciclos residuales**, cuenta efímera **cerrada y borrada**). Sin cuentas `e2e-*` residuales tras el run.
- **E2E `S5` mock** (`gp-e2e-s5-…-mock.spec.ts`) → **2/2 passed**.
- **`Release tag CI`** ahora ejecuta el `S5` integrado **obligatorio** (`playwright-integrated-auto-s5`), con `E2E_S5_REQUIRED=1` y guardia anti-skip; está en `certify.needs`.

## 3.b Verificación del sello en CI (tag `v2.88.106-beta`)

- `Release tag CI` del tag `v2.88.106-beta` → **GREEN**: 12 jobs verdes, incluido el nuevo `playwright (integrated AUTO S5)` (3 tests corridos, **guardia anti-skip OK**) y `certify` con `"status": "GREEN"` y `"playwright-integrated-auto-s5": "success"`. Artefacto `release-tag-ci-summary`.
- **Hallazgo del primer sello (honesto).** En esa corrida el job del `S5` necesitó **1 reintento**: el `afterAll` del primer intento falló con `DELETE /api/accounts/… falló (400)` — y el teardown original **se tragaba el cuerpo** de la respuesta, así que el motivo exacto del `400` no quedó en el log. Es una **carrera** en un gate que ahora **bloquea el tag**, no un fallo de producto: los 3 tests pasaron y el reintento dejó el job verde.
- **Corrección (mismo tag, re-anclado).** El teardown dejó de ser «ciego»: sondea el estado real (`GET /accounts/{id}`), verifica el cierre **antes** de borrar (con reintento), reintenta el borrado, adjunta **cuerpo + `status`/`type`** si falla, acepta el `400`/`404` cuando el sondeo confirma que la cuenta ya no existe y **asserta** el no-residuo al final. Re-verificado localmente con la versión endurecida: **3/3 passed** con `E2E_S5_REQUIRED=1` y **0 reintentos**, **0 cuentas `e2e-*` residuales**.
- **Tag `unsigned`.** El tag se re-ancló al commit de la corrección (misma versión).

## 4. Qué no cambia / deuda declarada

- **`H1`**: identidad exacta de la estrategia ejecutada (motor + contrato) — **versión dedicada siguiente**.
- **Validación por valor fuera de muestra** y deudas PARKED `F2-1`/`F2-2`: siguen abiertas.
- **Tag `unsigned`.**
