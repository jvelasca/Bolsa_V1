# Traspaso / relevo — post `v2.85` / `AUTO-MATERIAL-13`: cierre de `OBS-10` y observación `OBS-11`

> **AsOf:** 2026-09-28 · **Etiqueta de entrega:** **bump a `2.10.0-beta`**, en **rama aislada** y **SIN
> tag** · **Base:** `v2.84-beta` (`2.09.0-beta`, commit `fd3859e3`) · **HEAD de `main`:** `63696d0c`
> (**intacto**).
> **Rama:** `feat/v2.85-obs10-comportamiento` (worktree aislado, **NO** mergeada a `main`) ·
> **Alembic head:** `046_fill_reference_mid` (**SIN migración**) · **Freeze de `main` intacto:** `apps` =
> `980c7b6e782296dda50be99385a2350b2cb4b83e`, `packages` = `ffe36fd2fbcf3c12ea26b7523c334f6399a6b716`.
> **Lectura:** fase de **CÓDIGO** ejecutada en rama para **no mover el árbol de código de `main`** mientras
> corre la ventana PAPER (D1..D4). Cierra `OBS-10` **con código + test + mutación**, etiqueta
> `unresolvedRate` **sin renombrar la clave** y endurece `ops_seed_window_pair.py`. El **sello `v2.85-beta`
> está PENDIENTE** (se crea en `main` tras cerrar la ventana y mergear).

## Qué quedó hecho

### 1. `OBS-10` CERRADA (la observación de la auditoría de `v2.84-beta`)

En `packages/py/application/src/bolsa_application/operability_audit.py`, el bloque `stateCounts` de
`window_totals` iteraba **`rows`** (todos los días) mientras `counts`/`coverage`/`rSum`/`funnel` iteraban
**`measured_rows`**. Ahora itera **`measured_rows`**, y el docstring de `window_totals` declara que
`stateCounts` **también** respeta `measured_rows`.

**Matiz que esta fase midió (no lo tenía el auditor):** hoy sólo el bucket `unknown` podía contaminarse,
porque `operability_state` es **fail-closed** (`unknown` en cuanto `measured` no es `True`). Pero
`window_totals` es **pura sobre filas arbitrarias** (el CLI consume JSON/JSONL) ⇒ el endurecimiento es
**válido**. **Ninguna cifra publicada del material real se mueve.**

### 2. Test de regresión

`test_window_totals_state_counts_ignores_unmeasured_rows` **añadido** a
`packages/py/application/tests/test_operability_audit.py` (**18 → 19** tests), siguiendo el estilo de la
regresión de `OBS-7`: un día `measured=False` (**con** y **sin** `state` poblado) **no** crea bucket,
mientras un día medido **sí**.

### 3. Mutación `M233`

Añadida a `apps/api-python/scripts/v2_44_mutation_audit.py` (matriz **232 → 233**), mordiendo
**exactamente** ese test. Resultado: **`medidas: 233/233`**.

### 4. `ops_seed_window_pair.py` endurecido

`apps/api-python/scripts/ops_seed_window_pair.py` **ya no puede** acuñar una cuenta simulada nueva en
silencio. Nuevo flag **`--allow-create`**: sin `--account-id` y sin `--allow-create`, imprime
`# uso incorrecto: …` a `stderr` y sale con **código 1** (uso incorrecto) **antes** de tocar PostgreSQL.
`_resolve_account` gana `allow_create: bool = False` y levanta `ValueError` **defensivamente**.
**Motivo (auditor):** una cuenta nueva en silencio rompe la continuidad de la muestra (`D1 → account 101`,
`D2 → account 102`).

## Un hallazgo NUEVO mientras se etiquetaba `unresolvedRate`: `OBS-11` (LOW)

El plan sólo pedía **etiquetar** `unresolvedRate`. Al hacerlo se comprobó la aritmética y **no** encaja con
su etiqueta antigua. En `window_rates`,
`unresolved_pairs = [(1, 1) for row in rows if _measured(row) and _text(row.get("state")) == STATE_UNRESOLVED]`,
y `_rate_from_pairs` **suma** los pares ⇒ `numerador == denominador ==` número de días **medidos** en estado
`unresolved`. Por tanto `rate` es **`1.0`** en cuanto hay un día así, y **`None`** cuando no lo hay: es un
**indicador**, **no** una proporción **ni** una tasa de propuestas.

