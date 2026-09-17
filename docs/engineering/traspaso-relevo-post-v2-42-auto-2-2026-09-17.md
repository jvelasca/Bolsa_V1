# RELEVO — post V2.42/AUTO-2 (slice 2a) · Position Lifecycle FSM & Real Protection — 2026-09-17

> **Para quién es esto:** la persona (o el agente) que continúa la línea `AUTO` **después** de que
> `V2.42 / AUTO-2` (slice **2a**) quedara cerrado y sellado. No es un resumen de méritos: es el mapa
> de lo que ya existe, de lo que **no** existe todavía (eso es tu trabajo: el slice **2b**) y de las
> trampas que ya han mordido.
> **Pack auditado de la fase:** [`audit-pack-v2.42-auto-2-position-lifecycle-2026-09-17.md`](./audit-pack-v2.42-auto-2-position-lifecycle-2026-09-17.md)
> · **Guía de auditoría:** [`arranque-auditor-v2-42-auto-2-position-lifecycle-2026-09-17.md`](./arranque-auditor-v2-42-auto-2-position-lifecycle-2026-09-17.md).
> **Base sobre la que se asienta:** [`audit-pack-v2.41-auto-1-portfolio-reservation-2026-09-17.md`](./audit-pack-v2.41-auto-1-portfolio-reservation-2026-09-17.md)
> (AUTO-1) y [`audit-pack-v2.40.5-auto-1a-position-materialization-2026-09-17.md`](./audit-pack-v2.40.5-auto-1a-position-materialization-2026-09-17.md)
> (`POSITION = Σ APPLIED`).
> **Hoja de ruta:** [`roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md`](./roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md) §4.
> **Estado de la evidencia:** commit de fase `6e53294f` (17 ficheros, `+2914/−99`) y commit de
> arreglo de test `35e38c24` (1 fichero, `+59/−1`); el tag anotado **`v2.42-beta` → `35e38c24`**.
> CI: `Python CI` **GREEN** en `main` @ `35e38c24` (run [`35214904914`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35214904914),
> 5/5: `quality`, `auto-v2-durable-pg`, `lifecycle-pg`, `paper-forward-pg`, `grammar-discovery-pg`) y en
> la ref del tag (run [`35214985401`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35214985401), 5/5);
> `Release tag CI` **GREEN** @ `v2.42-beta` → `35e38c24` (run [`35214985392`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35214985392),
> 10 jobs ejecutados + `certify` (**9 requeridos**, más 1 opt-in `skipped` por diseño)). **Declarado, no escondido:** el primer sellado del tag (commit de fase
> `6e53294f`, run `35213906948`) puso **rojo** `auto-v2-durable-pg` — el test durable V2 **sorteaba**
> instrumento (lotería de la cola SIM) y el mismo commit había pasado 5/5 minutos antes en `main` (run
> `35213904170`) ⇒ **flaky preexistente, no regresión**; por eso `35e38c24` es test-only y el tag se
> **re-apuntó** a él.
> **Procedencia de las cifras de job:** en CI (`quality`) el comando del job da `1869 passed, 38 skipped`
> y en el `python` offline del tag `1880 passed, 35 skipped`; las cifras "redondas" con **0 skipped** que
> verás en packs de fases anteriores se midieron con `DATABASE_URL` y los `*_PG_REQUIRED` exportados
> (suites gated corriendo de propina). **La cifra que manda es la de CI.**
> **Sonda de referencias** (`apps/api-python/scripts/a9_doc_refs_probe.py`) sobre los tres documentos de
> la fase: `98 referencias comprobadas / 0 muertas`; destapó y corrigió un enlace muerto **de este mismo
> documento** (`arranque-auditor-v2.42-…` frente al nombre real `…-v2-42-…`). **Ojo:** la sonda valida
> rutas, **no** anclas de sección (una `§7.2` inexistente pasa la sonda).
> **Auditoría externa (2026-09-17):** sin P0; **7 hallazgos de código** declarados en el §9 del pack como
> criterio de aceptación de 2b, más la errata de mis cifras. Reprodujo 5 mutaciones (M1, M3, M4, M5, M7)
> con los rojos exactos.
> **Nota de artefacto:** la anotación del tag `v2.42-beta` (`git tag -n5`) enumera estados **en prosa** y
> nombra `REDUCED`, que **no existe** en el FSM: los 13 estados reales son los de
> `position_lifecycle.py`. La prosa del tag no es la fuente (y no se re-escribe un tag ya publicado).

**Bump:** `1.66.0-beta` → `1.67.0-beta`. **Migración: NINGUNA** (Alembic head sigue en
`042_portfolio_reservations`: el ciclo de vida vive en el JSONB `sim_auto_positions.position_state`).

**Alcance de lo cerrado (2a):** FSM explícito y persistido + `PROTECT`/trailing real (el `stop_update`
que se **descartaba** ahora se aplica, se persiste y se journaliza) + retirada de `ProtectionConfig`
como motor del camino AUTO (queda un shim de compatibilidad) + política T1/T2 en **una sola fuente**.

