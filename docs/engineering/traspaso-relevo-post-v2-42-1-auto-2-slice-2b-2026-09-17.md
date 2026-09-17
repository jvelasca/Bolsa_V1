# RELEVO — post V2.42/AUTO-2 (slice 2b) · `TIME_EXIT`, `THESIS_EXIT`, ATR real y cierre de H-1..H-7 — 2026-09-17

> **Para quién es esto:** el siguiente agente/persona que continúa la línea **AUTO**. Aquí está el estado
> real tras el slice **2b**, lo que se cerró, lo que **queda** (2c / `AUTO-3`), las trampas medidas, cómo
> verificar y el **freeze** que no se toca.
> **Pack auditado de esta fase:** [`audit-pack-v2.42.1-auto-2-slice-2b-2026-09-17.md`](./audit-pack-v2.42.1-auto-2-slice-2b-2026-09-17.md)
> · **arranque del auditor:** [`arranque-auditor-v2-42-1-auto-2-slice-2b-2026-09-17.md`](./arranque-auditor-v2-42-1-auto-2-slice-2b-2026-09-17.md).
> **Relevo anterior (2a, con las decisiones D1..D6 firmadas por el owner):** [`traspaso-relevo-post-v2-42-auto-2-2026-09-17.md`](./traspaso-relevo-post-v2-42-auto-2-2026-09-17.md).
> **Roadmap:** [`roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md`](./roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md) §4 (`AUTO-2`) y §5 (`AUTO-3`).
> **Base:** [`audit-pack-v2.42-auto-2-position-lifecycle-2026-09-17.md`](./audit-pack-v2.42-auto-2-position-lifecycle-2026-09-17.md)
> (2a). Su **§9** son los siete hallazgos que 2b cierra: están cerrados, no los reabras sin medir.

**Bump:** `1.67.0-beta` → **`1.67.1-beta`** (tag nuevo `v2.42.1-beta`; `1.68.0-beta` sigue siendo de `AUTO-3`).
**Migración: NINGUNA** (Alembic head sigue en `042_portfolio_reservations`).

---

## 0. Estado en una frase

El **criterio de salida completo** de `AUTO-2` ya está implementado y probado **salvo la evidencia de
journal de un día completo**: las tres deudas del slice (tiempo, tesis, ATR real) están **cerradas con
gate** (E1 con techo **congelado** en el JSONB, E3 con la invalidación confirmada **vendiendo** — D2
firmada —, E2 con ATR real **declarado** y veto **OFF** por decisión D3) y los **siete hallazgos** de la
auditoría de 2a (H-1..H-7) están cerrados con **13/13 mutaciones en rojo**. Lo que queda para la fase
siguiente es **medir el resultado en un día real** (journal de `time_exit`/`thesis_exit`), llevar el
**régimen** al FSM como evento con motivo propio y, ya en `AUTO-3`, el `RISK_EXIT` y el gobernador.

---

## 1. Contexto mínimo indispensable (verificado en código)

### 1.1 Qué es este proyecto

- Monorepo TS + Python. Todo el motor AUTO vive en Python (`packages/py/*` + `apps/api-python`).
- `AUTO` ejecuta **en simulado** (paper). `LIVE` está bloqueado por dos barreras independientes.
- La gestión de posición del camino `AUTO_ENGINE_SIM_V2=1` es la cadena
  `Strategy → TradePlan → ProtectionPlan → PositionState → PositionManager (FSM) → ExitPlan → PositionDecision`.

### 1.2 La cadena de gestión de posición (anclajes reales, post-2b)

