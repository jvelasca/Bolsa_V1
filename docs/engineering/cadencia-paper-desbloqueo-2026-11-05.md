# Cadencia PAPER — desbloqueo del 2026-11-05 (4 causas, 3 cerradas)

- **Fecha:** 2026-11-05
- **Rama:** `fix/059-060-proveedores` @ `3e092888` (verde en CI)
- **Naturaleza:** operación + instrumento. **`Δ motor = 0`**, **`Δ decisión = 0`**, **sin migración**.
  El único fichero de producto que cambia es el **pin** (`scripts/lib/window-forward.mjs`), que vive
  fuera del freeze. **AUTO sigue OFF** y **PAPER sigue INCONCLUSIVE**.

## 1. El síntoma

El ledger de la ventana tenía **8 sesiones consecutivas sin un día `MEDIDO`** desde el
`2026-10-22`:

| día | estado | motivo |
| --- | --- | --- |
| 2026-10-26 | `HARD_ERROR` | `API_NOT_READY` |
| 2026-10-27 | `HARD_ERROR` | `POSTGRES_DOWN` |
| 2026-10-28, 10-29 | `HARD_ERROR` | `PREFLIGHT_ERROR` (`preflight_sin_payload`) |
| 2026-10-30 | `MISSED` | sin run |
| 2026-11-02, 11-04 | `HARD_ERROR` | `TREE_MOVED` |
| 2026-11-03 | `HARD_ERROR` | `POSTGRES_DOWN` |

## 2. Las cuatro causas (medidas, no inferidas)

### C-1 · `TREE_MOVED` determinista — el runner corría desde el árbol de desarrollo · CERRADA

La tarea `BolsaV1_WindowForward` ejecutaba `window-forward-task.cmd`, que hacía
`cd /d "…\Bolsa_V1"`: la **raíz de desarrollo**, que avanza con las ramas. `run-day` compara
`HEAD:apps`/`HEAD:packages` con el pin y aborta fail-closed. Resultado: el día siguiente a
cualquier commit terminaba en `TREE_MOVED` **por construcción**, no por deriva.

**Arreglo:** el `.cmd` entra en un worktree clavado en el árbol del pin
(`.cursor/worktrees/window-seal-183`) y lanza el runner desde ahí. `node scripts/window-pin.mjs
--check` desde el worktree: `freeze OK`; desde la raíz de desarrollo: `TREE_MOVED`.

### C-2 · el venv compartido medía el árbol equivocado · CERRADA

Reutilizar el `.venv` del repo (`UV_PROJECT_ENVIRONMENT`) pasaba el freeze y ejecutaba **el código de
la rama**: los `.pth` editables apuntan a `Bolsa_V1\packages\…\src`. Medido en el traceback del
primer intento (rutas del árbol de desarrollo con el manifiesto declarando el sello).

**Arreglo:** el worktree tiene **su propio `.venv`** (`uv sync --frozen`) y el `.cmd` ya **no**
sobreescribe `UV_PROJECT_ENVIRONMENT`. Verificado: cada `.pth` apunta a su árbol.

### C-3 · la cuenta de la ventana no existía · CERRADA

El forward abortaba con `ValueError: Cuenta no encontrada o inactiva` para
`1484e253d2d54645945a6b1d7`. En `investment_accounts` solo había `default-account-seed`, creada el
**2026-10-27**: la base se recreó después del último día medido y la cuenta de la ventana
desapareció con su material.

**Arreglo:** `scripts/ops/seed_window_account_fixed_id.py --apply` (instrumento del propio repo,
id fijo de `WINDOW_CONFIG`) ⇒ `PAPER-VENTANA-a9c515`, `simulated`, `active`; y
`apps/api-python/scripts/ops_seed_window_pair.py --account-id … --version-a v283-window-a
--version-b v283-window-b` ⇒ par A/B sembrado. **No se recupera material**: la cuenta nace sin
fills, así que la serie de la ventana **reinicia** su conteo.

### C-4 · el árbol sellado está por detrás del esquema · **ABIERTA (bloquea medir)**

`ensure_migrated` aborta con `CommandError: Can't locate revision identified by
'065_auto_engine_intent'`. La base está en **065** y el sello `.183` solo conoce hasta **062**:

