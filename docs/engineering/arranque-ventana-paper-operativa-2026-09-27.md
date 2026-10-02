# Arranque operativo de la ventana PAPER forward — semilla A/B y cuenta fija (2026-09-27)

> **AsOf:** 2026-09-27 · **Re-anclaje:** 2026-10-02 (ver §0) · **Naturaleza:** **operación** (no es una fase de motor) ·
> **Objeto:** dejar listo el entorno para la ventana PAPER **≥4 días** de `AUTO-MATERIAL-12`
> que persigue cerrar `P3-2`/`P3-3`. **No** se toca motor, gobernador, `TOP_N`, umbrales,
> allocation, pesos A/B ni migraciones (arranque original con head `046_fill_reference_mid`;
> head **hoy** `048_journal_entry_dedupe_key`).
> Ejecutado por el script [`ops_seed_window_pair.py`](../../apps/api-python/scripts/ops_seed_window_pair.py).

## 0. Re-anclaje al árbol congelado `v2.88.29-beta` (2026-10-02)

La ventana de `2026-09-28` (D1) se corrió sobre un árbol **anterior**; el head de migraciones
avanzó de `046_fill_reference_mid` a `048_journal_entry_dedupe_key`. Antes de reiniciar la
ventana, este documento se **re-pinnea** al árbol congelado del sello vigente:

| Dato | Valor (comprobable) |
|---|---|
| Sello / tag | **`v2.88.29-beta`** · commit `2b67a2fa` · package `2.11.29-beta` |
| Alembic head | **`048_journal_entry_dedupe_key`** (**sin** migración pendiente) |
| Árbol de **código** congelado | `git rev-parse "HEAD:apps"` = `25afb7282e11240c19c63f85f82273ea3b1440f4` · `git rev-parse "HEAD:packages"` = `ce0a38b7e6f5a9f102490e5774f859d7f83aac4a` |
| Identidad fija (sin cambios) | `$ACCOUNT` = `1484e253d2d54645945a6b1d7` · `$VERSION_A` = `v283-window-a` · `$VERSION_B` = `v283-window-b` · watch = **20** símbolos |
| Configuración de operación | `AUTO_ENGINE_SIM_REAL_PRICE=1` (deja de fabricar `100.0`) y `AUTO_OPERATIONAL_AUDIT=1` (hechos durables para el monitor). **Ningún** cambio de motor/`TOP_N`/régimen/umbrales/A-B. |

**Declaración:** el bloque §4.bis (D1 del `2026-09-28`) pertenece al árbol **previo** al re-anclaje
y **no** cuenta para esta ventana; la ventana se reanuda sobre el árbol congelado de arriba. Si
`apps`/`packages` vuelven a moverse durante D1..D4, la hoja se **repite** (mismo protocolo del
incidente declarado en §4.bis).

### 0.1 Verificación de identidad ejecutada (2026-10-02, read-only)

| Comprobación | Comando | Resultado |
|---|---|---|
| Árbol congelado vivo | `git rev-parse "HEAD:apps" "HEAD:packages"` | `25afb728…` / `ce0a38b7…` (**coinciden** con el sello) |
| Watch de 20 símbolos | `v2_76 … --preflight-only --watch-size 20` | `watch 20 símbolos` · `barras servidas 20` |
| Régimen de hoy | idem | `{'trend_down': 10, 'range': 5, 'trend_up': 5}` ⇒ agregado `trend_down` ⇒ **`BEAR_TREND`** ⇒ **entradas LONG VETADAS** (`exit 2`) |
| Versión B (`v283-window-b`) | `session.get(StrategyVersionRow, …)` | **existe** (`PAPER-WINDOW sma_crossover`) |
| Localizador de promoción | `strategy_promotions.instrument_id == $ACCOUNT` | **1 fila** (`promoted=true`, `shadow_validated=false`) |
| `EdgeReport` A/B | `count(*) where account_id == $ACCOUNT` | **2 filas** |
| Cuenta `$ACCOUNT` | `session.get(InvestmentAccountRow, $ACCOUNT)` | **NO EXISTÍA** (sólo `default-account-seed`); **re-sembrada** el 2026-10-02 con el **mismo id** fijo (ver §0.2) |

### 0.2 Re-siembra de la cuenta fija (2026-10-02, operación autorizada por el propietario)