**Decisión tomada:** etiquetarlo **honestamente** (`_RATE_SOURCES`, el docstring de `window_rates` y el
render `_rate_lines` ya lo dicen), **sin renombrar la clave y sin cambiar la aritmética** (ningún número
publicado se mueve). La pregunta aritmética se registra como observación nueva **`OBS-11` (LOW)** en la
[deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md). **Es una declaración honesta, no un cierre.**

## Compuertas medidas en la rama

| Compuerta | Resultado |
|---|---|
| `pytest packages/py/application/tests/test_operability_audit.py -q` | **19 passed** (18 → 19) |
| `pytest packages/py/application/tests -q` | **2085 passed, 5 skipped** (= **2090** recogidos; eran **2089**) |
| `ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| `lint-imports` (vía `importlinter.cli`) | **Contracts: 4 kept, 0 broken.** |
| `mypy` (vía `python -m mypy`, 5 raíces de fuentes) | **Success: no issues found in 507 source files** |
| `v2_44_mutation_audit.py` | **medidas: 233/233** (crudo en [`evidencia-matriz-mutaciones-v2.85-233-2026-09-28.txt`](./evidencia-matriz-mutaciones-v2.85-233-2026-09-28.txt)) |
| Medida ANTES/DESPUÉS de `stateCounts` sobre material real | **Sin delta**: sobre 31 días medidos de una cuenta con material real (`v75-producer-orb-v1`), `stateCounts` = `{'no_signal': 30, 'operated': 1}` **idéntico** con el código pre-fix (`main`) y con el de `v2.85`. El arreglo sólo mueve filas `measured=False`, y el material real no tiene ninguna. |

> **Caveat de entorno (honesto):** en este worktree, invocar los shims de consola `mypy` y `lint-imports`
> está bloqueado por **Windows Application Control** (`os error 4551`), así que ambos se ejecutaron
> mediante `python -m mypy` / `importlinter.cli`; son **las mismas herramientas**.

## El hallazgo, en una línea

La única observación **real** de la auditoría de `v2.84-beta` era `OBS-10` (`stateCounts`), y su corrección
**no** podía hacerse en `main` porque una ventana PAPER viva prohíbe mover `packages/`. Se hizo **en una
rama aislada**, con test y mutación; al etiquetar `unresolvedRate` apareció **`OBS-11`**, que se registra
**sin** tocar la clave ni el número.

## Estado de la deuda

| Deuda | Estado |
|---|---|
| `OBS-10` (LOW, `stateCounts`) | CERRADA **en la rama** (código + test + `M233`); **pendiente de merge a `main`** |
| `OBS-11` (LOW, aritmética de `unresolvedRate`) | ABIERTA y declarada |
| `P3-2` / `P3-3` | ABIERTAS — exigen ventana PAPER ≥4 días **real** |
| `H-4` (LOW) | ABIERTO — visible vía `warnings: reason_contract` |
| `OBS-9` (doc-only, frase `1 = uso incorrecto` replicada en CLIs) | ABIERTA y declarada |
| `P3-5`, `OBS-5` | declaradas |
| `OBS-6` / `OBS-7` / `OBS-8` | CERRADAS en `v2.84` |

**Ninguna deuda se cierra por documentación.** Primero datos, después evidencia.

## La ventana D1..D4 (la sorpresa de la fase; es OPERACIÓN en tiempo real)

**(a) D1 apareció MUERTO al inicio de la fase.**

| Dato | Valor |
|---|---|
| Síntoma | PID `34492` desaparecido; `logs/dev/forward-d1.out.log` congelado en `ticks=60` (06:03:46 UTC / 08:03:46 local) |
| Salida esperada | `operability_runs/forward-market-20260928.json` **NO** existía |
| Logs antiguos | preservados como `forward-d1-dead.{out,err}.log` |
| **Causa raíz** | **Docker Desktop estaba parado** ⇒ PostgreSQL (contenedor `bolsa-postgres`) inalcanzable ⇒ el preflight read-only murió con `psycopg.errors.ConnectionTimeout`. **Eso, y no la sesión del agente, mató a D1.** |
| Remediación | Docker Desktop arrancado de nuevo; `bolsa-postgres` **healthy** en el puerto 5432 |

**(b) D1 RELANZADO detached** (2026-09-28 08:38:05 local) con el par **FIJO**:

- `--account-id 1484e253d2d54645945a6b1d7 --version-a v283-window-a`
- `--max-ticks 400 --interval-seconds 60 --stop-when-ready --level evidence`
- Salida `operability_runs/forward-market-20260928.json`; log `logs/dev/forward-d1.out.log`
- PID guardado en `logs/dev/forward-d1.pid` (PID **`16508`**)

**(c) Preflight (read-only) exit 2** — declarado, **no** forzado:

- Régimen por símbolo `{'range': 8, 'trend_down': 9, 'trend_up': 3}`, agregado `trend_down`, eje
  **`BEAR_TREND`** ⇒ entradas **LONG vetadas** (`regime_invalid`).
- **Consecuencia:** D1 acumulará `cycles=0/0` **legítimamente**, así que el gate de evidencia (≥4 días /
  ≥2 episodios / ≥32 ciclos) **NO** se cumplirá y el veredicto honesto esperado es **`INCONCLUSIVE` /
  `NO MEDIDO`**. **`P3-2`/`P3-3` siguen ABIERTAS.**

**(d) HALLAZGO DURO: la ventana de esta cuenta está VACÍA y seguirá vacía.** Medido en esta fase, no
deducido:

- La cuenta `1484e253d2d54645945a6b1d7` tiene, en los últimos 5 días, **0** filas en
  `sim_fill_finance_context` (fills), **0** en `portfolio_reservations` y **0** en
  `decision_journal_entries`.
- El capturador construye los días de la ventana **sólo** con material durable:
  `v2_80_market_window.py:210` es `days = sorted(set(fills_by_day) | set(cycles_by_day) | set(journal_by_day))`.
  El `--forward` **no crea días**: sólo **enriquece** los que ya existen (`evidence=evidence_by_day.get(day)`
  en la línea 232). Sin filas durables, el `--forward` de D1..D4 es **inocuo**.
- Por eso `v2_80_market_window.py --account-id 1484e253… --strategy-version v283-window-a --days 4` sale con
  **exit 2** y `# BLOQUEADO: no hay ningún día de operabilidad que leer en la ventana`.