| migración | entró en | fecha |
| --- | --- | --- |
| `063_auto_engine_lease` | `ec3f9bab` | 2026-11-04 |
| `064_strategy_account_scope` | `16aac962` | 2026-11-05 |
| `065_auto_engine_intent` | `d5b8868c` | 2026-11-05 |

No existe **ningún** tag con la 065 (`v2.88.184…` no existe). Es decir: la ventana llevaba dos días
sin poder medir por una razón más profunda que el `TREE_MOVED` — **el árbol que mide no puede hablar
con la base**.

**Arreglo aplicado (parcial, declarado):** re-anclaje del pin a `3e092888` (punta verde de la rama,
con 065) como **pin operativo**, con `node scripts/window-pin.mjs --write`. Desde ese árbol el
preflight sale limpio: `eje HIGH_VOLATILITY · LONG PERMITIDAS · 57/80 símbolos operables (exit 0)`.

**Lo que queda abierto:** el pin apunta a la **punta de una rama**, no a un sello. Cualquier commit
nuevo en `apps/`/`packages/` lo deja obsoleto y el día siguiente vuelve a `TREE_MOVED`. El cierre
definitivo es **un sello .184** sobre un árbol con 063–066, y su `window:pin --write` posterior. Se
pospone deliberadamente hasta que #96 y #97 estén fusionados: sellar antes de fusionarlos produciría
un sello que caduca en días.

## 3. Estado de la ventana

- La cuenta de la ventana y su par A/B existen de nuevo; el ledger **no** se ha duplicado
  (`operability_runs` es una *junction* al directorio del repo de desarrollo).
- La fila `2026-11-05` quedó escrita como `HARD_ERROR · PREFLIGHT_ERROR` (causa C-4) y se repite con
  `--force` una vez re-anclado el pin.
- **0 ciclos medibles** siguen siendo el bloqueo de fondo: el gate pide `4 días / 2 episodios /
  32 ciclos` y la serie arranca de cero tras la re-siembra.

## 4. Invariantes

- `Δ motor = 0`, `Δ decisión = 0`, sin migración, sin tocar umbrales.
- **AUTO OFF** · **PAPER INCONCLUSIVE**.
- Un hueco se declara: no se rellena con 0 ni se cuenta como medido.
- El orden correcto es **fusionar → sellar → re-anclar → medir**; medir antes de fusionar gasta días
  que el siguiente sello convierte en `STALE`.

## 5. Ejecución del 2026-11-05 (en curso al cerrar esta nota)

`run-day --force` desde el worktree pinneado (`d8a5d0f9`, freeze OK), arrancado a las **19:39**.

| medida | valor |
| --- | --- |
| preflight | `HIGH_VOLATILITY` · LONG permitidas · **57/80** operables · `exit 0` |
| cadencia | **~65 s/tick** (60 s de espera + trabajo) |
| material durable | **13 fills**, **3 posiciones**, **4 reservas**, **1 intención de salida** |
| journal | 10 699 → **10 740** entradas en una hora |
| gate | `cycles=0/0` · `verdict=BLOCKED` (bloqueador `no closed cycles`) |

`BLOCKED` **no** es un fallo: con fills y `closedCycles = 0` el bloqueador es que ninguna posición ha
cerrado todavía, y un ciclo solo nace al salir la posición. En el día 1 de una serie re-sembrada es
el estado esperado; la ventana se mide en **días**, no en ticks.

**Parón observado:** entre las **19:49 y las 20:40** el contador de ticks no avanzó (`12`) y se
recuperó solo. Es el *modern standby* ya documentado (`506`/`507`); la corrida **se congela sin
fallar**, así que un hueco de horas en `forward.err.txt` no es un error del runner.

**Qué mirar al día siguiente:** que el manifiesto de `operability_runs/window-runs/20261105/` esté
escrito con su `gate` y su `windowProvenance` (sha256 del `window.json`), y que la fila del ledger
haya pasado de `HARD_ERROR · PREFLIGHT_ERROR` a `MEDIDO` o `NO_MEDIDO_*`. Mientras el proceso siga
vivo, la fila vieja es **histórica**, no el resultado de esta corrida.

