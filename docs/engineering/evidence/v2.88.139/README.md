# Evidencia `v2.88.139-beta` — SELLO CORRECTOR: causa raíz del bloqueador de la ventana PAPER + login hermético en `test_auth` + instrumentos de operación

> **Bump:** `2.11.138-beta` → **`2.11.139-beta`** (`package.json` + `meta.bump` del CLI OOS `v2_87`, de los 9 CLIs `v2_89`…`v2_97`, del certificador `v2_98`, del CLI `v2_99` y de `v2_100` — **13 scripts** en [`apps/api-python/scripts`](../../../../apps/api-python/scripts/); guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) **2 passed**).
>
> **Naturaleza:** sello **corrector** — incremento de **pruebas + operación + documentación**; **no** toca el motor de decisión, umbrales, contrato HTTP ni esquema. · **`Δ motor = 0`** · **`Δ decisión = 0`** · **`Δ contrato HTTP = 0`** (`contract:check` **OK**; sin cambio en `apps/api-python/src` ni `packages/py`) · **SIN migración** (head `055_dia_d_identity_nullable`). Tag **unsigned**.
>
> **Base:** `v2.88.138-beta` (commit del tag `f79484d1`).

---

## 1. Qué cierra (y qué NO)

Cierra la **CAUSA RAÍZ** del bloqueador operativo que hizo desaparecer la cuenta de la ventana PAPER
(dos veces), y hermética el login de los tests. **NO** certifica la ventana: ésta sigue
`0/4 · 0/2 · 0/32` ⇒ `INCONCLUSIVE` (falta **MERCADO/OPERACIÓN**, no software).

### 1.1 Purga de residuos de tests — la cuenta de la ventana ya NO se borra

- **Defecto.** [`apps/api-python/tests/conftest.py`](../../../../apps/api-python/tests/conftest.py)
  purgaba, antes y después de cada sesión `pytest`, **toda** cuenta con
  `id <> 'default-account-seed'` (fixture autouse `_cleanup_residuals_around_session` →
  `purge_all_residuals()`). Como ADR-046 exige que la cuenta de la ventana
  (`1484e253d2d54645945a6b1d7`) sobreviva **≥4 días de CALENDARIO**, **cualquier `pytest` local**
  sobre la BD compartida `bolsa_v1` la devolvía a `0/4`.
- **Prueba controlada (falsable).** Con un testigo `SENTINEL-CONTROL` sembrado, una sesión de dos
  tests inertes lo **borraba**; con el fix, **sobrevive**.
- **Fix (fail-safe, no fail-open).** `PROTECTED_ACCOUNT_IDS` = **demo + cuenta de la ventana**, con el
  id leído de la **FUENTE ÚNICA** JS (`WINDOW_CONFIG.account` en
  [`scripts/lib/window-forward.mjs`](../../../../scripts/lib/window-forward.mjs)), **sin** literal
  duplicado. La regla vive en `residual_targets` (usada por `purge_accounts` y
  `purge_all_residuals`) y queda fijada por el tripwire
  [`test_window_account_purge_guard.py`](../../../../apps/api-python/tests/test_window_account_purge_guard.py).
- **Segundo destructor blindado.** [`scripts/ops/cleanup_residual_accounts.py`](../../../../scripts/ops/cleanup_residual_accounts.py)
  protegía sólo la demo; ahora protege también la ventana, **fail-closed** si no resuelve el id.
- **Instrumento de re-siembra.** [`scripts/ops/seed_window_account_fixed_id.py`](../../../../scripts/ops/seed_window_account_fixed_id.py)
  (dry-run por defecto; crea por el camino canónico y re-etiqueta el id reparentando las FK leídas de
  `information_schema`).

### 1.2 Login `401` en `test_auth` — hermético

- **Causa raíz.** `ensure_bootstrap_user` es **one-shot** (`count_users() > 0 → return`) y la tabla
  `users` **persiste entre corridas**; la secuencia «un test borra **todos** los usuarios → otro test
  re-siembra `app` con **otro** `APP_PASSWORD` (goldens de lifecycle)» deja al usuario `app` con un
  password **ajeno**, y el seed ya **no** re-siembra.
- **Prueba controlada (falsable).** Con el hash de `app` fijado a un password ajeno, el test **aislado**
  falla con `401`; con el hash correcto, pasa.
- **Fix (test-only).** Fixture `hermetic_bootstrap_user` (**upsert** del hash): crea `app` si falta; si
  existe con hash ajeno o `disabled_at`, lo repara. **No** se toca la semántica de producción
  (`ensure_bootstrap_user` sigue one-shot: nunca rota el password real).

### 1.3 Instrumentos de operación + guardián de bump

- NUEVO [`scripts/window-certify.mjs`](../../../../scripts/window-certify.mjs) (`pnpm window:certify`;
  **freeze-neutral** — vive en `scripts/`, no mueve el árbol — envuelve `v2_98`) + alias `contract:check`.