**Consecuencia operativa (la que importa):** mientras el eje siga en `BEAR_TREND` y el motor vete las
entradas LONG, la ventana **no acumula nada** — ni un día, ni una fila. Correr **D2, D3 y D4 no cambia el
resultado**: ni el censo de entradas (vive en memoria del proceso, `worker._v2_journal`, y sólo se serializa
en el `--out` del runner) ni los fills/cierres (no hay operaciones) se vuelven durables. El veredicto honesto
de esta ventana es **`NO MEDIDO`**, y `P3-2`/`P3-3` **no** se cierran.

> **No se fuerza nada.** Bajar `TOP_N`, umbrales, `min cycles`/`min R`/`folds`/`min_episodes`, cambiar el
> watch o el gobernador para «producir» operaciones está **prohibido**: sería fabricar la muestra. El
> `BEAR_TREND` es un **veto legítimo de régimen**.

> **Recordatorio para el operador:** el forward se lanza **detached** (`Start-Process -PassThru`) y, sobre
> todo, **Docker Desktop debe permanecer arriba durante toda la ventana D1..D4**; un Docker parado mata la
> corrida **en silencio**.

## Decisión de sellado (declarada, NO ejecutada)

`v2.85-beta` es la **SIGUIENTE auditoría externa** y **no** hay **re-sello intermedio**. Pero el tag anotado
**debe crearse en `main` después de cerrar la ventana y mergear esta rama**: la cita del CI de un tag es
**POST-TAG por construcción** y `main` **no puede moverse** mientras la ventana está viva. Por tanto esta
fase entrega **código + docs + bump** (`package.json` `2.09.0-beta → 2.10.0-beta`) y el **sello** (tag
`v2.85-beta` + la cita del CI POST-TAG, **autocontenida** según el patrón `OBS-3`/`OBS-4`) queda
**PENDIENTE** y declarado. **No** se cita aquí ningún `run` de CI: **`(pendiente)`** hasta que exista el tag.

## Lo que hereda el siguiente

1. **OPERACIÓN (bloqueante real, no se puede fabricar):** D1 quedó **relanzado y vivo**
   (PID `16508`, `logs/dev/forward-d1.pid`), pero el hallazgo (d) de arriba manda: con el eje en
   `BEAR_TREND` la ventana **está vacía y no acumulará nada**; completar D2..D4 **no** cambia el veredicto.
   Lo honesto es **declarar `NO MEDIDO` por veto legítimo de régimen** y **no** forzar entradas. Si se
   decide seguir mirando el eje, el [runbook](./runbook-ventana-forward-v2.78-2026-09-27.md) §3.1 sigue
   siendo el procedimiento: preflight → forward → ventana → auditoría, con **cuenta y versión fijas** y
   **chequeo de freeze cada día** (`git rev-parse "HEAD:apps" "HEAD:packages"` = `980c7b6e…` / `ffe36fd2…`).