La BD alcanzable había **perdido** la fila de `investment_accounts` de la ventana (sus `EdgeReport`
y la promoción sobrevivían). Para **no** inventar identidad ni romper la continuidad, se re-sembró la
cuenta con el **MISMO id documentado** `1484e253d2d54645945a6b1d7` (nombre `PAPER-VENTANA-a9c515`),
usando el constructor del repo (`create_simulated_account`, `initial_deposit=100000.0`) para crear la
cuenta **completa**: `investment_accounts` + cartera legacy + cartera de inversión + asiento de
depósito. **Sólo** se forzó el id de la cuenta al valor fijo; el resto de ids los generó el repo.

| Comprobación (read-only, tras la re-siembra) | Resultado |
|---|---|
| `investment_accounts` | `1484e253d2d54645945a6b1d7` = (`PAPER-VENTANA-a9c515`, `simulated`, `active`) |
| Cartera + depósito | **1** cartera de inversión · **1** asiento de depósito |
| Promoción (localizador) | **1** fila (`promoted=true`, `shadow_validated=false`, `reasons=[semilla_operativa_ventana_no_gate_certificada]`) |
| `EdgeReport` A/B | **2** filas |
| `v283-window-b` | **existe** (`PAPER-WINDOW sma_crossover`) |
| Watch | **20** símbolos |

**Bloqueante que queda (B2, no resoluble por código):** el día de hoy es **veto legítimo de régimen**
(`BEAR_TREND`, LONG vetadas) ⇒ **no computa** y **no** se fuerza el gobernador. La ventana exige
**≥4 días reales distintos** con material durable, así que `window-run`/`window-close` **avanzan solo
en días futuros sin veto**. `P3-2`/`P3-3` siguen **abiertas** mientras no exista el material.

## 1. Qué se ha hecho (una sola vez, antes de D1)

| # | Acción | Resultado |
|---|---|---|
| 1 | Cuenta simulada **dedicada y fija** de la ventana | `1484e253d2d54645945a6b1d7` (`PAPER-VENTANA-a9c515`) |
| 2 | **Versión B** con definición ejecutable sembrada | `v283-window-b` (preset `sma_crossover`) |
| 3 | Fila **localizadora** de promoción keyed por la cuenta | `strategy_promotions.instrument_id = 1484e253d2d54645945a6b1d7`, `promoted=true` |
| 4 | `EdgeReport` de **A** y de **B** sobre la misma cuenta | 2 filas (`edge_score=0.90`, `credibility=0.80`) |
| 5 | `.env` del operador | `PAPER_D_ACCOUNT_ID=1484e253d2d54645945a6b1d7`, `BROKER_VENUE=paper` |
| 6 | API reiniciada para releer `.env` | `/api/health/ready` = `ready`, head `046_fill_reference_mid` (hoy `048_journal_entry_dedupe_key`) |
| 7 | Registro de setup | `operability_runs/window-setup.json` (no versionado) |

**Identificadores fijos de la ventana (D1..D4):**

- `$ACCOUNT` = `1484e253d2d54645945a6b1d7`
- `$VERSION_A` = `v283-window-a`
- `$VERSION_B` = `v283-window-b` (ACTIVE sembrada, `sma_crossover`)
- watch = los 20 símbolos del catálogo real (derivación determinista por `id`, `>=60` barras D1)

## 2. Declaración de honestidad: la B es una SEMILLA, no una promoción certificada

El material de la ventana **no** gana crédito por esto; gana **medibilidad**. Sin ambigüedad:

- La fila de `strategy_promotions` es un **localizador de ámbito**, no una certificación. Lo declara
  el propio store: *«la fila de localización NO certifica shadow»*
  ([`strategy_lifecycle_store.py`](../../packages/py/application/src/bolsa_application/strategy_lifecycle_store.py), `save_active`).
- Por eso la fila se inserta con **`shadow_validated=false`** y con
  **`reasons=["semilla_operativa_ventana_no_gate_certificada"]`**, que viaja en la propia DB.
- El `EdgeReport` de B (y el de A) es **sintético**, con el mismo criterio y valores que el que el
  propio runner siembra para A cuando crea la cuenta
  ([`v2_76_forward_market_material.py`](../../apps/api-python/scripts/v2_76_forward_market_material.py), `_seed_edge_report`).
  La ausencia de edge **no** se rellena por defecto en producción: aquí se siembra **declarándolo**.