| Paso                      | Fichero / símbolo                                                                                         | Nota                                                                               |
| ------------------------- | --------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| Nacimiento de la posición | `auto_simulation_worker._v2_track_entry` → `position_state.build_position_state_from_fill`                | aquí se **congelan** `holdingDeadlineAt` (E1) e `invalidationPrice` (E3)           |
| Adopción (reinicio)       | `_v2_adopt_position` → `build_position_state_from_fill`                                                   | el techo y el nivel de invalidación se **reconstruyen una vez** y no se recalculan |
| Gestión por tick          | `_v2_position_package` → `plan_v2_position_outcome` (`auto_v2_entry`) → `exit_plan` / `position_decision` | recibe `now` **y** `expires_at` (sin ambos, `TIME_STOP` no puede dispararse)       |
| Decisión                  | `position_decision._action_from_plan`                                                                     | `THESIS_INVALIDATION` ⇒ **`EXIT`** (D2); bajo `CRITICAL` recon ⇒ veto declarado    |
| FSM                       | `position_lifecycle.apply_lifecycle_event` / `advance_lifecycle`                                          | `TIME_EXIT`/`THESIS_EXIT` ⇒ `EXIT_PENDING`; escalera **forward-only** (H-7)        |
| Journal                   | `auto_simulation_worker._v2_journal_exit_request` / `_v2_apply_stop_update` / `_v2_signals`               | `time_exit`, `thesis_exit`, `protect_requested`, `atr_geometry`                    |
| Marca durable             | `_mark_observation_changed` + `apply_position_mark`                                                       | persiste pico y `maeR` cuando cambian (dos sensores, H-2)                          |
| ATR                       | `auto_v2_entry.AtrSource` / `_v2_atr_geometry` / `atrRequired`                                            | origen declarado (`real`/`fallback`/`missing`)                                     |
| Durabilidad               | `sim_auto_positions.position_state` (JSONB, migración `040`)                                              | mismo JSONB que 2a; **sin** migración nueva                                        |

### 1.3 Invariantes que NO se tocan (violarlos = fallo de la tarea)

- `AUTO ⇒ SIMULATED`. `LIVE` bloqueado (`LIVE_EXECUTION_AUTHORIZED` + `LIVE_EXECUTION_UNLOCKED` false).
  **Cero caminos LIVE nuevos.**
- `AUTO_ENGINE_SIM_V2` sigue **OFF por defecto**; con el flag sin definir el comportamiento debe ser el de
  `v2.39.x` (lo sostiene `protection_compat.py` + los 9 tests legacy portados).
- RiskGate / SimulationGate / Ledger / Reconciliation **deterministas**; **sin LLM en el hot path**.
- **Fail-closed**: ausencia de evidencia ≠ aprobación. **Ninguna salida protectora se veta jamás** por
  reconciliación ni por medición (`_PROTECTIVE_EXIT_REASONS`).
- **Una posición siempre tiene estado persistido y verificable**; un estado no verificable degrada a
  `RECONCILIATION_REQUIRED` (+ `PROTECTION_MISSING` si además no hay stop), **nunca** a "sin protección".
  (H-6 cerrado: `lifecycleState: null` **explícito** también degrada.)
- **El techo de tiempo se congela en el nacimiento y es inmutable** (E1): ningún camino lo recalcula.
- **La invalidación confirmada de la tesis vende** (D2, firmado): `EXIT` real, no `REVIEW`; y un stop-out
  **no** se atribuye como salida por tesis.
- **El ATR sintético se declara como tal**; con `AUTO_ENGINE_SIM_V2_ATR_REQUIRED=1` una señal sin ATR real
  **no entra** (fail-closed, default OFF).
- **El stop nunca empeora** (clamp _never-worsen_) y **todo `PROTECT` con efecto deja traza** (H-2 cerrado).
- **Sin pico declarado no hay trailing** (H-4) y `PARTIAL_EXIT` **no** arma el trailing (H-3).
- **El FSM es forward-only** (H-7) y `RECONCILED` exige degradado de origen + estado verificado +
  coherencia con la cantidad (H-1).
- Migraciones **aditivas/nullables, sin backfill**, con `downgrade()` completo, **sin** ENUM de PG.
- `POSITION = Σ APPLIED` y `exit_qty <= materialized_qty`. Long-only intacto.
- **No editar** los ficheros de plan de Cursor en `~/.cursor/plans/`.

---

## 2. Qué acaba de cerrar el slice 2b (la base sobre la que arrancas)

Resumen operativo; el detalle auditado (con la matriz de mutación medida) está en el
[audit-pack v2.42.1](./audit-pack-v2.42.1-auto-2-slice-2b-2026-09-17.md).