- `test_dia_d_bump_guard` incorpora `v2_87` (hueco de cobertura del sello `.138`), declarando el matiz
  del `bump` **congelado** del replay (`2.11.0-beta`) en `test_v2_87_frozen_replay_bump_stays_pinned`.

---

## 2. Verificación (medida)

| Compuerta | Resultado |
| --- | --- |
| `pytest apps/api-python/tests` (suite completa) | **1191 passed / 0 failed** (antes `1188 / 3`) |
| `ruff check packages/py apps/api-python --config pyproject.toml` | **`All checks passed!`** |
| `test_dia_d_bump_guard` | **2 passed** (`2.11.139-beta`) |
| `pnpm run window:freeze` | **OK** |
| `pnpm run window:status` | `medidos=0 · veto=3 · duros=0` ⇒ gate **`NO_MEDIDO`** |
| `pnpm run window:certify` (v2_98) | `0/4 · 0/2 · 0/32` ⇒ **`INCONCLUSIVE`** |
| Cuenta de la ventana tras la suite | `1484e253…` = `PAPER-VENTANA-a9c515` **`active`** (sobrevive) |

**Los 3 fallos previos** se documentan y cierran en el dictamen §7.3: dos de `test_auth` por la causa
raíz §1.2, y el de caos `test_c3a` por un **servidor dev vivo** cuyo worker consumía las filas
`UNKNOWN` del outbox (la suite exige **acceso exclusivo** a la BD; con el stack dev parado, el test
**pasa** y su aserción ahora declara la causa).

---

## 3. Límites declarados (sin fabricar)

- La **ventana PAPER real** (ADR-046) sigue **`0/4 días`, `0/2 regímenes`, `0/32 ciclos`** ⇒
  **`INCONCLUSIVE`**; días `20261014/15/16` = `NO_MEDIDO_REGIMEN` por veto **`BEAR_TREND`** (LONG
  vetadas). Falta **OPERACIÓN** (días de mercado con LONG permitida), **no** software.
- El fix de auth es **test-only**; **no** cambia comportamiento de producción.
- `Δ motor = 0`; `Δ decisión = 0`; sin migración; tag **unsigned**; **no demuestra rentabilidad**.

---

## 4. Publicación del sello

El gate `window:freeze` del job `shared` de
[`release-tag-ci.yml`](../../../../.github/workflows/release-tag-ci.yml) es **fail-closed**: compara
los dos *tree hashes* del pin con `HEAD`. Por eso `window:pin` re-ancla el pin al árbol del sello y el
tag `v2.88.139-beta` (**anotado, unsigned**, objeto `f374f771`) se crea sobre el commit **cuyo pin
casa con su árbol** — el commit del re-anclaje **`0739daae`** (sello de **contenido** `fddd7a85`),
**no** sobre el commit del sello. Como la ventana seguía con **0 días `MEDIDO`**, re-anclar **no**
invalidó nada.

### 4.1 Cita POST-TAG — CI del sello

**`Release tag CI` [run `38933157663`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38933157663)
— VERDE** (`2026-10-16T16:35:32Z` → `16:49:27Z`, ~**13m55s**; **13 jobs `success` + `certify`
`success`**; `playwright (integrated E2E, opt-in)` `skipped`, declarado):

| Job | Resultado |
| --- | --- |
| `shared (build/typecheck/test)` | **`success`** — gate `window:freeze` **`freeze OK (0739daae)`** |
| `replay-repro (regenera el artefacto del sello desde el fixture)` | **`success`** — **REPRODUCIDO** `sha256 1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7` (3 340 728 bytes), **idéntico** a `.136`/`.137`/`.138` ⇒ **`Δ decisión = 0` medido** |
| `python (ruff/imports/mypy/pytest offline)` | **`success`** — incluye el guardián de bump (`2.11.139-beta`, **13** scripts) |
| `lifecycle-pg`, `a7-gate`, `dr-verify`, `decision-spine`, `frontend`, `playwright (mock E2E)`, `playwright (integrated AUTO S5)`, `playwright (integrated axe)`, `security (gitleaks)` | **`success`** |
| `certify (aggregate + artifact)` | **`success`** |

`Python CI` [run `38933157648`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38933157648) ·
`Frontend CI` [run `38933157675`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38933157675) ·
`Fase 2 scientific` [run `38933157627`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38933157627) ·
`Optimize lab` [run `38933157634`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38933157634) —
**VERDES** sobre el tag.

**Nota de intermitencia (declarada, no nueva).** `S5-04` (`playwright integrated AUTO S5`) mantiene la
intermitencia de arranque en frío ya **ABIERTA** en `.137`/`.138`; en este run el job salió **verde**
en el reintento, **sin** tocar `timeouts`/`retries`/`ADR-046`.