**Fuera de lo cerrado (2b, es tu trabajo):** `TIME_EXIT`, `THESIS_EXIT`, **ATR real**,
**horizonte de tiempo** y, si toca, migración `043`. El **criterio de salida completo** de `AUTO-2`
**no** está cumplido: el roadmap exige `TIME_EXIT`/`THESIS_EXIT` **con evidencia en el journal de un
día completo**, y eso no existe todavía.

---

## 0. Estado en una frase

La posición AUTO **ya no es un número con un stop congelado**: tiene un estado explícito persistido
(`OPEN → PROTECTED → T1_REACHED → PARTIAL_EXIT → TRAILING → EXIT_PENDING → CLOSED`, más la familia
degradada), el stop **hace ratchet real** (nunca empeora, trailing medido en `R`), hay **un solo
motor de protección** y una salida protectora **nunca** se veta; lo que **no** existe todavía es el
**resto del ciclo de vida**: no hay salida por **tiempo**, no hay motor de **tesis** (`thesis_health`
sigue siendo el stub `{"status": "none"}`) y el ATR de AUTO sigue siendo **sintético**
(`precio × 2 %`). Eso es `AUTO-2` slice **2b**.

---

## 1. Contexto mínimo indispensable (verificado en código)

### 1.1 Qué es este proyecto

Monorepo de una plataforma de bolsa personal (IBEX/Europa). Relevante para esta continuación:

- `packages/py/domain` — dominio puro.
- `packages/py/application` — casos de uso: orquestador del ciclo, stores durables, ejecución/ledger
  y toda la cadena **AUTO 2.0**.
- `packages/py/analytics` — motor determinista y `cognitive/` (puros, sin red): `position_state`,
  `position_decision`, `exit_plan`, `exit_policy`, `risk_allocator`, `portfolio_reservation`,
  `position_ledger` y el nuevo `position_lifecycle`.
- `packages/py/infrastructure` — SQLAlchemy + Alembic (PostgreSQL). `tables.py` es el espejo ORM.
- `apps/api-python` — API, **workers de fondo AUTO** y los E2E de certificación con PG real.

### 1.2 La cadena AUTO 2.0 y dónde vive la gestión de posición (anclajes reales, post-2a)

```
tick AUTO (auto_simulation_worker.auto_turn; runtime: AutoSimRuntime.run_tick ~L3283)
  → _advance()  (self._minute += 1; el seed del venue depende del minuto)
  → plan_v2_tick (auto_v2_entry) → PortfolioDecision + PortfolioReservation      [AUTO-1]
  → orden (venue_order_id namespaced) → _settle ~L899 (SIM; seed L932)
      → execution_events.status = APPLIED | RETRY | ...                          [AUTO-1A]
  → _v2_track_entry ~L2329 / _v2_track_reduce ~L2373 → self._v2_positions[symbol]
        · _v2_track_entry  escribe el estado de nacimiento (plan + stop) y su FSM
        · _v2_track_reduce marca trailing (`mark_trailing="target_1" in exit_reasons`)
  → gestión: _v2_position_package ~L2115 (async)
        → plan_v2_position_outcome / position_manager_package / manage_position_outcome
        → _v2_apply_stop_update ~L2193  ← AQUÍ se aplica y se persiste el ratchet
        → _journal_position_event ~L2296 (PROTECT, transiciones rechazadas, degradación)
  → persistencia durable: sim_auto_positions.position_state (JSONB; sin migración)
  → re-arranque: _v2_restore_durable_position ~L2075 / _v2_adopt_position ~L1949
        → _v2_degrade_adoption ~L2036 (fail-closed: RECONCILIATION_REQUIRED + PROTECTION_MISSING)
```

> **Lo que la auditoría externa del 2026-09-17 encontró (y es tu trabajo en 2b):** 7 puntos donde el
> código es **más débil que la prosa** del pack. Están listados con evidencia y criterio de aceptación en
> el **§9 de [`audit-pack-v2.42-auto-2-position-lifecycle-2026-09-17.md`](./audit-pack-v2.42-auto-2-position-lifecycle-2026-09-17.md)**;
> resumen: **H-1** `RECONCILED` se acepta desde cualquier estado sin verificar (`position_lifecycle.py:359-377`),
> **H-2** no-op del trailing sin journal (`worker:2283-2293`), **H-3** `PARTIAL_EXIT` arma trailing sin T1
> (`position_lifecycle.py:530`), **H-4** sin pico cae al precio de entrada, **H-5** `+inf` pasa y revienta
> en `round()`, **H-6** `lifecycleState: null` con `status=CLOSED` y posición viva no degrada,
> **H-7** 7 transiciones retroceden. **No los arregles de forma aislada**: entran en 2b con su propio
> gate y su propia matriz de mutación.

Rutas exactas que hay que leer antes de diseñar 2b:

