# Audit-pack — `AUTO-MATERIAL-13` / `V2.85` — CIERRE DE `OBS-10` (stateCounts) + ETIQUETA DE `unresolvedRate` + ENDURECIMIENTO OPS

> **Objeto a auditar:** rama **`feat/v2.85-obs10-comportamiento`** (worktree aislado sobre `63696d0c`;
> **NO** mergeada a `main`) · **Versión:** `2.10.0-beta` · **Base del diff:** `v2.84-beta`
> (`2.09.0-beta`, commit `fd3859e3`) · **AsOf:** 2026-09-28 · **Alembic head:** `046_fill_reference_mid`
> (**SIN migración**). **Tag `v2.85-beta`: PENDIENTE** (se crea en `main` tras cerrar la ventana PAPER y
> mergear la rama; ver §5).

## 1. Qué es esta fase

Fase de **código** que cierra la observación **`OBS-10`** de la auditoría externa de `v2.84-beta`, etiqueta
honestamente `unresolvedRate` (sin renombrar la clave) y endurece un script de OPERACIÓN. **No** cambia el
motor (`auto_simulation_worker.py`), el gobernador (`aggregate_trial_regime`), `operability_window.py`,
`v2_80_market_window.py`, `TOP_N`, umbrales, allocation, pesos A/B, UI ni migraciones.

**Por qué se ejecuta en una rama aislada y no en `main`:** hay una **ventana PAPER viva** (D1..D4) y la
regla de freeze prohíbe mover `packages/`/`apps/` en `main` mientras corre. Las lecturas hacia delante de
la ventana consumen el **árbol de trabajo de `main`**, que esta rama **no toca**; la ventana sigue válida y
esta fase se mergea a `main` cuando la ventana cierre. `main` permanece en **`63696d0c`**.

## 2. Diff esperado (acotado)

- `package.json` (`2.09.0-beta → 2.10.0-beta`).
- `packages/py/application/src/bolsa_application/operability_audit.py` (instrumento puro).
- `packages/py/application/tests/test_operability_audit.py` (+1 test).
- `apps/api-python/scripts/v2_44_mutation_audit.py` (+`M233`).
- `apps/api-python/scripts/ops_seed_window_pair.py` (**endurecimiento OPS**, ver §2.1).
- `docs/engineering/*` (audit-pack, arranque del auditor, arranque del agente, relevo, `PROJECT_STATE`,
  índice, deuda P3) + `CHANGELOG.md`.

### 2.1 Anexo operativo (DECLARADO, fuera del instrumento)

`ops_seed_window_pair.py` **no** forma parte de las tesis falsables de §3: es el **script OPS** que el
operador ejecuta para sembrar la cuenta fija de la ventana, la versión B `ACTIVE` y los `EdgeReport` de
A/B. El endurecimiento cierra la vía de **acuñar una cuenta nueva en silencio** (el auditor advirtió que
`D1 → account 101`, `D2 → account 102` **rompe la continuidad de la muestra**):

- Nuevo flag **`--allow-create`**. Sin `--account-id` **y** sin `--allow-create`, el script imprime
  `# uso incorrecto: …` a `stderr` y sale con **código 1** (uso incorrecto) **antes** de tocar PostgreSQL.
- `_resolve_account` gana `allow_create: bool = False` y levanta `ValueError` **defensivamente** si se le
  pide crear sin autorización explícita.

**Ficheros PROHIBIDOS en el diff** (si aparecen, la fase se sale de alcance): `auto_simulation_worker.py`,
`aggregate_trial_regime`/gobernador, `operability_window.py`, `v2_80_market_window.py`, cualquier
`alembic/` o migración, `apps/web/**`, y cualquier cambio de `TOP_N`/umbrales/allocation/pesos.

## 3. Tesis falsables (lo que el auditor debe intentar **romper**)

1. **`OBS-10` cerrado:** el bloque `stateCounts` de `window_totals` itera **`measured_rows`** (como
   `counts`/`coverage`/`rSum`/`funnel`); una fila `measured=False` con `state` poblado **no** crea bucket.
   Su docstring declara que `stateCounts` también respeta `measured_rows`. (Regresión: `M233`.)
2. **Trazabilidad del efecto:** hoy el único bucket contaminable era `unknown` (los productores son
   fail-closed: `operability_state` devuelve `unknown` si `measured` no es `True`); ninguna cifra publicada
   del material real se mueve.
3. **Etiqueta honesta de `unresolvedRate`:** `_RATE_SOURCES`, el docstring de `window_rates` y el render
   `_rate_lines` declaran que la clave es un **indicador** (vale `1.0` en cuanto hay un día medido en
   `unresolved`, `None` si no lo hay), **no** una proporción ni una tasa de propuestas. **No** se renombra
   la clave y **no** cambia la aritmética (ningún número publicado se mueve).
4. **`OBS-11` (nuevo, LOW) declarado, no cerrado:** la aritmética de `unresolvedRate` queda registrada como
   pregunta abierta en la deuda P3 (ver [deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md)).
