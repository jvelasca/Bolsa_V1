# Entrega a auditoría externa (MIA) — `v2.88.51-beta` · AUTO · UI: **fix del PnL `PARTIAL` + `AUTO UI SEMANTIC MODEL 1.0` congelado**

> **Fecha:** 2026-10-05 · **Producto:** V2.88.51-beta · **Package:** `2.11.51-beta` · **Alembic head:** `048_journal_entry_dedupe_key` (**sin migración**).
> **Base:** `v2.88.50-beta` (tag → `f48975bb`, `Release tag CI` `37297920781` **VERDE**).
> **Unidad:** el **ciclo**. **Regla del hueco:** un valor sin muestra es `None`/`NOT_MEASURED`/**`"UNKNOWN"`**, **nunca** `0`.
> **`Δ AUTO decision/execution motor = 0`.** Ningún fichero de motor tocado. **`Δ motor = 0` CONFIRMADO POR CI:** el artefacto congelado de `replay-repro` **se reproduce byte a byte**.
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.51/README.md`](./evidence/v2.88.51/README.md) (`§1`–`§7`).
> **Nota de auditabilidad:** como en `v2.88.46`…`v2.88.50`, la cita del `Release tag CI` **no puede** viajar dentro del propio tag (el job sólo corre al empujar el tag). La cita viaja en el **`Release`** y en `main` (`3e12ab22`); dentro del tag la evidencia la declara como **`POST-TAG`**. No es un hueco: es el límite estructural ya conocido.

**Sello dirigido (declarado).** Cierra el **único hallazgo nuevo** de la auditoría externa de `v2.88.50` y produce el entregable de diseño que el propio auditor pidió **antes** de extender la UI. **NO** se re-corre el pipeline `DÍA-D` (A/C cerrada: reabrirla sería volver a preguntar lo mismo) y **NO** se implementa el refactor de pantallas.

---

## 1. Qué se entrega (y qué NO)

**Se entregan** dos bloques, ambos **sin tocar el motor**:

1. **Fix del PnL que se publicaba `COMPLETE` con cierre `PARTIAL`.** El bloque `result` de `_build_cycle` sólo miraba `window_truncated`; un cierre degradado a `None`/`PARTIAL` por un `side` no clasificable (`unclassified_fills > 0`) **seguía publicando una cifra de dinero**. Corregido en backend (`result` se rige por la MISMA medición del cierre, `closed_measurement != COMPLETE`) y en frontend (la cifra **rota su medición**, no pinta el número a fuego como `COMPLETE`).
2. **`AUTO UI SEMANTIC MODEL 1.0` (diseño congelado).** Documento que fija la semántica de las **14 etapas** antes de crear más pantallas: clases (hecho / derivada / contexto / explicación), los **dos ejes** (estado de etapa vs medición del hecho), definiciones duras y navegación objetivo. Resuelve `TOP_N ≠ DECISIÓN`, `SALIDA ≠ LIQUIDACIÓN` y `OPORTUNIDAD` como **contexto**.

**NO se entrega**, y se declara:

- **NO** se toca el motor, los umbrales, `TOP_N`, la allocation, ni las costuras de decisión (`Δ motor = 0`).
- **NO** hay cambio de **contrato HTTP**: `openapi.json`/`schema.d.ts` **no** se mueven (`contract:check` OK).
- **NO** se re-mide `DÍA-D`: las cifras OOS de `v2.88.50` se **heredan y citan**, no se reutilizan como nuevas.
- **NO** se sustituye ninguna pantalla ni se toca el view-model `buildAutoOperationStory` (su migración al modelo es trabajo posterior, declarado en el propio documento).
- **NO** se nombra la causa de los `23 orden_creada_sin_fill` (va a una futura **Execution Analysis**, separada de la UI principal).
- **NO** se cierra `stopBasisMismatchR` ni la duplicidad semántica nivel↔stop; **NO** se emite `CONFIRMED`.

> **Modelo de ejecución declarado:** `AUTO` **no deja una orden STOP en reposo**; el stop lo ejecuta el decider `D1`. Este sello **no** re-ejecuta nada.

---

## 2. Cambios verificables (todo puro, todo con test)

| Pieza | Fichero | Qué hace |
| --- | --- | --- |
| Guard de `result` | `packages/py/application/src/bolsa_application/auto_operational_monitor.py` (`_build_cycle`) | `result = None` salvo `closed_measurement == COMPLETE` (cubre `window_truncated` **y** `unclassified_fills > 0`). |
| Mediciones en la cifra | `apps/web/src/features/auto-monitor/auto-cycle-timeline.tsx` | Usa `cycle.closedMeasurement`; con medición ≠ `COMPLETE` **rota** `PARCIAL`/`NO MEDIDO` en vez de mostrar el número. `data-testid="auto-monitor-cycle-pnl"` / `data-pnl-measurement`. |
| Modelo semántico | `docs/engineering/spec-auto-ui-semantic-model-1-2026-10-05.md` | Contrato de significado (14 etapas, dos ejes, 3 correcciones, navegación, migración, límites). |
| Test de regresión backend | `packages/py/application/tests/test_auto_operational_monitor.py` | `test_cycle_result_not_published_when_close_is_partial_by_unclassified_side` — **falla** sin el fix (publicaba `{'pnl': 100, ...}` con cierre no afirmable). |
| Test de UI | `apps/web/src/features/auto-monitor/auto-monitor.test.tsx` | 2 casos: ciclo `PARTIAL` pinta `PARCIAL` y **no** la cifra; ciclo `COMPLETE` sí publica el número. |
| Guardián de versión | `test_dia_d_bump_guard.py` | `meta.bump == package.json.version` (`2.11.51-beta`) en `v2_89`…`v2_97`. |

> **Nota de método.** El test de regresión **se verificó en rojo**: revertido el fix, el caso falla con `assert {'pnl': Decimal('100'), ...} is None` (el bug medido) y vuelve a verde al restaurarlo. **Ninguna** aserción se relajó.

---

## 3. Medición (cifras heredadas de `v2.88.50`, NO re-medidas)

Sin cambio de motor **ni de muestra**, este sello no re-corre el pipeline. Se **citan** (no se reutilizan como nuevas) las cifras vigentes de [`v2.88.50`](./evidence/v2.88.50/README.md):

| Métrica (`v2.88.50`) | Valor |
| --- | --- |
| `route` (A/C, `dia-d-thesis-exit-v5` capa v7) | `{materializado: 19, orden_creada_sin_fill: 23}` ⇒ **A = `0`**, **C = `23`** |
| `stopEvaluatedOnTouch` / `deciderRanOnTouch` | **`42/42`** / **`42/42`** |
| `candidate` (`structuralStopCandidate`) | **`42/42`** |
| `THESIS_EXIT` (n) | **`42`** (antes `38`: `2026` entra por la corrección PIT) |
| Expectancy bruta global | `-0.7150` |
| Banda global de R | `[-17.290, +19.328]`, `crossesZeroR = true`, **`pointCitable = false`** |
| Determinismo re-pipeline / plegado | `draw-00…11` idénticos · `F865106D…` / `2268FA79…` |

**Por qué no se re-mide:** la investigación A/C quedó **cerrada** en `v2.88.50` (`A = 0`); el auditor pidió **no** abrir otra rama `THESIS_EXIT`. Este sello no toca ninguna de esas costuras.

---

## 4. Gates (comandos exactos, re-ejecutados)

| Comando | Resultado |
| --- | --- |
| `pytest packages/py/application/tests/test_auto_operational_monitor.py apps/api-python/tests/test_dia_d_bump_guard.py` | **53 passed** |
| `pytest packages/py/application/tests` (directorio completo) | **2492 passed** (`207.62 s`) |
| `ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| `uv run lint-imports --config packages/py/.importlinter` | **4 kept, 0 broken** |
| `mypy` (gate CI, `--follow-imports=silent`) | **Success: no issues found in 531 source files** |
| Web `vitest` (`src/features/auto-monitor`) | **24 passed** (7 ficheros; **+2** sobre `22` de `v2.88.50`) |
| `@bolsa/web` `typecheck` / `lint` / `contract:check` | limpio · **0 errores** (`24` warnings pre-existentes) · **OK** |
| `@bolsa/shared` vitest / build | **804 passed** (+1 todo) · limpio |
| `node --test scripts/lib/window-forward.test.mjs` | **25 passed** |
| **`Δ motor = 0` (árbol)** | `git diff` de motor **vacío**; sólo un read-model (`bolsa_application`) + UI + docs |
| **`Δ motor = 0` (CI)** | `Release tag CI` [`37305844986`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37305844986) **VERDE**: `replay-repro` **`REPRODUCIDO`** `1E3ADAC2…` = sello `24066225…` |

---

## 5. Límites declarados (no se cierran aquí)

1. El fix es de **proyección/UI**, no de motor: el hueco de `result` era un read-model; el motor no cambia.
2. `unclassified_fills` es un caso **raro pero real** (fills con `side` no legible): el fix elimina la última vía por la que una cifra de dinero podía viajar junto a un cierre no afirmable.
3. **El modelo semántico NO se implementa aquí:** las 3 correcciones conceptuales se congelan **por escrito**; el piloto sigue como está hasta la migración.
4. **PIT histórico institucional** (listings/delistings/sector) sigue **abierto** (`P3` científico).
5. **REPLAY/OOS ≠ PAPER:** `P3-2`/`P3-3` **ABIERTAS**; `CONFIRMED` **NO** se emite.
6. **`n` pequeño** y banda global que cruza cero (heredado, sin cambios): nada es citable como punto.
7. `formatMonitorFactValue` por sí solo **no** basta para rotar `PARCIAL` sobre un valor no nulo (devuelve el número): de ahí el branch explícito en el timeline, y de ahí la propuesta de `MeasurementValue` único (§9.3 del spec).

---

## 6. Sello

- **Producto:** `V2.88.51-beta`. **Package:** `2.11.51-beta`. **Sin migración** (Alembic head `048_journal_entry_dedupe_key`). **Sin cambio de contrato HTTP.**
- **Ficheros añadidos:** `docs/engineering/spec-auto-ui-semantic-model-1-2026-10-05.md`, `docs/engineering/evidence/v2.88.51/README.md`, esta entrega.
- **Ficheros modificados:** `packages/py/application/src/bolsa_application/auto_operational_monitor.py` (guard de `result`), `packages/py/application/tests/test_auto_operational_monitor.py` (test de regresión), `apps/web/src/features/auto-monitor/auto-cycle-timeline.tsx` (medición del PnL), `apps/web/src/features/auto-monitor/auto-monitor.test.tsx` (2 tests), `package.json` (`2.11.51-beta`), `v2_89`…`v2_97` (`meta.bump`), `scripts/lib/window-forward.mjs` (re-anclaje del freeze), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`.

### 6.1 Cadena de commits y SHAs (auditable)

| Rol | Commit | Árboles |
| --- | --- | --- |
| **Sello funcional** (`feat`) | `b05de1b5` | `apps` `f931a357…` / `packages` `28d2faf4…` |
| Re-anclaje del freeze de la ventana (`chore`) | `fa487409` | pin `commit: b05de1b5` (no mueve árbol) |
| **Commit del tag** | `fa487409` | (mismos árboles que `b05de1b5`) |
| Cita **POST-TAG** (evidencia `§7`) | `3e12ab22` | — |

- **Tag:** `v2.88.51-beta` (**anotado**, objeto `ad878fb1…`) → **`fa487409`**.
- **`Release tag CI`** run [`37305844986`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37305844986) **VERDE** (`attempt 1`, `2026-10-05T11:53:28Z`): **`11 jobs success`** (`python`, `security`, `dr-verify`, `playwright (mock E2E)`, `shared`, `lifecycle-pg`, `a7-gate`, `decision-spine`, `replay-repro`, `frontend`, `certify`) + `playwright (integrated E2E, opt-in)` `skipped` por diseño; `certify` `success`; `python` **`4538 passed / 45 skipped`** (`83.63 s`; **+1** = el test de regresión) con `ruff`/`imports` `4 kept, 0 broken`/`mypy` `531` limpios; `replay-repro` **`REPRODUCIDO`** `1E3ADAC2…` ⇒ **`Δ motor = 0` confirmado por CI**.
- **`GitHub Release`** `v2.88.51-beta` **publicado** (pre-release).

---

## 7. Guion de auditoría desde GitHub (paso a paso)

Todo lo anterior se verifica **sin clonar el repo**:

1. **Objeto inmutable.** Abrir el tag: `https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.88.51-beta` (o `…/tree/v2.88.51-beta`). El commit del tag debe ser **`fa487409`** (árbol funcional `b05de1b5`).
2. **Evidencia cruda dentro del tag.** Leer `docs/engineering/evidence/v2.88.51/README.md`: las **5** afirmaciones falsables con su forma de romperse, la tabla de gates, el detalle del fix y el resumen del modelo semántico.
3. **Cita del CI (fuera del tag, por diseño).** En el **`Release`**: `Release tag CI` `37305844986` **VERDE** con `replay-repro` ⇒ `Δ motor = 0`. La cita larga está también en la evidencia **`§7`**, escrita en `main` en `3e12ab22`. *(Dentro del tag, la evidencia declara la cita como `POST-TAG`: es el límite estructural, no un hueco.)*
4. **El fix, verificado contra el código.** En el árbol del tag, `auto_operational_monitor.py` (`_build_cycle`) debe leer `None if closed is None or closed_measurement != MEASUREMENT_COMPLETE else {...}`, y `auto-cycle-timeline.tsx` debe usar `cycle.closedMeasurement` (no el literal `"COMPLETE"`).
5. **Las dos pruebas del fix (rojo→verde).** `test_cycle_result_not_published_when_close_is_partial_by_unclassified_side` (backend) y los dos casos de `auto-monitor.test.tsx` (UI). Revertir el guard del backend debe **romper** el primero.
6. **`Δ motor = 0` sin re-ejecutar.** En el run `37305844986`, el job `replay-repro` imprime `sha256 1E3ADAC2…` (contenido LF) = sello `24066225…` (`3 445 622 B` CRLF). Si coincide, el motor no se movió.
7. **El modelo semántico.** Leer `docs/engineering/spec-auto-ui-semantic-model-1-2026-10-05.md` dentro del tag: debe contener las **14** etapas, los **dos ejes**, y las tres correcciones (`TOP_N ≠ DECISIÓN`, `SALIDA ≠ LIQUIDACIÓN`, `OPORTUNIDAD` = contexto). **No** debe haberse reescrito `buildAutoOperationStory`.
8. **Doctrina del hueco.** Buscar cualquier `0` donde falta el dato: no debe existir. La cifra de PnL sólo se publica con cierre `COMPLETE`; con `PARTIAL`/`UNKNOWN` se lee `PARCIAL`/`NO MEDIDO`.
9. **Qué NO creer.** Que este sello re-mida algo (§3: cifras heredadas). Que el modelo semántico esté implementado en pantallas (§5.3: es diseño). Que el determinismo valide: no lo hace. Que `formatMonitorFactValue` baste para rotar una medición (§5.7).