| Qué                                    | Dónde                                                                                                                                                                                                                                                                              |
| -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **FSM (nuevo, puro)**                  | `packages/py/analytics/src/bolsa_analytics/cognitive/position_lifecycle.py` (629 líneas)                                                                                                                                                                                           |
| · estados / eventos                    | `PositionLifecycleState` **L36–50** (13 estados) · `PositionLifecycleEvent` **L52–67** (14 eventos) · `LIFECYCLE_EVENTS` **L185**                                                                                                                                                  |
| · tabla de transiciones                | `_MANAGEMENT_EVENTS` **L113** · `_TRANSITIONS` **L133** (mapa explícito estado → evento → estado) · `apply_lifecycle_event` **L321** · `advance_lifecycle` **L398**                                                                                                                |
| · derivación y proyección              | `derive_lifecycle_state` **L446** · `lifecycle_state_is_consistent` **L205** · `is_open_lifecycle` **L627** · `trailing_status` **L489** (`inactive`/`armed`/`active`)                                                                                                             |
| · stop y trailing                      | `compute_trail_stop` **L533** (clamp _never-worsen_) · `is_trail_armed` **L520** (solo tras T1) · `trailing_state_dict` **L577** · `protection_state_dict` **L596** · `protection_state_name` **L613**                                                                             |
| · conjuntos de estados                 | `VERIFIED_/DEGRADED_/ACTIVE_LIFECYCLE_STATES` **L77–98** · `PROTECTIVE_EXIT_ALLOWED_STATES` **L103** · `PROTECTED_LIFECYCLE_STATES` **L109**                                                                                                                                       |
| `PositionState` (dato)                 | `packages/py/analytics/src/bolsa_analytics/cognitive/position_state.py`                                                                                                                                                                                                            |
| · rehidratación (puerta única)         | `position_state_from_dict` **L336** (estado inconsistente ⇒ degrada) · `mfe_mae` **L286** y `thesis_health` **L287** siguen siendo `dict[str, object]` (el stub `{"status": "none"}` está en **L466**)                                                                             |
| · ratchet de stop (red de seguridad)   | `apply_position_current_stop` **L742** · `does_stop_worsen` **L182** · `apply_position_mark` (pico / high watermark)                                                                                                                                                               |
| **Política de salida (fuente única)**  | `packages/py/analytics/src/bolsa_analytics/cognitive/position_decision.py` (`_PROTECTIVE_EXIT_REASONS`: las salidas protectoras no se vetan; `resolve_exit_policy` es la única resolución)                                                                                         |
| Fracciones T1/T2                       | `packages/py/analytics/src/bolsa_analytics/cognitive/exit_policy.py` (`CONSERVATIVE` 0.5/1.0 · `MODERATE` **0.3/0.3** · `AGGRESSIVE_SWING` 0.0/0.3). **Sin plantilla ⇒ MODERATE** (declarado, ya no el fallback 0.5/1.0)                                                           |
| **Shim legacy (flag OFF)**             | `packages/py/application/src/bolsa_application/protection_compat.py` (148 líneas): un motor con modos pct/r, evalúa **trailing antes de T1**, y traduce los motivos legacy a eventos del FSM. `ProtectionConfig` **ya no es motor**; el alias histórico vive en el worker **L240** |
| `ExitPlan` / motores de salida         | `packages/py/analytics/src/bolsa_analytics/cognitive/exit_plan.py` (`ExitReason` **L17–28**, `EXIT_REASON_PRECEDENCE` **L32–44**)                                                                                                                                                  |
| `PositionManager`                      | `packages/py/application/src/bolsa_application/position_manager.py` (`manage_position_outcome` **L187–273**, `REGIME_EXIT` **L60** — ya existe y se emite **L262**)                                                                                                                |
| Surface del stop (nuevo)               | `packages/py/application/src/bolsa_application/auto_v2_entry.py`: `position_manager_stop_update` (el único surface del stop propuesto), `build_position_management_journal_entry`, `regime_exit_only` **L1144**                                                                    |
| Segundo camino de gestión              | `packages/py/application/src/bolsa_application/auto_investment_system.py` (`run_auto_cycle`, +`exit_template` y el mismo `compute_trail_stop`/`is_trail_armed`)                                                                                                                    |
| Reason codes                           | `packages/py/application/src/bolsa_application/auto_reason_codes.py` (+44 líneas: lifecycle/ratchet/protección)                                                                                                                                                                    |
| ATR real (existe, **no** llega a AUTO) | `packages/py/analytics/src/bolsa_analytics/indicators/compute.py` `compute_atr` **L175**                                                                                                                                                                                           |
| Espejo durable de posición             | `sim_auto_positions` (`tables.py`) + `sim_fill_finance_context`; la autoridad en AUTO **es** `sim_auto_positions`, **no** `position_states`                                                                                                                                        |

### 1.3 Invariantes que NO se tocan (violarlos = fallo de la tarea)

- `AUTO ⇒ SIMULATED`. `LIVE` bloqueado (`LIVE_EXECUTION_AUTHORIZED` + `LIVE_EXECUTION_UNLOCKED`
  false). **Cero caminos LIVE nuevos.**