1. **E1 · `TIME_EXIT`** — `resolve_holding_horizon` (plantilla de política, con
   `DEFAULT_MAX_HOLDING_PERIOD_DAYS`) y el techo **congelado** en `holdingDeadlineAt`; la gestión recibe
   `now`+`expires_at`; vencido ⇒ venta real con `time_exit` y FSM `EXIT_PENDING`.
2. **E3 · `THESIS_EXIT`** — nivel de invalidación congelado del plan o del stop estructural;
   `is_thesis_invalidated` decide sobre el **peor adverso persistido**; D2: la invalidación confirmada
   **vende**; el motivo se toma del **motivo decisorio** (un stop-out no se disfraza).
3. **E2 · ATR real** — `AtrSource` (barras → ATR, fail-closed sin barras); el worker **declare**
   `atrSource`; `atr_required` (env `AUTO_ENGINE_SIM_V2_ATR_REQUIRED`, default OFF) veta con
   `atr_unknown`.
4. **H-1..H-7 cerrados** — `RECONCILED` estricto, `PROTECT` no mudo + marca durable, `PARTIAL_EXIT` sin
   armar trailing, sin pico no hay trailing, `math.isfinite`, `lifecycleState: null` degrada, escalera
   forward-only.
5. **Red de seguridad** — 11 tests hermeticos nuevos de worker
   (`apps/api-python/tests/test_auto_v2_lifecycle_clock_thesis.py`), 6 PG de durabilidad y 13 mutaciones
   medidas en rojo; cableado explícito en los dos workflows.

---

## 3. Anatomía **REAL** de la gestión de posición hoy (post-2b)

### 3.1 Lo que sí existe

- FSM persistido y forward-only, con `TIME_EXIT`/`THESIS_EXIT` entre los eventos de gestión.
- Ratchet real con clamp nunca-empeorar, `PROTECT` con traza y marca durable (pico + `maeR`).
- Techo de mantenimiento congelado e immutable; invalidación congelada y juicio sobre hechos persistidos.
- ATR real cableado, declarado en el journal y veto disponible detrás de flag.
- Degradación fail-closed con puerta estricta de salida (`RECONCILED` verificado).

### 3.2 Los huecos que quedan (esto ES la fase siguiente)

1. **Evidencia de un día completo (criterio de salida de `AUTO-2`)** — el roadmap §4 pide
   `TIME_EXIT`/`THESIS_EXIT` **con evidencia en el journal de un día completo**. Hoy la evidencia es de
   test (hermetico + PG). Falta: corrida golden de un día con al menos una posición que **venza** por
   tiempo y otra cuya tesis se **invalide**, y contar los motivos en el journal.
2. **El régimen no es un evento del FSM** — `REGIME_EXIT` existe en el camino legacy
   (`position_manager.manage_position`, con **precedencia absoluta**) y está probado, pero en el camino
   V2 el régimen entra como sesgo de planificación, **no** como salida con motivo propio en el FSM. Un
   `REGIME_EXIT` de primera clase (evento + journal) es trabajo pendiente del `AUTO-2` o, más
   naturalmente, de `AUTO-3` (regímenes en 3 dimensiones).
3. **`RISK_EXIT`** — no existe como motivo; llega con el gobernador de riesgo de `AUTO-3` (roadmap §5, §11).
4. **El veto de ATR está OFF** (D3: cablear + medir y **solo después** vetar). Medir el % de señales con
   ATR real antes de flipear es el siguiente paso natural; los contadores por origen son **medición
   interna** (los leen los tests, no se publican).
5. **`RECONCILED` sigue sin emisor** en el camino del worker: H-1 endurece la puerta, no la abre. La
   resolución real de una degradación (reconciliación con el bróker/ledger) es trabajo de una fase
   posterior, no de `AUTO-2`.
6. **Política de horizonte por estrategia** — hoy el horizonte viene de la **plantilla**; una política
   por estrategia (no por template) no existe.

### 3.3 Trampas medidas (landmines que te van a morder)