- La definición ejecutable de B se construye con el constructor del repo
  ([`strategy_definition_from_preset`](../../packages/py/analytics/src/bolsa_analytics/signals/preset_catalog.py)),
  no se inventa: la señal se evalúa de verdad (`evaluate_strategy_last_bar`).

**Consecuencia exacta:** `pairActive=true` significa **«par A/B operativo sembrado»**, *no*
«promoción certificada por los gates». `P3-3` (A/B) **no se cierra** con esta semilla: queda
**medible**. Del mismo modo, `P3-2` sigue exigiendo **≥4 días de calendario reales**; una fixture o
una corrida rápida no la cierran.

## 3. Verificación ejecutada (antes de D1)

**Preflight read-only (no escribe nada)** — `v2_76 … --preflight-only --watch-size 20`:

```
régimen por símbolo            {'range': 8, 'trend_down': 9, 'trend_up': 3}
agregado (más conservador)     trend_down
eje operativo                  BEAR_TREND
entradas LONG                  VETADAS (regime_invalid)
exit 2
```

**Lectura honesta (idéntica a la del runbook §1).** El mercado de hoy veta todas las entradas LONG
con el agregado más conservador. Si la ventana arranca en `BEAR_TREND`, `signals=0`/`fills=0` es un
**veto legítimo de régimen**, **no** un fallo de AUTO. No se fuerza `AUTO_ENGINE_SIM_V2_REGIME` y el
veredicto honesto mientras no haya material sigue siendo **`INCONCLUSIVE` / `NO MEDIDO`**.

**Sonda read-only de la B** (sin abrir el motor ni escribir material): `get_active(instrument_id=$ACCOUNT)`
devuelve `v283-window-b` con `executable` presente; `load_active_strategy_decider(...)` devuelve un
decider real con `source="active-strategy:v283-window-b"` ⇒ **`secondaryActive=true`**,
`versionB` no vacío y `watchB` no vacío ⇒ **`pairActive=true`** en el JSON del forward.

## 4. Reglas duras durante la ventana (no negociables)

- `$ACCOUNT` y `$VERSION_A` **constantes** D1..D4; un cambio de cuenta intermedio **invalida** la ventana.
- **No** se toca el gobernador (`aggregate_trial_regime`), `TOP_N`, umbrales `32/3/8/4/2`, allocation,
  pesos A/B, ni la lógica A/B durante la observación: se **mide** el AUTO congelado, no se optimiza.
- **No** se fuerza el régimen, **no** se backdatea `created_at`, **no** se baja
  `min cycles`/`min R`/`folds`/`min_is`/`min_oos`/`min_episodes`.
- **Forward, no replay.** Capturador y auditor **read-only**; no se escribe en `evidence_runs/` ni
  `evidence_validations/` ni en el journal durable desde el auditor.
- **No** se borran los *fixtures* de `operability_runs/`; el glob de las corridas **reales** es
  `operability_runs/forward-market-*.json`.
- `otherCount > 0` ⇒ `H-4` deja de ser teórico: catalogar los `signal_*` **antes** de cerrar la fase
  estadística. `n/d` = **no medido**, nunca `0`.
- Ninguna deuda (`P3-2`, `P3-3`, `H-4`) se cierra por documentación: **primero datos, después evidencia**.

## 4.bis Registro de D1 (lanzado; reiniciado por cambio de árbol ajeno)

D1 quedó **lanzado** con el comando exacto del runbook §3.1 (protocolo completo, **sin** atajos de
cadencia), en segundo plano:

```
uv run --no-sync python apps/api-python/scripts/v2_76_forward_market_material.py \
    --account-id 1484e253d2d54645945a6b1d7 --version-a v283-window-a \
    --interval-seconds 60 --max-ticks 400 --stop-when-ready --level evidence \
    --json --out operability_runs/forward-market-20260928.json
```

### Incidente: el árbol cambió DURANTE la ventana (declarado)

Entre el primer lanzamiento y el definitivo, **terceros** (no esta operación) crearon tres commits
en el repo **mientras D1 corría**:

| Commit | Hora | Alcance |
|---|---|---|
| `a0f03017` `feat(v2.84): CONTRATO DEL FUNNEL (AUTO-MATERIAL-12)` | 23:54:56 | **código**: `operability_audit.py` (+42/-9), `v2_83_window_audit.py` (docstring), `v2_44_mutation_audit.py`, tests |
| `bad2866c` `chore(ops): anexo operativo…` | 23:55:04 | barrió los ficheros de **esta** operación (script ops + este doc + runbook) |
| `fd3859e3` `docs(v2.84): docs de fase + bump … -> 2.09.0-beta` | 23:55:14 | docs de fase + **bump de `package.json`** |