2. **Auditoría de comportamiento** con el
   [protocolo](./protocolo-auditoria-comportamiento-auto-2026-09-28.md): localizar el escalón del atasco
   —hoy el **escalón 0**: el eje veta y no hay ni una propuesta— y emitir el veredicto honesto. **Nada se
   cierra con 1 día degenerado.**
3. **Merge a `main`** de esta rama (`feat/v2.85-obs10-comportamiento`, commit `89f0596d`) **cuando la
   ventana cierre** (hoy `main` no puede moverse).
4. **Sello `v2.85-beta`** en `main` (tag + cita POST-TAG). Después, `AUTO-22`/`AUTO-23` y cierre de
   `P3-2`/`P3-3`; `H-4` sólo si `otherCount > 0`; `OBS-11` cuando se decida la semántica.

## Reglas duras que siguen vigentes

- **No** se toca el motor (`auto_simulation_worker.py`), el gobernador (`aggregate_trial_regime`),
  `operability_window.py`, `v2_80_market_window.py`, `TOP_N`, umbrales, allocation, pesos A/B, UI ni
  migraciones (`046_fill_reference_mid`).
- **No** se cierra deuda por documentación: `OBS-11`/`P3-2`/`P3-3`/`H-4`/`OBS-9`/`P3-5`/`OBS-5`
  **ABIERTAS**.
- **No** se baja `min cycles` / `min R` / `folds` / `min_episodes` para forzar una corrida.
- **Forward, no replay:** no se inyecta ni se backdatea `created_at`.
- **No** se añade ninguna capa nueva de observabilidad (es lo que pide el auditor).
- El **capturador y el auditor son read-only**; veredicto honesto `INCONCLUSIVE`/`NO MEDIDO` si la ventana
  está degenerada.

## Comandos de verificación rápida

```powershell
git branch --show-current                               # feat/v2.85-obs10-comportamiento
git rev-parse "HEAD:apps" "HEAD:packages"               # 980c7b6e… / ffe36fd2…  (freeze de main intacto)
Select-String -Path package.json -Pattern version        # 2.10.0-beta
pytest packages/py/application/tests/test_operability_audit.py -q   # 19 passed
python apps/api-python/scripts/v2_44_mutation_audit.py   # medidas: 233/233
```

## Ficheros de la fase

- [Audit-pack `v2.85`](./audit-pack-v2-85-auto-material-13-obs10-comportamiento-2026-09-28.md) ·
  [arranque del auditor](./arranque-auditor-v2-85-auto-material-13-obs10-comportamiento-2026-09-28.md) ·
  [arranque del agente](./arranque-agente-v2-85-auto-material-13-obs10-comportamiento-2026-09-28.md)
- [Plan `v2.85`](./plan-v2-85-auto-material-13-statecounts-y-auditoria-comportamiento-2026-09-28.md) ·
  [deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md) (`OBS-10` cerrada, `OBS-11` abierta)
- [Protocolo de comportamiento](./protocolo-auditoria-comportamiento-auto-2026-09-28.md) ·
  [evidencia matriz 233](./evidencia-matriz-mutaciones-v2.85-233-2026-09-28.txt)
- **Cierre de la ventana:** [ventana PAPER — veredicto `NO MEDIDO` (2026-09-28)](./ventana-paper-cierre-no-medido-2026-09-28.md)
- Registro de la ventana: [arranque operativo PAPER](./arranque-ventana-paper-operativa-2026-09-27.md) ·
  [runbook](./runbook-ventana-forward-v2.78-2026-09-27.md)
- Auditoría externa que originó `OBS-10`:
  [auditoría `v2.84`](./auditoria-v2-84-auto-material-12-instrument-funnel-contract-2026-09-28.md)
- Contexto previo: [relevo `v2.84`](./traspaso-relevo-post-v2-84-auto-material-12-instrument-funnel-contract-2026-09-27.md) ·
  [relevo `v2.85` docs-only](./traspaso-relevo-post-v2-85-auto-material-13-comportamiento-2026-09-28.md)