5. **Endurecimiento OPS:** sin `--account-id` y sin `--allow-create`, `ops_seed_window_pair.py` falla
   **antes** de PostgreSQL con código **1**; con `--allow-create` la creación sigue siendo posible y
   explícita.
6. **Sin deriva semántica:** `window_rates` sigue devolviendo `rate=None` (nunca `0.0`) sin días medidos o
   con denominador `0`; `render_window_audit` sigue determinista y con `n/d` en los huecos.
7. **Compuertas verdes y reproducibles** (§4).
8. **Sin cierre de deuda por documentación:** `P3-2`/`P3-3`/`H-4`/`OBS-9`/`P3-5`/`OBS-5`/`OBS-11` siguen
   **ABIERTOS** y así se declaran.

## 4. Compuertas medidas en la rama (números exactos)

```powershell
pytest packages/py/application/tests/test_operability_audit.py -q          # 19 passed (18 -> 19)
pytest packages/py/application/tests -q                                    # 2085 passed, 5 skipped (2090 recogidos; eran 2089)
ruff check packages/py apps/api-python --config pyproject.toml             # All checks passed!
python -c "from importlinter.cli import lint_imports_command; ..."         # Contracts: 4 kept, 0 broken.
python -m mypy (5 raíces de fuentes)                                       # Success: no issues found in 507 source files
python apps/api-python/scripts/v2_44_mutation_audit.py                     # medidas: 233/233 (matriz 232 -> 233)
```

**Medida ANTES/DESPUÉS del arreglo (obligatoria, para descartar que mueva una cifra publicada):** sobre
**material real** (31 días medidos de una cuenta con fills/cierres, no fixtures), `stateCounts` da
`{'no_signal': 30, 'operated': 1}` **idéntico** con el código pre-fix (`main`) y con el de esta rama. El
arreglo sólo afecta a filas `measured=False`, y el material real no tiene ninguna.

**Evidencia cruda de la matriz:** [`evidencia-matriz-mutaciones-v2.85-233-2026-09-28.txt`](./evidencia-matriz-mutaciones-v2.85-233-2026-09-28.txt)
(capturada por el coordinador; **no** la genera el instrumento de auditoría).

## 5. Límites declarados (honestidad)

- **NO mergeada a `main`; `main` intacto en `63696d0c`.** El freeze de `main` sigue **INTACTO**:
  `git rev-parse "HEAD:apps" "HEAD:packages"` = `980c7b6e782296dda50be99385a2350b2cb4b83e` /
  `ffe36fd2fbcf3c12ea26b7523c334f6399a6b716`.
- **Sello `v2.85-beta` PENDIENTE, con motivo.** `v2.85-beta` es la **siguiente auditoría externa** y **no
  hay re-sello intermedio**, pero el tag anotado **debe crearse en `main` tras cerrar la ventana y mergear
  esta rama**: la cita del CI de un tag es **POST-TAG por construcción** (`Release tag CI` solo corre al
  empujar) y `main` **no puede moverse** mientras la ventana está viva. Esta fase entrega **código + docs +
  bump**; el sellado (tag + cita del CI autocontenida, patrón `OBS-3`/`OBS-4`) queda **PENDIENTE y
  declarado**. **No** se cita aquí ningún `run` de CI: **`(pendiente)`** hasta que exista el tag.
- **Sin CI del tag todavía** ⇒ no hay `evidencia-ci-tag` de `v2.85`; el auditor **no** debe leer su
  ausencia como fallo.
- **Caveat de entorno (honesto):** en este worktree, invocar los shims de consola `mypy` y `lint-imports`
  está bloqueado por **Windows Application Control** (`os error 4551`); ambos se ejecutaron mediante
  `python -m mypy` y `importlinter.cli`. Son **las mismas herramientas**, no sustitutos.
- **Ventana PAPER viva:** la fase se ejecutó **en rama** precisamente para no invalidarla; el material real
  de la ventana sigue pendiente de cierre (ver el [relevo](./traspaso-relevo-post-v2-85-auto-material-13-obs10-comportamiento-2026-09-28.md)).
- **`OBS-11` (LOW) y `P3-2`/`P3-3`/`H-4`/`OBS-9`/`P3-5`/`OBS-5` ABIERTOS.** Ninguna deuda se cierra por
  documentación: primero el dato, después la evidencia.

Referencias: [plan `v2.85`](./plan-v2-85-auto-material-13-statecounts-y-auditoria-comportamiento-2026-09-28.md) ·
[arranque del auditor](./arranque-auditor-v2-85-auto-material-13-obs10-comportamiento-2026-09-28.md) ·
[arranque del agente](./arranque-agente-v2-85-auto-material-13-obs10-comportamiento-2026-09-28.md) ·
[relevo](./traspaso-relevo-post-v2-85-auto-material-13-obs10-comportamiento-2026-09-28.md) ·
[deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md) ·
[protocolo de comportamiento](./protocolo-auditoria-comportamiento-auto-2026-09-28.md) ·
[auditoría que originó `OBS-10`](./auditoria-v2-84-auto-material-12-instrument-funnel-contract-2026-09-28.md).