- `AUTO_ENGINE_SIM_V2` sigue **OFF por defecto**; con el flag sin definir el comportamiento debe ser
  el de `v2.39.x` (lo sostiene `protection_compat.py` + los 9 tests legacy portados).
- RiskGate / SimulationGate / Ledger / Reconciliation **deterministas**; **sin LLM en el hot path**.
- **Fail-closed**: ausencia de evidencia ≠ aprobación. **Ninguna salida protectora se veta jamás**
  por reconciliación ni por medición (2a lo convirtió en invariante explícito: `_PROTECTIVE_EXIT_REASONS`).
- **Una posición siempre tiene estado persistido y verificable**; un estado no verificable degrada a
  `RECONCILIATION_REQUIRED` (+ `PROTECTION_MISSING` si además no hay stop), **nunca** a "sin protección".
- **El stop nunca empeora** (clamp _never-worsen_) y **un `PROTECT` nunca es mudo**: se journaliza
  aunque no genere orden (un ratchet no vende).
- Migraciones **aditivas/nullables, sin backfill**, con `downgrade()` completo, **sin** ENUM de PG
  (convención del repo: `String` para estados).
- `POSITION = Σ APPLIED` y `exit_qty <= materialized_qty` (AUTO-1A). `RETRY`/`CAPTURED`/`APPLYING`/
  `FAILED` **nunca** son posición ni realizado.
- No existe aprobación sin reserva ni reserva sin liberación (AUTO-1). Long-only intacto.
- **No editar** los ficheros de plan de Cursor en `~/.cursor/plans/`.

---

## 2. Qué acaba de cerrar AUTO-2 slice 2a (la base sobre la que arrancas)

Resumen operativo; el detalle auditado (con la matriz de mutaciones medida) está en el
[audit-pack v2.42](./audit-pack-v2.42-auto-2-position-lifecycle-2026-09-17.md).

1. **FSM explícito y persistido** en `position_lifecycle.py`: 13 estados, 14 eventos, tabla de
   transiciones **total y auditable** y **rechazo de transiciones inválidas** (una transición no
   declarada devuelve el estado actual y deja rastro `lifecycle_transition_rejected`). El estado
   viaja en `sim_auto_positions.position_state` (`lifecycleState`), **sin migración**.
2. **Rehidratación honesta** (`position_state_from_dict`): un estado inconsistente con la geometría
   o con las señales consumidas **degrada** en vez de inventarse.
3. **Ratchet real**: `position_manager_stop_update` surface el `stop_update` que antes se tiraba;
   `_v2_apply_stop_update` lo aplica (con `apply_position_current_stop`: **nunca empeora**) y lo
   persiste; el trailing se mide en **`R`** (`compute_trail_stop`, widths 0.75/1.0/1.25 R) y solo se
   arma **tras T1**.
4. **Un solo motor de protección**: `ProtectionConfig` fuera del camino AUTO y
   `protection_compat.py` sosteniendo `v2.39.x` con el flag OFF; los 9 tests legacy que lo cubrían
   fueron **portados** (no borrados) a `V2=1`.
5. **Política única T1/T2**: `resolve_exit_policy(exit_template)` es la única resolución en los dos
   caminos de gestión; sin plantilla ⇒ `MODERATE 0.3/0.3` (declarado), nunca el fallback 0.5/1.0.
6. **Adopción fail-closed**: una posición adoptada sin plan durable verificable nace
   `RECONCILIATION_REQUIRED` + `PROTECTION_MISSING` **y se journaliza**; no se publica un stop que
   no existe.
7. **Observabilidad**: `build_position_management_journal_entry` + `_journal_position_event` hacen
   visibles los `PROTECT`, las transiciones rechazadas y las degradaciones (antes mudos).

**Matriz de mutaciones medida (11 mutaciones, rojo en las 11)**: aceptar transiciones inválidas ·
no degradar al rehidratar · perder el clamp _never-worsen_ · descartar el `stop_update` · vetar la
salida protectora con reconciliación `CRITICAL` · no armar trailing tras T1 · adopción no degradada ·
volver al fallback 0.5/1.0 · evaluar T1 antes del trailing en el shim · `PROTECT` silencioso · armar
trailing antes de T1.

**Deuda declarada de 2a (no la reabras sin motivo):** la dualidad `sim_auto_positions` (autoridad en
AUTO) vs `position_states` (camino Confirm) **sigue viva**; la retención de `portfolio_reservations`
(AUTO-1) sigue sin política; `correlation`/`strategy_capacity`/`liquidity_capacity` siguen **no
medidas** en el tick (es AUTO-3/AUTO-4); el generador de drift `schema.prisma` ↔ `pg_indexes` y la
reparación de `execution_events` en `RETRY` históricos siguen pendientes; el **CLI de Alembic ignora
`DATABASE_URL`** en modo online (el camino programático `ensure_migrated` sí lo respeta).

