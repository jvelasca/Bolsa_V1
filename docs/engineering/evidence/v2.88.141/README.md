# Evidencia `v2.88.141-beta` — SELLO CORRECTOR: el Ruff del CI del sello `.140` (hueco de PARIDAD local↔CI) + scripts de paridad

> **Bump:** `2.11.140-beta` → **`2.11.141-beta`** (`package.json` + `meta.bump` del CLI OOS `v2_87`, de los 9 CLIs `v2_89`…`v2_97`, del certificador `v2_98`, del CLI `v2_99` y de `v2_100` — **13 scripts** en [`apps/api-python/scripts`](../../../../apps/api-python/scripts/); guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) **2 passed**).
>
> **Naturaleza:** incremento **de pruebas + infra de desarrollo + documentación** — **no** toca el motor de decisión, ni umbrales, ni el contrato HTTP, ni el esquema, ni el vigía de la ventana: **`Δ motor = 0`** · **`Δ decisión = 0`** · **`Δ contrato HTTP = 0`** (`contract:check` **OK**) · **SIN migración** (head `055_dia_d_identity_nullable`). Tag **unsigned**.
>
> **Base:** `v2.88.140-beta` (commit del tag `248d0257`).

**Qué es este sello.** El sello `.140` (vigilancia diaria de la ventana PAPER) quedó **ROJO** en CI: el job
`python (ruff/imports/mypy/pytest offline)` de su `Release tag CI` murió en el paso **Ruff** y **ni
siquiera llegó** a import-linter/mypy/pytest. Este sello **corrige la causa raíz** y, sobre todo, **cierra
el hueco estructural** que la hizo posible. **No** cambia comportamiento del vigía ni de la ventana.

---

## 1. Causa raíz (medida, no interpretada)

### 1.1 El defecto

- **Síntoma.** Run **38939275316** (`Release tag CI` de `v2.88.140-beta`), job `python` (ID
  `117102516091`): `X Ruff in 14s`; el resto de jobs verdes (`a7-gate`, `shared` —gate `window:freeze`
  incluido—, `dr-verify`, `frontend`, `decision-spine`, `playwright` ×3, `replay-repro`,
  `lifecycle-pg`). El mismo contenido en `main` dejó **`Python CI` rojo** (run **38939270481**, 1m1s;
  duplicado del tag **38939275569**).
- **Diagnóstico.** `I001 [*] Import block is un-sorted or un-formatted` en
  `apps/api-python/tests/test_window_day_watch.py:7`: el bloque de imports ponía
  `from bolsa_infrastructure.config import get_settings` **antes** del bloque `from bolsa_api...`, y el
  `known-first-party` del [`pyproject.toml`](../../../../pyproject.toml) de la **raíz** exige el orden
  contrario.
- **Causa raíz (del proceso, no del código).** El fix del sello `.140` se verificó con
  `python -m ruff check --fix` **ejecutado dentro de `apps/api-python` y SIN `--config pyproject.toml`**,
  mientras el CI ejecuta, desde la **RAÍZ**:
  `uv run ruff check packages/py apps/api-python --config pyproject.toml`. **Mismo código, dos
  verdades**: el lint local no era el lint del CI. Sólo el flag/config de la raíz fija el orden.

### 1.2 Cierre ESTRUCTURAL del hueco (lo importante de este sello)

No bastaba con arreglar el import: había que **quitar la posibilidad de repetirlo**. Se añaden en
[`package.json`](../../../../package.json) los **comandos de paridad**, copiados **literalmente** de los
pasos del CI:

| Comando de casa | Paso del CI que replica | Definición |
| --- | --- | --- |
| `pnpm lint:py` | `Ruff` ([`python-ci.yml:36`](../../../../.github/workflows/python-ci.yml), [`release-tag-ci.yml:645`](../../../../.github/workflows/release-tag-ci.yml)) | `uv run ruff check packages/py apps/api-python --config pyproject.toml` |
| `pnpm lint:py:fix` | ídem, con `--fix` | el mismo comando + `--fix` |
| `pnpm imports:py` | `Import-linter` (`python-ci.yml:41`, `release-tag-ci.yml:648`) | `uv run lint-imports --config packages/py/.importlinter` |
| `pnpm types:py` | `Mypy` (`python-ci.yml:48`, `release-tag-ci.yml:652`) | `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent` |

**Falsable:** ejecutar `pnpm lint:py` en un árbol con el defecto del `.140` lo habría cazado **antes** de
publicar. El comando de casa **es** el comando del CI.

### 1.3 El fix

`uv run ruff check packages/py apps/api-python --config pyproject.toml --fix` ⇒ mueve **una línea** de
import (bloque `bolsa_infrastructure` después del bloque `bolsa_api`). Archivo:
[`test_window_day_watch.py`](../../../../apps/api-python/tests/test_window_day_watch.py). **No** hay
cambio de comportamiento: es orden de imports.