El commit declara **no** tocar motor, gobernador, `operability_window.py`, `TOP_N`, umbrales,
allocation, pesos A/B, UI ni migraciones (sigue `046_fill_reference_mid`), pero **sí** cambia la
lectura del funnel que usa el pipeline (`v2_83`). Mantener el primer forward habría dejado el material
**en un árbol y la auditoría en otro**: se **abortó y reinició** D1 para que forward y auditoría
compartan **un único árbol**.

- **Coste:** ~20 min de reloj y **cero** material (comprobado: `sim_fill_finance_context`,
  `sim_auto_positions`, `sim_consumed_signals`, `portfolio_reservations`, `pending_orders`,
  `execution_events`, `decision_sessions`, `trial_records` = **0 filas** para la cuenta). No se borró
  ni se fabricó nada.
- **Verificación previa al relanzamiento:** imports OK de `v2_76`/`v2_77`/`v2_80`/`v2_83` en el árbol
  nuevo y preflight read-only idéntico (`BEAR_TREND`, exit 2).
- **Si el árbol vuelve a moverse durante D1..D4, esta hoja debe repetirse.**

### Estado final del forward de D1

| Dato | Valor |
|---|---|
| Árbol de **CÓDIGO** congelado (lo que importa) | `apps` = `980c7b6e782296dda50be99385a2350b2cb4b83e`, `packages` = `ffe36fd2fbcf3c12ea26b7523c334f6399a6b716` |
| Commit de arranque | `fd3859e3` (docs-only posteriores: `1f2638aa`, `434f058d` — **no** tocan `apps`/`packages`) |
| PID del forward | `34492` (proceso `uv`, lanzado **2026-09-28 00:02:32** local) |
| Salida | `operability_runs/forward-market-20260928.json` (se escribe **al terminar**) |
| Logs | `logs/dev/forward-d1.out.log`, `logs/dev/forward-d1.err.log` |
| Duración prevista | 400 ticks × 60 s ≈ **6 h 40 min** (estimación **incumplida**: ver *cadencia observada*) |
| Primera lectura del relanzamiento | `[22:11:36Z] ticks=10 prices=20/20 cycles=0/0 verdict=BLOCKED` |

**Cadencia observada — la máquina SE SUSPENDIÓ durante D1 (declarado 2026-09-28):** el log del
forward registra solo **tres** marcas en 7 h 30 min, con un **salto** entre el tick 20 y el tick 30:

```text
[22:11:36] ticks=10 prices=20/20 cycles=0/0 verdict=BLOCKED
[22:21:52] ticks=20 prices=20/20 cycles=0/0 verdict=BLOCKED
[05:30:12] ticks=30 prices=20/20 cycles=0/0 verdict=BLOCKED   <-- ~7 h 08 min después del tick 20
```

El forward pidió **60 s por tick**, así que esos 10 ticks «debían» tardar 10 min: hubo ≈**6 h 58 min**
de **suspensión del equipo** (no de trabajo del motor). Consecuencias, declaradas en lugar de maquilladas:

- **D1 NO termina ≈06:45**: a 60 s/tick le restan ~370 ticks ⇒ fin **≈11:40 local** (estimación, puede
  moverse). El `--max-ticks 400` sigue siendo el criterio, no el reloj.
- **La cadencia no es «1 tick = 1 minuto de mercado»**: la suspensión dilata el reloj de pared. El
  material que se acumule sigue siendo **honesto** (cada tick sigue midiendo precio/régimen reales), pero
  el **día** del material es el de la fecha de ejecución y **no** se puede inferir del número de ticks.
- **No** se altera el proceso ni se reinicia D1 por esto: la suspensión **no** cambia el árbol de
  **código** (los hashes `apps`/`packages` siguen intactos) ni fabrica ni pierde material.
- **Recomendación operativa:** mantener el equipo **sin suspensión** durante D1..D4 (o declarar cada
  salto como este) para que los cuatro días tengan una cadencia comparable.

**Cómo comprobar que el árbol de código no se movió** (debe repetirse al cerrar la ventana):

```powershell
git rev-parse "HEAD:apps" "HEAD:packages"   # debe dar 980c7b6e… y ffe36fd2…
```