**Hallazgo medido que se declara y NO se arregla aquí** (fuera del alcance del arreglo del test
durable): la barrida `_filling_instrument_id` de
`apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py` **solo verifica el minuto 0**,
pero el seed del venue depende del minuto. Medido: el id que elige hoy
(`inst-a9restart-0000000000`) llena en los minutos 0–6 y **no** en el 7 (y da parcial en el 8). Si la
entrada de ese test cayera en el minuto 7, sería un rojo espurio. La barrida del test durable que sí
se ha arreglado exige llenado en **toda** la ventana; portar ese criterio a la barrida de A9 es una
tarea corta y recomendable **antes** de que muerda.

---

## 3. Anatomía **REAL** de la gestión de posición hoy (post-2a)

### 3.1 Lo que sí existe

- **Estado explícito**: `PositionLifecycleState` (13 estados) + `lifecycleState` persistido en el
  JSONB + proyección de `status` y de `protection_state`/`trailing` tipados (`protection_state_dict`,
  `trailing_state_dict`).
- **Transiciones válidas y auditables** con `advance_lifecycle(position, event, ...)`; el rechazo es
  un hecho observable, no un silencio.
- **Ratchet**: `compute_trail_stop` + `apply_position_current_stop` + persistencia en cada tick;
  `trailing_status` ∈ {`inactive`, `armed`, `active`}.
- **Journal de gestión**: `auto_position_management` (ratos de protección, degradación, rechazos).
- **Degradación fail-closed** por dos vías: adopción (`_v2_degrade_adoption`) y rehidratación
  (`position_state_from_dict`).
- **Invariante de no-veto protector** aplicado en `position_decision.py`.
- **Un shim de compatibilidad** para el flag OFF, con tests legacy portados.

### 3.2 Los huecos que quedan (esto ES `2b`)

1. **`TIME_EXIT` (salida por tiempo)**: no existe en el camino AUTO. `max_holding_period_days`
   existe en `trading_policy`/`operating_policy`/plantillas (**90/45/21 días**) y **no tiene ningún
   consumidor**. Tampoco hay `expected_holding_period`.
2. **`THESIS_EXIT` (motor de tesis)**: no existe. `PositionState.thesis_health` sigue siendo el
   stub `{"status": "none"}` (**position_state.py L466**); `exit_radar.py` (advisory, camino mesa)
   sí tiene una noción de `thesis_exit`, pero **no** la consume AUTO.
3. **`REGIME_EXIT`/`RISK_EXIT`**: `REGIME_EXIT` **ya existe** en
   `position_manager.py` (`REGIME_EXIT` L60, emitido L262) y `regime_exit_only` existe como veto de
   **entrada**; lo que el roadmap pide para `AUTO-2` en esta materia es que la salida por régimen
   forme parte del ciclo de vida completo, y `RISK_EXIT` pertenece de hecho a los gobernadores de
   `AUTO-3`. Léelo en el roadmap §4 y §5 antes de tocar nada.
4. **ATR real**: AUTO sigue entrando con **ATR sintético** (`atr_pct_fallback`):
   worker **L1149–1150** (geometría de entrada), **L1198** (`atr=` del plan), **L1988–1989**
   (geometría de adopción). `compute_atr` existe en analytics y **no** llega a AUTO. El roadmap dice
   literalmente _"sin ATR no hay stop ⇒ `NO ENTRY` cuando la política exija precisión de riesgo"_, y
   eso es un **cambio de comportamiento grande** en producción simulada: confírmalo con el owner y
   **mide cuántas señales caen** antes de activarlo.
5. **Horizonte de tiempo**: sin consumidor (ver 1) y sin transporte en el `TradePlan`.
6. **Migración `043`** (si 2b la necesita): columnas de horizonte/tesis o tabla de transiciones. Si
   el estado cabe en el JSONB + columnas existentes, **no** la crees por inercia (2a no la necesitó).
7. **`mfe_mae`**: sigue siendo un `dict[str, object]` sin esquema tipado (lee §3.3).

### 3.3 Trampas medidas (landmines que te van a morder)

- **`position_manager_package` colapsa `PROTECT` a `None` a propósito** (un ratchet no vende y no
  debe inventar una orden). Si en 2b añades salidas nuevas, **no** las hagas pasar por
  `order_action`: surface el efecto por el canal correcto (el stop va por
  `position_manager_stop_update`; una salida real sí genera orden).
- **Dos caminos de gestión** (worker y `run_auto_cycle`) comparten hoy la política gracias a
  `resolve_exit_policy(exit_template)`. Si 2b introduce una política nueva (horizonte/tesis),
  **resuélvela en un solo sitio** y pásala a ambos; el repo ya pagó el bug de las dos fracciones.
- **`apply_position_current_stop` rechaza stops que empeoran** sin override auditado
  (`does_stop_worsen` + `_is_audited_override`). Es tu red de seguridad: úsala, no la sortees.
- **El `suggested_price` de una venta es `position.current_stop`**: si el stop está mal, el precio
  sugerido está mal. Con 2a el stop ya avanza; no lo vuelvas a congelar.