- **Dos fuentes de marca**: el pico y el `maeR` son **sensores independientes**. Un test que sólo mueva
  uno deja verde una mutación que rompe el otro (pasó con M10/M13). Si tocas `_mark_observation_changed`,
  cubre **los dos** casos (pico favorable sin memoria en R, y un segundo extremo adverso con el pico quieto).
- **Mutaciones que se tapan entre sí**: dos superficies que hacen lo mismo (p. ej. `suggested_action`
  frente a la rama del decider) dejan mutaciones verdes que **no** son agujeros de cobertura. Antes de
  declarar "cobertura OK", comprueba que la mutación **cambia el resultado**, no la línea.
- **`plan_v2_tick` recibe `tunables`, no `config`**: el argumento por keyword se renombró; un test viejo
  que use `config=` revienta con `TypeError` (ya corregido en `test_auto_v2_entry.py`).
- **El journal ya no empieza por la decisión**: `atr_geometry` puede precederla. Un test que asuma
  `journal[0]` es frágil: busca por contenido, no por índice (pasó en
  `test_v2_journal_records_reason_codes`).
- **Un skip mudo no certifica**: los ficheros PG deben seguir en el `--ignore` de los jobs **offline** y
  correr con `AUTO_V2_LIFECYCLE_PG_REQUIRED=1` (gate fail-if-skipped). No los quites del `--ignore` para
  "tener más verde": en una máquina sin PG **cuelgan** (DSN que no responde ni rechaza).
- **`connect` puede colgarse, no fallar**: el DSN de esta máquina no rechaza; se queda. Si un bloque de CI
  local "tarda para siempre", sospecha de un fichero PG que no está en el `--ignore`. `offline_ci_run.py`
  ya ignora `*_pg.py` y `*_pg_*.py`.
- **`--noconftest`** en las corridas locales evita depender del fixture de limpieza de sesión (que habla
  con PG). No lo uses para "arreglar" un rojo real.
- **Mide con la lista EXTRAÍDA del YAML, nunca con una copia a mano.** El wiring de 2b llegó a incluir en
  `python-ci.yml` una ruta **inexistente** (`packages/py/application/tests/test_auto_v2_lifecycle_clock_thesis.py`:
  el fichero vive en `apps/api-python/tests`); con la invocación de pytest eso es **exit 4** y habría puesto
  el job **rojo**. Lo cazó el verificador de rutas del runner al re-medir desde el YAML. Cualquier runner
  local que use una copia manual puede dar verde midiendo **otra cosa** que CI: si una mutación o un typo
  no aparece, sospecha de la lista antes que de la suite.

---

## 4. Alcance sugerido de la fase siguiente y decisiones abiertas

**Recomendación (una sola frase):** cierra `AUTO-2` con **evidencia** (slice 2c corto: corrida golden de
un día con `time_exit` y `thesis_exit` en el journal + medición del ATR real) y **después** abre `AUTO-3`
(gobernador de riesgo + regímenes + `RISK_EXIT`).

| #   | Decisión                                                       | Recomendación                                                                                                                     |
| --- | -------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| C1  | ¿El día completo se cierra como slice 2c o dentro de `AUTO-3`? | **2c corto** (docs + corrida golden), porque es el **criterio de salida** que el roadmap ya escribió para `AUTO-2`                |
| C2  | ¿Se flipea el veto de ATR ya?                                  | **No**: primero medir (% de señales con ATR real en un día golden). Fliparlo sin medir cambia el número de entradas sin evidencia |
| C3  | ¿`REGIME_EXIT` como evento del FSM en 2c o en `AUTO-3`?        | **`AUTO-3`**, junto con los regímenes en 3 dimensiones (evita dos rediseños del FSM)                                              |
| C4  | ¿Se abre ya una migración para el estado?                      | **No**: el JSONB aguanta el techo y la invalidación (D5 de 2a sigue vigente)                                                      |
| C5  | ¿Se puede declarar `AUTO-2` cerrado tras 2c?                   | **Sí**, con dos deudas declaradas: `REGIME_EXIT` de primera clase y emisor de `RECONCILED` (fases posteriores)                    |