Si esos dos hashes cambian durante D1..D4, la ventana deja de ser de un solo árbol de código y hay que
**declararlo** (y decidir si se reinicia el día, como se hizo aquí).

**Nota de día:** el forward arrancó pasada la medianoche local, así que el día del material es
**2026-09-28** y el fichero se nombra en consecuencia. `v2_77` deriva el `day` del **nombre del
fichero** (`_derive_day`: sin campo `day`/`asOf`/`date` en el JSON del runner, toma el token `YYYYMMDD`
del stem) y lo declara en `daySource`; por eso el nombre del fichero **no** es cosmético.

**Lectura honesta:** el runner sirve precio de los 20 símbolos (`prices=20/20`) y **no** acumula
ciclos (`cycles=0/0`, `verdict=BLOCKED`) porque el eje sigue en `BEAR_TREND` y el motor veta las
entradas LONG. Es el **veto legítimo de régimen** ya declarado en §3, no un fallo de AUTO:
`signals=0`/`fills=0` **no** se maquilla ni se fuerza.

## 4.ter Pipeline de D1 (al terminar el forward)

Una vez exista `operability_runs/forward-market-20260928.json`, se encadena (valores fijos, sin
placeholders):

```powershell
$ACCOUNT   = "1484e253d2d54645945a6b1d7"
$VERSION_A = "v283-window-a"
$DIA       = "20260928"

uv run --no-sync python apps/api-python/scripts/v2_77_market_operability.py `
    --forward "operability_runs/forward-market-$DIA.json" --render

uv run --no-sync python apps/api-python/scripts/v2_80_market_window.py `
    --account-id "$ACCOUNT" --strategy-version "$VERSION_A" --days 4 --render `
    --forward 'operability_runs/forward-market-*.json' `
    --out "operability_runs/operability-window.json" `
    --html "operability_runs/operability-window.html"

uv run --no-sync python apps/api-python/scripts/v2_83_window_audit.py `
    --window "operability_runs/operability-window.json" `
    --forward 'operability_runs/forward-market-*.json' --render `
    --out "operability_runs/operability-audit.json"
```

**Qué se exige leer al terminar el pipeline:** `Par = ACTIVO` y **ausencia** del aviso
`pair_not_active` (la semilla habilitó `pairActive=true`); el funnel
`universe → marketData → regimeAllowed → signals → topN → risk → reservation → orders → fills → cycles`
debe localizar el escalón donde se pierde la oportunidad (con `BEAR_TREND`, el corte cae en
`regimeAllowed`). El gate de evidencia sigue en **`NO MEDIDO`** hasta reunir ≥4 cubos, ≥2 episodios y
≥32 ciclos.

**Automatización (opcional):** el [runbook §3.3](./runbook-ventana-forward-v2.78-2026-09-27.md) documenta el
runner `scripts/window-forward-runner.mjs` (`pnpm window:preflight` / `window:run-day` / `window:status` /
`window:task:install`), que encadena los pasos 1–5 con artefactos por día, ledger y **freeze** del árbol
(`git rev-parse "HEAD:apps" "HEAD:packages"`); aborta con `TREE_MOVED` si el código se mueve y registra
`NO_MEDIDO_REGIMEN` cuando el preflight vetea (sin lanzar el forward).

## 5. Cadencia diaria D1..D4

Los comandos exactos (PowerShell) están en el
[runbook de la ventana](./runbook-ventana-forward-v2.78-2026-09-27.md) §3.1, con `$ACCOUNT` y
`$VERSION_A` de esta tabla. Resumen del encadenado por día:

```
preflight v2_76  →  forward v2_76 (--account-id fijo)  →  journal v2_77
                 →  ventana v2_80 (--days 4 --forward 'operability_runs/forward-market-*.json')
                 →  auditoría read-only v2_83 (--window operability_runs/operability-window.json)
```

El gate de evidencia (§4 del runbook) solo se lee con **≥4 cubos de calendario compartidos**,
**≥2 episodios** de régimen y **≥32 ciclos** medibles; hasta entonces el veredicto es
**`NO MEDIDO`**.

## 6. Qué NO cambia

El tag `v2.83.1-beta` (objeto auditado) permanece **intacto**: este arranque es operación sobre el
mismo instrumento read-only y el mismo AUTO congelado. Diff de producto: **ninguno** (solo el script
de operación, `.env` local no versionado y este documento).