- **`position_state_from_dict` es la puerta de rehidratación** y el canario está en
  `apps/api-python/tests/test_auto_v2_durable_pg.py` (afirma `plan2.current_stop == plan1.current_stop`
  y la continuidad del `tradePlanId`). Si cambias el _shape_ de `PositionState`, ese test es el
  primero que debe sonar.
- **`TRAIL_ADVANCED` re-verifica estados degradados** a propósito (un trail que avanza es un hecho
  observable sobre una posición viva: vale desde cualquier estado de gestión y **re-verifica** los
  degradados). No lo "arregles" quitándolo de `_MANAGEMENT_EVENTS`.
- **Identidad aleatoria en tests que necesitan un llenado = rojo espurio.** El ruido del venue es
  `sha256(seed, instrument_id, side, ...)` con
  `seed = self._minute * 100_003 + sum(ord(symbol)) % 9999`, y `symbol` es el **id vigilado**
  (`_settle` **L899**, seed **L932**). Medido sobre 5 000 ids de la familia `inst-v2d-<10hex>`:
  **12,74 %** no llenan (el mismo sorteo que el 12,4 % que documentó `v2.40.3` para
  `inst-a9restart-`). Si escribes un test nuevo que necesite un fill, barre una identidad
  determinista que llene en **toda** la ventana de minutos (patrón ya implementado en
  `test_auto_v2_durable_pg.py`: `_filling_instrument_id`).
- **`mfe_mae`/`thesis_health` son dicts `object` sin esquema**: cuando 2b los pueble (tesis), **tipa**
  el contenido y declara la degradación a `UNKNOWN` en vez de dejar un diccionario libre.
- **La autoridad de posición en AUTO es `sim_auto_positions`**, no `position_states` (esa es la del
  camino Confirm). No mezcles.

---

## 4. Alcance declarado de `2b` y decisiones abiertas

### 4.1 Lo que pide el roadmap §4 (texto normativo, lo que falta)

- Salidas nuevas: `TIME_EXIT` (`expected_holding_period` / `max_holding_period`), `THESIS_EXIT`
  (motor de tesis `VALID`/`WEAKENING`/`INVALID` con **condición de invalidación explícita en el
  plan**), `REGIME_EXIT`, `RISK_EXIT`.
- **ATR real**: sin ATR no hay stop ⇒ `NO ENTRY` cuando la política exija precisión de riesgo (el
  fallback `precio × 2 %` queda **solo** para el camino legacy, fuera de AUTO).
- **Criterio de salida de `AUTO-2`** (aún **no** cumplido): `TIME_EXIT`/`THESIS_EXIT` **con evidencia
  en el journal de un día completo**. La otra mitad del criterio (`ProtectionConfig` sin ninguna
  lectura en el camino `AUTO_ENGINE_SIM_V2=1`) **sí** está cumplida por 2a.
- **Gate** (extensión del que ya existe): el cartesiano de eventos debe cubrir **tiempo, tesis,
  régimen y riesgo** además de stop/T1/T2/trailing; el test de reinicio debe rehidratar **cada**
  estado intermedio nuevo; y la certificación de que **ninguna** salida protectora se veta se
  mantiene.

### 4.2 Decisiones que hay que tomar (pregúntalas al owner **antes** de codificar)

1. **¿De dónde sale el horizonte de tiempo?** `trading_policy`/`operating_policy` ya declaran
   `max_holding_period_days`/`min_holding_period_minutes` por plantilla (90/45/21 días) **sin
   consumidor**. Recomendación: que el `TradePlan` los transporte (es el contrato que ya viaja al
   `PositionState`) y que `TIME_EXIT` sea consecuencia del plan, no una constante del worker.
2. **¿Quién evalúa la tesis?** Hay `thesis_health.py` (`map_thesis_health`) y el campo
   `PositionState.thesis_health`. Recomendación: reutilizar + **condición de invalidación explícita**
   en el plan; `AI`/LLM **no** entra en el hot path.
3. **Severidad del ATR real**: convertirlo en `NO ENTRY` es un cambio **grande** de comportamiento
   en simulado. **Mide primero** cuántas señales caen con las barras reales y decide con el número
   delante (¿`NO ENTRY` o `ENTRY_REDUCED`?).
4. **¿Qué es "protección mínima viable" para una posición adoptada** sin estado verificable? Hoy
   degrada a `RECONCILIATION_REQUIRED` + `PROTECTION_MISSING`; con ATR real puede **no haber** stop,
   y hay que decidir si eso obliga a cerrar, a reducir o a mantener con vigilancia.
5. **¿Migración `043` o JSONB?** Si el horizonte y la tesis caben en `position_state`, **no** la
   crees; si creas columnas para consultarlas desde SQL, recuerda el patrón obligatorio del §5.
6. **¿Un solo slice (2b) o dos?** El patrón de AUTO-1/2a (a hermético + b durable) funcionó bien;
   2b es más pequeño que 2a, así que un solo slice con las dos mitades dentro (hermético + PG) es
   defendible.