**Nada de esto exige firma del owner salvo C2** (flipar el veto cambia el número de entradas ⇒ dinero).

---

## 5. Infraestructura: CI y gates

- `python-ci.yml` → job `quality`: pase de `packages/py/*` + `apps/api-python/tests` (directorio completo)
  con lista de `--ignore` para los ficheros PG; el fichero hermetico nuevo
  (`apps/api-python/tests/test_auto_v2_lifecycle_clock_thesis.py`) lo **cubre ese pase de directorio** — no
  se lista por fichero, y **no** debe listarse bajo `packages/py/application/tests` (una ruta inexistente
  hace fallar pytest con exit 4: pasó y se corrigió antes del sello) — más el gate `auto-v2-durable-pg` con
  `AUTO_V2_LIFECYCLE_PG_REQUIRED=1`.
- `release-tag-ci.yml` → job `python`: el mismo fichero hermetico **explícito** en su lista por fichero
  (aquí no basta el pase de directorio: la lista del tag es por fichero, salvo los directorios que sí
  recolecta); bloque `lifecycle-pg` con PG real.
- Los **6 tests PG nuevos** viven en `apps/api-python/tests/test_auto_v2_lifecycle_pg.py` y **un skip es
  un fallo**.
- Alembic head: **`042_portfolio_reservations`** (2b no añade migración).

---

## 6. Cómo verificar SIEMPRE antes de decir "hecho"

```bash
# 1) Calidad (invocación EXACTA de CI: SIN `packages/py/analytics/src`, que CI no compila).
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
    packages/py/application/src apps/api-python/src --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter

# 2) Hermeticos del slice (segundos)
uv run pytest packages/py/analytics/tests/test_position_lifecycle.py \
    packages/py/analytics/tests/test_exit_plan.py packages/py/analytics/tests/test_position_decision.py \
    packages/py/application/tests/test_auto_v2_entry.py packages/py/application/tests/test_position_manager.py \
    packages/py/application/tests/test_v127_golden_path_fail.py \
    apps/api-python/tests/test_auto_v2_lifecycle_clock_thesis.py \
    apps/api-python/tests/test_auto_v2_worker_integration.py -q

# 3) Offline del job `quality`: EXTRAE la lista y los --ignore del propio YAML y ejecutala tal cual
#    (si tu DSN cuelga, mantén los ficheros PG en el --ignore: en CI saltan, aquí se quedan colgados)

# 4) PG de certificación (Postgres 16 local). Un skip es FALLO.
AUTO_V2_LIFECYCLE_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_auto_v2_lifecycle_pg.py -q

# 5) Matriz de mutación (13 mutaciones, 13 rojos). Si alguna no cae, falta el test que la mata.
```

**Verificado en el árbol final de 2b:** `ruff` limpio · `mypy` **487 ficheros / 0** · `lint-imports`
**4/4** · bloque offline del job `quality` **1914 passed / 0 failed / 0 skipped** (y **1925** en el job
`python` del tag), con la lista **extraída del YAML** y verificación de existencia de cada ruta · matriz
**13/13 rojos**. **PG real no
medido en local** (motivo medido: el `connect` cuelga) ⇒ la evidencia es de CI.

---

## 7. Uso sugerido de subagentes

- **explore (very thorough)**, antes de escribir nada: mapa real de `_v2_position_package` →
  `plan_v2_position_outcome` → `exit_plan`/`position_decision`, y de `_v2_journal_exit_request`. Verifica
  los números de línea: **el código se mueve**.
- **explore (medium)**: inventario de consumidores de `holdingDeadlineAt`, `invalidationPrice`,
  `atrSource`, `time_exit`/`thesis_exit` (para no dejar lectores huérfanos).
- **generalPurpose**: cambios que cruzan worker + application + analytics manteniendo el camino con
  `AUTO_ENGINE_SIM_V2` **off** (shim).
- **ci-investigator**: si un run de CI falla.
- **bugbot** / **security-review**: **solo** si el owner los pide explícitamente.
- **Para mutaciones: `git worktree add`** — nunca mutes el árbol vivo mientras otro agente lo lee (el
  error de proceso de la auditoría de 2a).

---