---

## 2. Verificación (medida) — los mismos comandos del CI

| Compuerta | Resultado |
| --- | --- |
| `pnpm lint:py` (Ruff, **config de la raíz**) | **`All checks passed!`** |
| `pnpm imports:py` (import-linter) | **`Contracts: 4 kept, 0 broken.`** (680 ficheros, 3750 dependencias) |
| `pnpm types:py` (mypy) | **`Success: no issues found in 557 source files`** |
| `pytest test_dia_d_bump_guard.py test_window_day_watch.py test_scheduler_worker.py` | **24 passed** (guardián `2.11.141-beta` **2 passed**) |
| `pnpm window:test` | **28 passed / 0 failed** |
| `pnpm window:freeze` | **OK** tras el re-anclaje — `apps` `e151cd43` (**movido**: el árbol pinado de `apps/` **incluye `apps/api-python/tests`**, no sólo `src`) / `packages` `e96a12b8` (**idéntico** al `.140`) |
| `pnpm window:status` | `medidos=0 · veto=3 · duros=0` ⇒ gate **`NO_MEDIDO`** |
| Sonda del vigía contra el ledger real (read-only) | `2026-10-16 20:01` ⇒ `VETO/info` (no alerta); día ausente ⇒ `MISSED/alert`; sábado ⇒ `NON_MARKET_DAY` |

### 2.1 Rastro de la caída corregida (trazabilidad)

| Run | Workflow | Ref | Resultado |
| --- | --- | --- | --- |
| [38939275316](https://github.com/jvelasca/Bolsa_V1/actions/runs/38939275316) | Release tag CI | `v2.88.140-beta` | **failure** — job `python` `X Ruff`, 14s (resto de jobs verde) |
| [38939275569](https://github.com/jvelasca/Bolsa_V1/actions/runs/38939275569) | Python CI | `v2.88.140-beta` | **failure** (1m11s) |
| [38939270481](https://github.com/jvelasca/Bolsa_V1/actions/runs/38939270481) | Python CI | `main` | **failure** (1m1s) |

---

## 3. Límites declarados (sin fabricar)

- El tag `v2.88.140-beta` sigue **publicado y ROJO**: un tag publicado **no se mueve** (convención de la
  casa); la corrección viaja como **sello nuevo** (`v2.88.141-beta`), igual que `v2.88.139-beta` fue el
  sello corrector del bloqueador de la ventana.
- Este sello **no** revive la ventana PAPER: sigue **`0/4 días`, `0/2 regímenes`, `0/32 ciclos` ⇒
  `INCONCLUSIVE`** (días `20261014/15/16` = `NO_MEDIDO_REGIMEN`, veto **`BEAR_TREND`**). Falta
  **OPERACIÓN**, no software. **No demuestra rentabilidad.**
- La **vigilancia diaria** (lo que pedía el propietario) **no cambia**: el vigía
  [`window_day_watch_worker`](../../../../apps/api-python/src/bolsa_api/background/window_day_watch_worker.py)
  sigue **ON por defecto** (`WINDOW_DAY_WATCH_ENABLED`, hora `20:00` Europe/Madrid) y la cadencia diaria
  sigue **instalada** (`BolsaV1_WindowForward`, próxima `17/10/2026 18:00:00`). Su dependencia sigue
  declarada: **si el API/crons está caído a la hora del vigía, ese día no avisa**.
- `Δ contrato HTTP = 0` (sin endpoint nuevo); sin migración; tag **unsigned**.

---

## 4. Publicación del sello

El gate `window:freeze` del job `shared` es **fail-closed** (compara los dos *tree hashes* del pin con
`HEAD`). **Medido — y corrige una suposición previa de este mismo documento:** el sello `.141` **sí
mueve** `appsHash` (`d38dc7ae…` → **`e151cd43…`**) porque el árbol pinado de `apps/` **incluye
`apps/api-python/tests`** (no sólo `src`): **tocar un test mueve el pin**. `packagesHash` queda
**idéntico** (`e96a12b8…`). Por eso `window:pin` **re-ancla** el pin al árbol del sello y el tag
`v2.88.141-beta` (**anotado, unsigned**) se crea sobre el commit del **re-anclaje**, **no** sobre el del
sello de contenido (mismo patrón que `.139` y `.140`). Como la ventana sigue con **0 días `MEDIDO`**,
re-anclar **no** invalida ningún día medido.

### 4.1 Cita POST-TAG — CI del sello

_Pendiente de la corrida del `Release tag CI` de `v2.88.141-beta` (se citará aquí el run y la tabla de
jobs al completarse)._