---

## 5. Infraestructura: migración, store, CI (si el slice lleva migración)

Si 2b necesita esquema nuevo (`043_*`):

- **Patrón obligatorio**: copia la forma de
  `packages/py/infrastructure/alembic/versions/042_portfolio_reservations.py` — docstring largo en
  español con el _por qué_, `revision`/`down_revision` en cadena lineal, constantes de nombres de
  tabla/índice, guardas `_table_exists`/`_column_exists`/`_index_exists`, `upgrade()` con bloques
  numerados y `downgrade()` **completo y simétrico**, `sa.String()` para estados (**nunca** un ENUM
  de PG), `sa.Numeric(18,6)`, `sa.DateTime(timezone=True)`.
- **El baseline `003` NO copia los `Index` de `__table_args__`** (solo FK y `UniqueConstraint`):
  cualquier `Index(...)` nuevo hay que crearlo **explícitamente** en la migración.
- **Espejo 1:1 en `tables.py`** (nombres de índice incluidos).
- **Bumpear la head si añades `043`** (esto **rompe CI si se olvida**):
  `apps/api-python/tests/test_discovery_evidence_snapshot_pg.py` → `_ALEMBIC_HEAD` (hoy
  `"042_portfolio_reservations"`).
- **CI (un test nuevo NO entra solo)**:
  - Test **hermético de application** (`packages/py/application/tests/test_*.py`): añadirlo
    **explícitamente** a la lista del job `quality` (`python-ci.yml`) y a la del job `python` de
    `release-tag-ci.yml`. **Comentarios siempre FUERA del bloque plegado `run: >`** (lección
    `v2.40.2`/`v2.40.3`).
  - Test **de app** (`apps/api-python/tests/…`): entra solo por directorio; `--ignore` solo si
    necesita PG.
  - Test **PG nuevo**: lista del job `auto-v2-durable-pg` (`python-ci.yml`) y/o `lifecycle-pg`
    (`release-tag-ci.yml`), **más** su `--ignore` en los jobs offline, **más** su gate
    `*_PG_REQUIRED: '1'` en el `env:` (un skip silencioso debe ser fallo duro; los jobs ya tienen un
    step «fail on skipped»).

---

## 6. Cómo verificar SIEMPRE antes de decir «hecho»

Orden mínimo, **paridad con CI**. Extrae los comandos del YAML, **no** los reescribas de memoria:

```bash
# 1) Calidad (invocación de CI: SIN `packages/py/analytics/src`, que CI no compila).
#    Corregido tras la auditoría externa: con analytics/src la línea da exit 2 por hallazgos
#    PREEXISTENTES ajenos a la fase, así que etiquetarla "exacta de CI" era falso.
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src \
           packages/py/infrastructure/src packages/py/application/src \
           apps/api-python/src --follow-imports=silent

# 2) Herméticos del slice (segundos)
uv run pytest packages/py/analytics/tests/test_position_lifecycle.py \
              packages/py/application/tests/test_auto_v2_lifecycle_stop.py \
              apps/api-python/tests/test_auto_v2_worker_integration.py -q

# 3) Offline del job `quality`: EXTRAE su lista y sus --ignore del propio YAML y ejecútala tal cual
uv run python -c "import yaml;print(yaml.safe_load(open('.github/workflows/python-ci.yml',encoding='utf-8'))['jobs']['quality']['steps'][-1]['run'])"

# 4) PG de certificación (Postgres 16 local). Un skip es FALLO.
cd packages/py/infrastructure && uv run alembic upgrade head && cd -
AUTO_V2_LIFECYCLE_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_auto_v2_lifecycle_pg.py -q
AUTO_V2_DURABLE_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_auto_v2_durable_pg.py -q   # ×N: es el canario del sorteo
AUTO_SCHEDULER_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_auto_scheduler_real_pg_zero_human_intervention.py -q   # ×30
AUTO_SCHEDULER_PROCESS_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py -q

# 5) Batería completa de paquetes
uv run pytest packages/py -q
```

Reglas de honestidad del repo (no negociables):

- No declares verde sin haber corrido los bloques.
- Distingue fallos **preexistentes** de regresiones tuyas; mide con **A/B** (`git stash` + re-run) y
  con **sondas puras** cuando el fenómeno sea determinista (así se diagnosticó el sorteo del venue).
- No certifices `main`/HEAD como si fuera un tag.
- **Muta tu propio código**: por cada invariante nuevo, aplica una mutación, mide el rojo, revierte y
  **publica la matriz medida**.
- Si un test que **no** es tuyo pone el CI rojo, **no** lo tapes: diagnostícalo, declara el primer
  rojo y arréglalo con su propio commit (`fix(...)`) si el arreglo es de test.

---

## 7. Uso sugerido de subagentes

- **explore (very thorough)**, antes de escribir nada: mapa de la FSM
  (`position_lifecycle.py`), del camino `PositionState → ExitPlan → PositionDecision` y de los dos
  caminos de gestión (worker y `run_auto_cycle`). Esta §1.2 es el atajo, pero **verifica** los
  números de línea: el código se mueve.