## 8. Checklist de arranque (haz esto primero)

- [ ] `git log --oneline -8` → busca la cabecera del **sellado de 2b** (commit de fase + tag
      `v2.42.1-beta` + docs de cierre). **Encima del tag puede haber docs-only**: lo que importa es que
      **entre el tag y tú no haya un commit de código**.
- [ ] Lee el **§6 (límites declarados)** del audit-pack de 2b: es la lista honesta de lo que **no** está
      medido (empezando por PG local).
- [ ] `git status --short` → **vacío** (el ruido de `logs/`, `__pycache__/` o `.pytest_cache/` es de tus
      propias pruebas).
- [ ] `git tag -l -n5 v2.42.1-beta` → tag anotado con el bump `1.67.1-beta`.
- [ ] `package.json` → **`1.67.1-beta`**. `1.68.0-beta` es de `AUTO-3`.
- [ ] Head de Alembic → **`042_portfolio_reservations`** (2b no añadió migración).
- [ ] `git stash list` → hay un stash **ajeno y antiguo** (`all-v170`). **No lo toques.**
- [ ] `AUTO_ENGINE_SIM_V2_ATR_REQUIRED` → **no** definido en el entorno (default OFF); si lo activas para
      medir, déjalo como estaba.
- [ ] Decisiones abiertas de §4: sólo **C2** (flipar el veto de ATR) exige firma del owner.

---

## 9. Freeze (copiar en cualquier sesión)

`AUTO ⇒ SIMULATED` · LIVE bloqueado (`LIVE_EXECUTION_AUTHORIZED` + `LIVE_EXECUTION_UNLOCKED` false) ·
`AUTO_ENGINE_SIM_V2` **OFF por defecto** · `PAPER_D_EXECUTE` off · sin LLM en hot path · fail-closed
(ausencia de evidencia ≠ aprobación) · **ninguna salida protectora se veta jamás** por reconciliación ni
por medición · migraciones aditivas/nullables sin backfill con `downgrade()` completo y **sin ENUM de PG** ·
long-only · Alembic head **`042_portfolio_reservations`** · **`POSITION = Σ APPLIED`** y
**`exit_qty <= materialized_qty`** · **no existe aprobación sin reserva ni reserva sin liberación** ·
`RETRY`/`CAPTURED`/`APPLYING`/`FAILED` **nunca** son posición ni realizado · **ningún `PROTECT` con
efecto queda mudo** (`AUTO-2` 2b) · **una posición siempre tiene estado persistido y verificable; un
estado no verificable degrada a `RECONCILIATION_REQUIRED`, nunca a "sin protección"** — incluido
`lifecycleState: null` explícito (`AUTO-2` 2b) · **el FSM es forward-only**: ninguna transición
retrocede de estado (`AUTO-2` 2b) · **el stop nunca empeora** · **el techo de tiempo se congela en el
nacimiento y es inmutable**; **la invalidación confirmada vende** (`EXIT`, no `REVIEW`) y **un stop-out
no se confunde con salida por tesis**; **el ATR sintético se declara** y con
`AUTO_ENGINE_SIM_V2_ATR_REQUIRED=1` **no entra** · **la política de salida tiene una sola fuente**
(`resolve_exit_policy`; sin plantilla ⇒ `MODERATE 0.3/0.3`).

**No hacer:** tocar las barreras LIVE · añadir un segundo motor de trading/FSM · leer
`position_state`/`position_states` como autoridad de posición · contabilizar la cantidad **pedida** ·
dejar dos fuentes de verdad del estado de posición · retirar el shim sin portar los 9 tests legacy ·
congelar el stop otra vez · elegir la identidad de un test que necesite fill **al azar** · certificar sin
correr los bloques de §6 · declarar CI de un tag que aún no existe · meter ruido de `logs/` y caches en un
commit · editar los ficheros de plan de Cursor en `~/.cursor/plans/` · **mutar código en el árbol vivo
mientras otro auditor lo lee** (usa `git worktree add`) · reutilizar una cifra de un documento sin
re-medirla · **afirmar que PG se midió en local** cuando el `connect` se cuelga.