- **explore (medium)**: inventario de consumidores de `max_holding_period_days`,
  `thesis_health`, `mfe_mae` y de todo lo que lee `lifecycleState`/`status`, para no dejar
  consumidores huérfanos.
- **generalPurpose**: cambios que cruzan worker + application + analytics manteniendo la semántica
  del camino con `AUTO_ENGINE_SIM_V2` off (shim).
- **best-of-n-runner**: solo si dudas entre dos diseños (p. ej. horizonte en el `TradePlan` vs
  columnas nuevas).
- **bugbot** / **security-review**: **solo** si el owner los pide explícitamente.
- **ci-investigator**: si un run de CI falla y hay que diagnosticarlo.

---

## 8. Checklist de arranque (haz esto primero)

- [ ] `git log --oneline -6` → cabecera de **sellado** (`60a6c984` y `1d6df658`, docs-only) sobre
      `35e38c24` (arreglo de test) sobre `6e53294f` (fase) sobre `15618c0c` (relevo previo). El **tag
      apunta al de arreglo** (`35e38c24`), no al sellado; y como el sellado es docs-only, de su commit
      solo corre `Gitleaks` ⇒ **la evidencia de CI sigue anclada a `35e38c24`**.
- [ ] `git status --short` → **vacío** (si hay ruido de `logs/`, `__pycache__/`, `.pytest_cache/`,
      es de tus propias pruebas).
- [ ] `git tag -l -n5 v2.42-beta` → tag anotado apuntando a `35e38c24`.
- [ ] `git stash list` → hay un stash **ajeno y antiguo** (`all-v170`). **No lo toques**.
- [ ] `package.json` → `1.67.0-beta` (el bump a `1.68.0-beta` es de `AUTO-3`; 2b no lo necesita).
- [ ] Head de Alembic → `042_portfolio_reservations` (2a **no** añadió migración).
- [ ] Lee §3.2 y §3.3 **enteros** y verifica en código **dos** huecos (el de `TIME_EXIT` y el de
      `thesis_health` son los más rentables).
- [ ] Pregunta al owner las **seis decisiones** de §4.2 **antes** de codificar.
- [ ] Mide (no supongas) el impacto del ATR real sobre el número de entradas antes de convertirlo en
      `NO ENTRY`.

---

## 9. Freeze (copiar en cualquier sesión)

`AUTO ⇒ SIMULATED` · LIVE bloqueado (`LIVE_EXECUTION_AUTHORIZED` + `LIVE_EXECUTION_UNLOCKED` false) ·
`AUTO_ENGINE_SIM_V2` **OFF por defecto** · `PAPER_D_EXECUTE` off · sin LLM en hot path · fail-closed
(ausencia de evidencia ≠ aprobación) · **ninguna salida protectora se veta jamás** por reconciliación
ni por medición · migraciones aditivas/nullables sin backfill con `downgrade()` completo y **sin ENUM
de PG** · long-only · Alembic head **`042_portfolio_reservations`** · **`POSITION = Σ APPLIED`** y
**`exit_qty <= materialized_qty`** · **no existe aprobación sin reserva ni reserva sin liberación**
(`reserved_cash == Σ reservas vivas`) · `RETRY`/`CAPTURED`/`APPLYING`/`FAILED` **nunca** son posición
ni realizado · ningún skip de gestión queda mudo (**matiz H-2**: el no-op del trailing no es un skip,
pero hoy tampoco deja journal) · **una posición siempre tiene estado persistido y
verificable; un estado no verificable degrada a `RECONCILIATION_REQUIRED`, nunca a "sin protección"**
(**matiz H-6**: hoy sólo degrada si la clave `lifecycleState` está presente y no nula)
(`AUTO-2`) · **el stop nunca empeora y un `PROTECT` nunca es mudo** (`AUTO-2` slice 2a) · **la
política de salida tiene una sola fuente** (`resolve_exit_policy`; sin plantilla ⇒ `MODERATE 0.3/0.3`).

**No hacer:** tocar las barreras LIVE · añadir un segundo motor de trading/FSM · leer
`position_state`/`position_states` como autoridad de posición · contabilizar la cantidad **pedida** ·
dejar dos fuentes de verdad del estado de posición · retirar el shim sin portar los 9 tests legacy ·
congelar el stop otra vez (ni "simplificar" quitando `apply_position_current_stop`) · elegir la
identidad de un test que necesite fill **al azar** · certificar sin correr los bloques de §6 ·
declarar CI de un tag que aún no existe · meter ruido de `logs/` y caches en un commit · editar los
ficheros de plan de Cursor en `~/.cursor/plans/` · **mutar código en el árbol vivo mientras otro
auditor lo lee** (usa `git worktree add`; ver §9.3 del pack) · reutilizar una cifra de un documento sin
re-medirla (la auditoría de 2a encontró "7/28 citas", "36 ficheros" y "10 jobs requeridos" **falsos**).
