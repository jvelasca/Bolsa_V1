# RELEVO — post V2.41/AUTO-1 · Portfolio Reservation Engine — 2026-09-17

> **Para el agente entrante (con sus subagentes).** Este documento es autocontenido: asume **cero
> contexto previo** más allá de lo que aquí se dice. Léelo entero antes de tocar nada. Respeta el
> estilo del repo: español, fail-closed, sin LLM en hot path, LIVE congelado.
>
> **AsOf:** 2026-09-17 · **Base:** `main` · HEAD **`78416b2c`** (commit docs-only de sellado) ·
> **tag vigente:** `v2.41-beta` → **`e6b0dd5b`** (el tag **no** incluye el commit de sellado:
> patrón del repo, el código certificado en el tag y la guía de lectura en el tip de `main`).
> **Versión de paquete:** `1.66.0-beta` · **Alembic head:** `042_portfolio_reservations`.
> **Fase que arranca:** `V2.42` / **`AUTO-2` — Position Manager 2.0** → bump a **`1.67.0-beta`**.
>
> **Veredicto:** `v2.41-beta` está **sellado y certificado**. `Python CI` en `main` **GREEN** (run
> [`35201047304`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35201047304), 5/5),
> `Release-tag CI` **GREEN** (run
> [`35201538048`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35201538048)) y `Python CI`
> re-disparado por el push del tag **GREEN** (run
> [`35201537986`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35201537986), 5/5). **Árbol
> limpio** (`git status --short` vacío). Nada pendiente de esta fase: **no** hay que sellar AUTO-1
> otra vez.
>
> **Contexto inmediato:** [audit-pack v2.41](./audit-pack-v2.41-auto-1-portfolio-reservation-2026-09-17.md)
> · [arranque auditor v2.41](./arranque-auditor-v2-41-auto-1-portfolio-reservation-2026-09-17.md).
> **Especificación de la fase que arranca:**
> [roadmap AUTO](./roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md) **§4** (`AUTO-2`), con los P1
> diferidos que le caen en **§11** (_Time Stop / holding period_, _Thesis Engine_, _ATR real sin
> fallback 2 %_). **Numeración:** la línea AUTO se identifica por **versión de paquete**, no por
> `V2.4x` (que colisiona con las fases de cabina ya publicadas) — ver roadmap §0.

---

## 0. Estado en una frase

La reserva de cartera ya **no** es artesanal: cada aprobación tiene un `PortfolioReservation` con
identidad, siete dimensiones, coste real y ciclo de vida durable (`reserved_cash == Σ reservas
vivas`). **Lo que sigue sin existir es la vida de la posición después de abrirla**: el
`PositionState` tiene un estado **derivado** (`OPEN`/`PARTIAL`/`PROTECTED`/`CLOSED`) pero **no** un
ciclo de vida explícito, **no hay salida por tiempo**, **no hay motor de tesis**, **el stop nunca
sube** (el `stop_update` que el `PositionManager` calcula se **descarta** y `current_stop` queda
congelado en el valor de nacimiento) y el ATR de AUTO es **sintético** (`precio × 2 %`). Eso es
`AUTO-2`.

---

## 1. Contexto mínimo indispensable (verificado en código)

### 1.1 Qué es este proyecto

Monorepo de una plataforma de bolsa personal (IBEX/Europa). Relevante para esta continuación:

- `packages/py/domain` — dominio puro.
- `packages/py/application` — casos de uso: orquestador del ciclo, stores durables, ejecución/ledger
  y toda la cadena **AUTO 2.0**.
- `packages/py/analytics` — motor determinista y el módulo `cognitive/` (puros, sin red):
  `position_state`, `position_decision`, `exit_plan`, `exit_policy`, `risk_allocator`,
  `portfolio_reservation`, `position_ledger`.
- `packages/py/infrastructure` — SQLAlchemy + Alembic (PostgreSQL). `tables.py` es el espejo ORM.
- `apps/api-python` — API, **workers de fondo AUTO** y los E2E de certificación con PG real.

### 1.2 La cadena AUTO 2.0 y dónde vive la gestión de posición (anclajes reales)

```
tick AUTO (auto_simulation_worker.auto_turn, ~L2158–2431)
  → plan_v2_tick (auto_v2_entry)  → PortfolioDecision + PortfolioReservation  [AUTO-1]
  → orden (venue_order_id namespaced) → SIM settlement (simulated_fill_schedule)
      → execution_events.status = APPLIED | RETRY | ...
  → contabilidad de posición aplicada (POSITION = Σ APPLIED)                   [AUTO-1A]
  → _v2_track_entry / _v2_track_reduce  → self._v2_positions[symbol]: PositionState
  → gestión: _v2_position_package → plan_v2_position_outcome → PositionManager
                                                            → PositionDecision/ExitPlan
  → persistencia durable: _persist_position → _position_store.upsert(sim_auto_positions)
  → re-arranque: _v2_restore_durable_position / _v2_adopt_position
```

Rutas exactas que hay que leer antes de diseñar:

| Qué                                               | Dónde                                                                                                                                                                                                                                         |
| ------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Worker AUTO (todo el foco)                        | `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py`                                                                                                                                                                          |
| · gestión de posición                             | `_v2_position_package` **L2072–2109** · `_v2_track_entry` **L2111–2129** · `_v2_track_reduce` **L2131–2155**                                                                                                                                  |
| · persistencia durable                            | `_persist_position` **L815–850** · `_v2_durable_state` **L852–874**                                                                                                                                                                           |
| · adopción / rehidratación                        | `_v2_adopt_position` **L1980–2030** · `_v2_restore_durable_position` **L2032–2070**                                                                                                                                                           |
| · rama de protección LEGACY                       | `ProtectionConfig` **L210–268** · `_protection_config_from_env` **L271–310** · uso en `auto_turn` **L2224–2248** (solo con `AUTO_ENGINE_SIM_V2` **off**)                                                                                      |
| `PositionState` (dato)                            | `packages/py/analytics/src/bolsa_analytics/cognitive/position_state.py` (**L251–319**)                                                                                                                                                        |
| · build desde fill / rehidratación                | `build_position_state_from_fill` **L435–527** · `position_state_from_dict` **L336**                                                                                                                                                           |
| · ratchet de stop (existe, **no** se usa en AUTO) | `apply_position_current_stop` **L742** · `does_stop_worsen` **L182** · `apply_position_reduce`                                                                                                                                                |
| `ExitPlan` (motores de salida)                    | `packages/py/analytics/src/bolsa_analytics/cognitive/exit_plan.py` (`ExitReason` **L17–28**, `EXIT_REASON_PRECEDENCE` **L32–44** `MANUAL > STRUCTURAL_STOP > THESIS_INVALIDATION > PORTFOLIO_RISK > TARGET_1 > TARGET_2 > TRAIL > TIME_STOP`) |
| Fracciones T1/T2 por plantilla                    | `packages/py/analytics/src/bolsa_analytics/cognitive/exit_policy.py` (`CONSERVATIVE` 0.5/1.0 · `MODERATE` **0.3/0.3** · `AGGRESSIVE_SWING` 0.0/0.3, **L47–49**)                                                                               |
| `PositionManager` (orquestador fino)              | `packages/py/application/src/bolsa_application/position_manager.py` (`manage_position_outcome` **L187–273**, `PositionManagerResult` **L95–121**, `PositionManagerSkip` **L63–92**, `REGIME_EXIT` **L60**)                                    |
| Segundo camino de gestión AUTO                    | `packages/py/application/src/bolsa_application/auto_investment_system.py` (`run_auto_cycle` → `manage_position_outcome` **L404–409**)                                                                                                         |
| Tunables / flags AUTO                             | `packages/py/application/src/bolsa_application/auto_v2_entry.py` (`V2Tunables` **L140–160**, `_cost_model_from_env` **L189–206**, `plan_v2_position_outcome` **L700–722**, `position_manager_package` **L727–747**)                           |
| Reason codes (dueño único)                        | `packages/py/application/src/bolsa_application/auto_reason_codes.py` (92 líneas; familias `fill_`/`reservation_`/`mark_`/`decision_`/`no_`)                                                                                                   |
| ATR real (existe, **no** llega a AUTO)            | `packages/py/analytics/src/bolsa_analytics/indicators/compute.py` `compute_atr` **L175**                                                                                                                                                      |
| `db` espejo durable de posición                   | `sim_auto_positions` (`tables.py` **L2256–2313**) + `sim_fill_finance_context`                                                                                                                                                                |

### 1.3 Invariantes que NO se tocan (violarlos = fallo de la tarea)

- `AUTO ⇒ SIMULATED`. `LIVE` bloqueado (`LIVE_EXECUTION_AUTHORIZED` + `LIVE_EXECUTION_UNLOCKED`
  false). **Cero caminos LIVE nuevos.**
- `AUTO_ENGINE_SIM_V2` sigue **OFF por defecto**; con el flag sin definir el comportamiento debe ser
  el de `v2.39.x`. Cualquier cosa nueva de AUTO-2 vive detrás de ese flag.
- RiskGate / SimulationGate / Ledger / Reconciliation **deterministas**; **sin LLM en el hot path**.
- **Fail-closed**: ausencia de evidencia ≠ aprobación. **Ninguna salida protectora se veta jamás**
  por reconciliación o medición (el roadmap §4 lo exige como gate explícito).
- Migraciones **aditivas/nullables, sin backfill**, con `downgrade()` completo, **sin** ENUM de PG
  (convención del repo: `String` para estados).
- `POSITION = Σ APPLIED` y `exit_qty <= materialized_qty` (AUTO-1A). No se contabiliza la cantidad
  **pedida**; `RETRY`/`CAPTURED`/`APPLYING`/`FAILED` **nunca** son posición.
- No existe aprobación sin reserva ni reserva sin liberación (AUTO-1).
- Long-only intacto. `PAPER_D_EXECUTE` off.
- **No editar** los ficheros de plan de Cursor en `~/.cursor/plans/`.

---

## 2. Qué acaba de cerrar AUTO-1 (la base sobre la que arrancas)

Resumen operativo; el detalle auditado está en el
[audit-pack v2.41](./audit-pack-v2.41-auto-1-portfolio-reservation-2026-09-17.md).

- **`PortfolioReservation` + `ReservationLedger`** en
  `packages/py/analytics/src/bolsa_analytics/cognitive/portfolio_reservation.py` (puro, sin I/O ni
  reloj): identidad `RES-{decision_id}`, siete dimensiones (`reserved_cash`, `reserved_risk`,
  `asset_exposure`, `sector_exposure`, `correlation`, `strategy_capacity`, `liquidity_capacity`),
  coste y ciclo de vida (`OPEN`/`RELEASED_BY_FILL`/`_CANCEL`/`_RESTART`/`_ROLLBACK`). `reserve()` es
  **idempotente-rechazante**; una liberación **parcial** escala dimensiones y deja viva la cola.
- **`PortfolioRiskState`** (`gross_risk`, `net_risk`, `reserved_risk`, `pending_risk`,
  `sector_risk`, `strategy_risk`, `correlation_adjusted_risk` como **cota superior**), con
  `MeasurementStatus` fail-closed compartido.
- **Coste real en el sizing**: `TradingCostModel` + `estimate_trading_cost` derivan
  `ExpectedLoss`/`WorstCaseLoss`/`GapAdjustedLoss`; `compute_allocation` recorta por
  `risk_real = stop_loss + comisión + spread + slippage` y declara `cost_unmeasured` (nunca 0).
- **Migración `042_portfolio_reservations`** (head actual): tabla + índices `(account_id, status)`,
  `(account_id, sector)`, `(account_id, created_at DESC)` + el índice que faltaba
  `execution_events(account_id, status)` (**plano**, no parcial: un parcial dejaría fuera `APPLIED`).
- **Worker**: las reservas vivas son la autoridad de `reserved_cash`/`pending_risk` del libro
  pendiente; `execution_events` queda como **reconciliación de arranque**.
- **Bug real corregido en el camino**: `coerce_applied_fill_fact` solo aceptaba `applied_at` como
  `str` ⇒ todo hecho leído de PostgreSQL quedaba **sin fecha** (`_instant_text` en
  `position_ledger.py` lo normaliza ahora).

**Deuda que AUTO-1 dejó declarada y que NO es tuya** (no la reabras sin motivo):
`correlation`/`strategy_capacity`/`liquidity_capacity` quedan no medidas en el tick (es
`AUTO-3`/`AUTO-4`), la tabla de reservas crece sin política de retención, y `lease_generation` se
persiste pero no hay lógica de _lease_ entre procesos.

---

## 3. Anatomía **REAL** de la gestión de posición hoy (medida, no supuesta)

Esta sección es el núcleo del relevo: lo que el roadmap pide en §4 sólo tiene sentido si se ve
exactamente qué hay y qué no. **Todo lo de aquí está verificado leyendo el código en `78416b2c`.**

### 3.1 Lo que sí existe

- **`PositionState`** (frozen-ish dataclass en analytics): `position_id`, `trade_plan_id`,
  `instrument_id`, `direction`, `status`, `planned_entry`, `actual_entry`, `initial_stop`,
  `current_stop`, `target1`, `target2`, `quantity`, `remaining_quantity`, `initial_risk`,
  `realized_r`, `unrealized_r`, `mfe_mae`, `thesis_health`, `protection_state`, `trailing`,
  `exit_status`, `target1_leg`, `target2_leg`, `revisions`, `created_at`, `updated_at`,
  `target1_achieved_at`, `target2_achieved_at`, `decision_id`.
- **Estados**: `PositionStatus = Literal["OPEN", "PARTIAL", "PROTECTED", "CLOSED"]` y
  `PositionExitStatus = Literal["none","hint","armed","done"]`, más `TargetLegStatus =
Literal["pending","triggered","executed","failed"]`. El `status` **se deriva**, no se fija:
  `derive_position_status` da precedencia `CLOSED > PROTECTED (stop = break-even) > PARTIAL
(remaining < quantity) > OPEN`.
- **`ExitPlan`** con 8 motivos ya tipados: `STRUCTURAL_STOP`, `THESIS_INVALIDATION`, `TARGET_1`,
  `TARGET_2`, `TRAIL`, `TIME_STOP`, `PORTFOLIO_RISK`, `MANUAL`, con precedencia explícita.
- **`PositionManagerSkip`** tri-estado (AUTO-1A): `mark_rejected`, `decision_unavailable` (el
  worker los journaliza con `attention="high"`; `manage_position` colapsa a `None` por
  compatibilidad).
- **`REGIME_EXIT`** con **precedencia absoluta**: si `regime_is_exit_only(regime)`, el manager
  fuerza `order_action="sell"` con la cantidad viva y `stop_update=None`
  (`position_manager.py` L257–261).
- **Persistencia durable de la posición**: `sim_auto_positions` tiene `quantity`, `avg_price`,
  `entry_price`, `high_watermark`, `stop_price`, `t1_state`, `trailing_state`, `strategy_version_id`
  y `position_state` (JSONB con el `PositionState.to_dict()` rehidratable).

### 3.2 Los siete huecos medidos (esto ES el trabajo de AUTO-2)

1. **No existe `ProtectionPlan`.** La cadena `Strategy → TradePlan → ProtectionPlan → PositionState
→ PositionManager` del roadmap §4 **no** está implementada: `ProtectionPlan` aparece **solo en
   documentación** (grep en todo el repo: cero clases/módulos/tablas). Hoy la protección es
   `PositionState.current_stop` + `ExitPlan`, y el plan de protección **no es un objeto durable**.
   El propio `audit-pack-v2.40.1` ya declaró _"No se implementan `ProtectionPlan`/`ProtectionInstruction`
   durables"_.
2. **No hay ciclo de vida explícito.** No existe ningún estado `ENTRY_PENDING`, `T1_REACHED`,
   `PARTIAL_EXIT`, `TRAILING`, `EXIT_PENDING`, `ERROR`, `UNKNOWN`, `RECONCILIATION_REQUIRED` ni
   `PROTECTION_MISSING`. Lo que el roadmap pide como FSM hoy es un `Literal` de 4 valores
   **derivado** + dos ejes sueltos (`exit_status`, `TargetLeg.status`). T1/T2 se registran como
   _efecto lateral_ de `apply_position_reduce`, no como transición de estado.
3. **No hay salida por tiempo.** `TIME_STOP` **existe** en `ExitPlan` (L169–171) y **nunca se
   dispara en AUTO**, porque `expires_at` no se pasa:
   `_v2_position_package` (worker L2086–2094) y `run_auto_cycle` (L404–409) llaman sin
   `expires_at`/`now`. Además, `TradePlan.expires_at` es `None` en el camino AUTO
   (`decide_portfolio` se invoca sin `expires_at` en `plan_v2_tick`). Y los horizontes
   `max_holding_period_days` / `min_holding_period_minutes` de `trading_policy.py` (L72–73) y
   `operating_policy.py` (L32–34) son **metadata declarada sin ningún consumidor**. Y
   `expected_holding_period` **no existe en el repo** (cero coincidencias).
4. **No hay motor de tesis.** `THESIS_INVALIDATION` existe en `ExitPlan` (L141–142) y el parámetro
   `thesis_invalid` llega hasta `manage_position_outcome`, pero **el worker nunca lo pone a `True`**
   (pasa el default `False`). `PositionState.thesis_health` nace como stub `{"status":"none"}`
   (L491, usado en L518–520) y **nunca se actualiza**. No hay evaluador de "condición de
   invalidación" en ninguna parte (la palabra `invalidation` solo aparece como metadata de journal).
5. **El stop nunca sube en AUTO (el hallazgo más grave).**
   `manage_position_outcome` **calcula** `stop_update` y lo publica en `PositionManagerResult`,
   pero `position_manager_package` (`auto_v2_entry.py` L727–747) **lo descarta**: solo lee
   `order_action`/`order_qty`, y **devuelve `None` cuando `order_action == "hold"`** — de modo que
   una intención de **`PROTECT`** (que `ExitPlan` emite vía `TRAIL` → `suggested_action="protect"`
   con `suggested_stop`) **no produce paquete, no se aplica y no se journaliza**. Consistente con
   eso: `apply_position_current_stop` **nunca se llama en el worker** (grep: cero coincidencias en
   `auto_simulation_worker.py`) y `current_stop` solo se **lee** (L871, L1169, L2067); se fija una
   vez en el nacimiento (`build_position_state_from_fill`). Consecuencia: **break-even nunca se
   protege, el trailing no existe en AUTO**, y `sim_auto_positions.trailing_state` /
   `high_watermark` se persisten pero nunca avanzan (los escriben otras rutas).
6. **El ATR de AUTO es sintético.** El worker construye **cada** `V2Signal` con
   `atr = float(price) * atr_pct_fallback` (`auto_simulation_worker.py` **L1229**; default `0.02` en
   `auto_v2_entry.py` **L149**, env `AUTO_ENGINE_SIM_V2_ATR_PCT`). También en `_v2_stop_map`
   (**L1180**) y `_v2_adopt_position` (**L2002–2003**). `compute_atr` real existe
   (`indicators/compute.py` **L175**) y `compute_atr_stop` lo consume
   (`risk_allocator.py` **L159**), pero **AUTO nunca lo alimenta con barras**.
7. **El camino AUTO SIM no escribe `position_states`.** Lo acredita el propio CHANGELOG
   (`CHANGELOG.md:371`). El espejo durable del AUTO es `sim_auto_positions`; la tabla
   `position_states` (ADR-033, con índice único parcial `status <> 'CLOSED'` y hot scalars) la
   escribe el camino Confirm/ExecutionRouter (`persist_position_from_fill/exit/protect`). **Decide
   explícitamente** si AUTO-2 vive en `sim_auto_positions` (mínimo cambio, es el espejo que el
   worker ya lee al rearrancar) o si unifica hacia `position_states` (más fiel al roadmap, más
   superficie de riesgo). **No** lo hagas "por accidente".

### 3.3 Trampas medidas (landmines que te van a morder)

- **`position_manager_package` devuelve `None` en `hold`** ⇒ hoy _cualquier_ intento que no sea
  `reduce`/`sell` desaparece, incluido `protect`. Si AUTO-2 introduce `PROTECT`/`TRAILING` y no
  toca esto, el estado avanzará en RAM y **no** producirá efecto ni journal.
- **Dos fracciones de T1 distintas entre los dos caminos AUTO.** El worker pasa
  `exit_template="moderate"` ⇒ `MODERATE_EXIT_POLICY` = **T1 30 % / T2 30 %**. `run_auto_cycle`
  llama **sin** `exit_template` ⇒ `template_id=None` ⇒ en `build_position_decision` (L241–243)
  `policy = None` ⇒ `suggestion_from_exit_policy` cae al fallback **T1 0.5 / T2 1.0**
  (`exit_policy.py` L96 y L105). **Hoy AUTO sale de T1 con 30 % en un camino y 50 % en el otro.**
  AUTO-2 debe unificar la resolución de política (una sola fuente) y declararlo.
- **`trail_width` nunca se convierte en stop.** `TRAIL_DISTANCE_R_BY_WIDTH` /
  `trail_distance_r_from_width` (0.75/1.0/1.25 R) solo lo consume el advisory `trail_plan.py`
  (camino mesa). En AUTO, `trail_hint`/`trail_stop` son parámetros que **nadie rellena**.
- **`ProtectionConfig` está en el camino legacy y morirá.** `ProtectionConfig` (worker L210–268,
  env `AUTO_ENGINE_SIM_PROTECTION`) solo se evalúa con `AUTO_ENGINE_SIM_V2` **off** (L2224–2248).
  Su retirada (criterio de salida de `AUTO-2`) **rompe tests que existen**: `test_auto_simulation_worker.py`
  (3 tests con `AUTO_ENGINE_SIM_PROTECTION=1`) y `test_a9_1_durability_integrity.py`
  (`test_restart_with_open_position_trailing_uses_persisted_watermark`,
  `test_exit_reason_trailing_wins_over_t1`). Habrá que **portarlos**, no borrarlos: el
  comportamiento que cubren (trailing desde high-watermark persistido) es justamente lo que
  AUTO-2 debe reimplementar bien.
- **`apply_position_current_stop` rechaza stops que empeoran** sin override auditado
  (`does_stop_worsen` + `_is_audited_override`). Es tu red de seguridad al introducir trailing:
  úsala, no la sortees.
- **El `suggested_price` de la orden de venta es `position.current_stop`**
  (`position_manager_package` L744) ⇒ si el stop está mal, el precio sugerido está mal. Otro motivo
  para que el stop deje de estar congelado.
- **`position_state` JSONB es rehidratable exacto** (`position_state_from_dict`) y el e2e PG
  `test_auto_v2_durable_pg.py` **afirma que `current_stop` sobrevive al reinicio** (L250–273). Si
  cambias el shape de `PositionState`, ese test es tu canario.
- **`mfe_mae`, `thesis_health`, `protection_state`, `trailing` son dicts `object`**: no hay
  esquema. Si AUTO-2 los puebla, tipa el contenido y declara la degradación a `UNKNOWN`.

---

## 4. Alcance declarado de `V2.42` / `AUTO-2` y decisiones abiertas

### 4.1 Lo que pide el roadmap §4 (texto normativo)

- **Objetivo.** Convertir la gestión de posición en una **máquina de estados persistente** con
  salidas temporales, de tesis y de régimen, no solo por stop.
- **Invariante que instala.** _Una posición siempre tiene un estado persistido y verificable; un
  estado no verificable degrada a `RECONCILIATION_REQUIRED`, nunca a "sin protección"._
- **Estados:** `FLAT → ENTRY_PENDING → OPEN → PROTECTED → T1_REACHED → PARTIAL_EXIT → TRAILING →
EXIT_PENDING → CLOSED`, más `ERROR`, `UNKNOWN`, `RECONCILIATION_REQUIRED`, `PROTECTION_MISSING`.
- **Contenido:** salidas nuevas `TIME_EXIT` (`expected_holding_period`/`max_holding_period`),
  `THESIS_EXIT` (motor de tesis `VALID`/`WEAKENING`/`INVALID` con **condición de invalidación
  explícita en el plan**), `REGIME_EXIT`, `RISK_EXIT`; **eliminar el doble motor de protección**
  (`ProtectionConfig` fuera del camino AUTO); **ATR real** (sin ATR no hay stop ⇒ `NO ENTRY` cuando
  la política exija precisión de riesgo; el fallback `precio × 2 %` queda **solo** para el camino
  legacy).
- **Gate:** test de ciclo de vida completo por **producto cartesiano de eventos** (stop, T1, T2,
  trailing, tiempo, tesis, régimen, riesgo) con **transiciones inválidas rechazadas**; test de
  **reinicio que rehidrata cada estado intermedio**; test que certifica que **ninguna salida
  protectora se veta** por reconciliación/medición.
- **Criterio de salida:** `ProtectionConfig` sin **ninguna** lectura en el camino
  `AUTO_ENGINE_SIM_V2=1` **y** `TIME_EXIT`/`THESIS_EXIT` con **evidencia en el journal de un día
  completo**.

### 4.2 Decisiones que hay que tomar (pregúntalas al owner **antes** de codificar)

1. **¿Dónde vive el estado?** ¿Extender `sim_auto_positions` (espejo que el worker ya lee, mínimo
   riesgo) o migrar a `position_states` (ADR-033, más canónico)? Recomendación: **extender
   `sim_auto_positions`** con un `lifecycle_state` explícito y **declarar** la dualidad, porque
   unificar toca el camino Confirm y multiplica el riesgo. Sea cual sea, **una** autoridad.
2. **¿Un solo slice o dos?** Caben dos: **2a** = FSM + `PROTECT`/trailing real (aplicar
   `stop_update`, eliminar `ProtectionConfig`, unificar fracciones T1) sobre `sim_auto_positions`,
   **sin** migración si el estado cabe en `position_state` JSONB + columnas ya existentes;
   **2b** = `TIME_EXIT` + `THESIS_EXIT` + ATR real + migración `043` (columnas de horizonte y de
   tesis, o tabla nueva de transiciones). El patrón de AUTO-1 (a hermético + b durable) funcionó
   bien: **recomendado**.
3. **¿De dónde sale el horizonte de tiempo?** `trading_policy`/`operating_policy` ya declaran
   `max_holding_period_days`/`min_holding_period_minutes` por plantilla (90/45/21 días) pero **sin
   consumidor**. ¿Se cablean esos, o `TradePlan` gana campos propios? Recomendación: que el
   `TradePlan` los transporte (es el contrato que ya viaja al `PositionState`).
4. **¿Quién evalúa la tesis?** Hay `thesis_health.py` (`map_thesis_health`) y `thesis_health` en el
   `PositionState`. ¿Se reutiliza y se puebla, o se implementa un evaluador con condición de
   invalidación declarada en el plan? Recomendación: reutilizar + **condición explícita**;
   `AI`/LLM **no** entra en el hot path.
5. **¿Qué pasa con las posiciones abiertas en el arranque sin estado verificable?** El invariante
   dice `RECONCILIATION_REQUIRED`, **nunca** "sin protección". Eso obliga a decidir qué es una
   "protección mínima viable" para una posición adoptada (`_v2_adopt_position` reconstruye con
   ATR sintético hoy; con ATR real puede **no haber** stop ⇒ `PROTECTION_MISSING`).
6. **Severidad del ATR real.** El roadmap dice literalmente _"sin ATR no hay stop ⇒ `NO ENTRY`
   cuando la política exija precisión de riesgo"_. Hoy AUTO **siempre** entra con ATR sintético.
   Convertir eso en `NO ENTRY` es un cambio de comportamiento **grande** en producción simulada:
   confírmalo explícitamente y mide cuántas señales caen.

---

## 5. Infraestructura: migración, store, CI (si el slice lleva migración)

Si AUTO-2 no necesita esquema nuevo (todo en `position_state` JSONB), **dilo** y no crees una
migración por inercia. Si la necesita (`043_*`):

- **Patrón obligatorio**: copia la forma de
  `packages/py/infrastructure/alembic/versions/042_portfolio_reservations.py` — docstring largo en
  español con el _por qué_, `revision`/`down_revision` en cadena lineal, constantes de nombres de
  tabla/índice, guardas `_table_exists`/`_column_exists`/`_index_exists`, `upgrade()` con bloques
  numerados y `downgrade()` **completo y simétrico** (índices primero, tabla después), y
  `sa.String()` para estados (**nunca** un ENUM de PG), `sa.Numeric(18,6)`, `sa.DateTime(timezone=True)`.
- **El baseline `003` NO copia los `Index` de `__table_args__`** (solo FK y `UniqueConstraint`).
  Cualquier `Index(...)` nuevo hay que crearlo **explícitamente** en la migración. Está documentado
  en el docstring de la `042` y en `041`.
- **Espejo 1:1 en `tables.py`**: la fila ORM debe coincidir exactamente con lo que crea la
  migración (nombres de índice incluidos).
- **Store**: si hace falta persistir transiciones, sigue el template de
  `packages/py/application/src/bolsa_application/reservation_store.py` — `Protocol` +
  `InMemory` + `Postgres`, **imports de fila perezosos dentro de cada método**, `ON CONFLICT` para
  idempotencia, `_commit_if(session, autocommit)` y `limit` fail-closed (`[]` si `limit <= 0`).
- **Bumpear la head si añades `043`** (esto **rompe CI si se olvida**):
  - `apps/api-python/tests/test_discovery_evidence_snapshot_pg.py:43` → `_ALEMBIC_HEAD =
"042_portfolio_reservations"` (aserción en L618, 668, 770, 1011, 1079).
  - Revisa `_PREVIOUS_REVISION` de `test_portfolio_reservation_pg.py:48` (hoy
    `"041_unique_natural_keys"`, con `downgrade`/`upgrade` en L282–303) y de
    `test_unique_natural_keys_pg.py:46`.
- **CI (un test nuevo NO entra solo)**:
  - Test **hermético de application** (`packages/py/application/tests/test_*.py`): añadirlo
    **explícitamente** a la lista de `quality` en `.github/workflows/python-ci.yml` (**~L116–148**) y
    a la del job `python` en `.github/workflows/release-tag-ci.yml` (**~L339–372**).
  - Test **de app** (`apps/api-python/tests/…`): entra solo por directorio; añade `--ignore` solo si
    necesita PG.
  - Test **PG nuevo**: añadirlo a la lista del job `auto-v2-durable-pg`
    (`python-ci.yml` L427–432) y/o `lifecycle-pg` (`release-tag-ci.yml` L530–560), **y** su
    `--ignore` en los jobs offline. Registra su gate `*_PG_REQUIRED` en el bloque `env:` (un
    **skip silencioso debe ser fallo duro**; los jobs ya tienen un step «fail on skipped»).
  - **Comentarios siempre FUERA del bloque plegado `run: >`** (lección de `v2.40.2`: un `#` dentro
    de un bloque plegado se come el resto del comando y dejó jobs en verde falso).
  - **Los `ProtectionConfig`/posición son tests auto-recogidos**: `test_auto_simulation_worker.py` y
    `test_a9_1_durability_integrity.py` viven en `apps/api-python/tests/` y entran por directorio, así
    que **una retirada de `ProtectionConfig` los pone rojos en `quality`** aunque no estén en la
    lista explícita. Cuéntalo.

---

## 6. Cómo verificar SIEMPRE antes de decir «hecho»

Orden mínimo, **paridad con CI**. Extrae los comandos del YAML, **no** los reescribas de memoria:

```bash
# 1) Calidad (invocación EXACTA de CI)
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src \
           packages/py/infrastructure/src packages/py/application/src \
           apps/api-python/src --follow-imports=silent

# 2) Offline del job `quality`: EXTRAE su lista y sus --ignore del propio YAML y ejecútala tal cual
uv run python -c "import yaml;print(yaml.safe_load(open('.github/workflows/python-ci.yml',encoding='utf-8'))['jobs']['quality']['steps'][-1]['run'])"

# 3) PG de certificación (Postgres 16 local)
cd packages/py/infrastructure && uv run alembic upgrade head && cd -
AUTO_V2_DURABLE_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_auto_v2_durable_pg.py -q
AUTO_SCHEDULER_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_auto_scheduler_real_pg_zero_human_intervention.py -q   # ×30
AUTO_SCHEDULER_PROCESS_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py -q

# 4) Batería completa de paquetes
uv run pytest packages/py -q
```

Reglas de honestidad del repo (no negociables):

- No declares verde sin haber corrido los bloques.
- Distingue fallos **preexistentes** de regresiones tuyas; mide con **A/B** (`git stash` + re-run).
- No certifices `main`/HEAD como si fuera un tag.
- **Muta tu propio código**: por cada invariante nuevo, aplica una mutación, mide el rojo, revierte y
  **publica la matriz medida** (es el estándar de `v2.40.x`/`v2.41`). Una mutación que no pone nada
  en rojo significa que el gate no muerde.
- La máquina de verificación es **Windows con política de control de aplicaciones**: si
  `alembic` falla al spawnear, usa `uv run python -m alembic`. `mypy` sí funciona.

---

## 7. Uso sugerido de subagentes

- **explore (very thorough)**, antes de escribir nada: mapa de `_v2_position_package` /
  `_v2_track_entry` / `_v2_track_reduce` / `_v2_durable_state` / `_v2_adopt_position` y del camino
  `PositionState → ExitPlan → PositionDecision`. Esta sección §3 es el atajo, pero **verifica** los
  números de línea: el código se mueve.
- **explore (medium)**: inventario de todo lo que lee `ProtectionConfig` y de todo lo que lee
  `PositionState.status` (para no dejar consumidores huérfanos al introducir el FSM).
- **generalPurpose**: cambios que cruzan worker + application + analytics manteniendo semántica y
  retrocompatibilidad del camino con `AUTO_ENGINE_SIM_V2` off.
- **best-of-n-runner**: solo si dudas entre dos diseños de FSM (p. ej. estado en columna String vs
  JSONB vs tabla de transiciones).
- **bugbot** / **security-review**: **solo** si el owner los pide explícitamente.
- **ci-investigator**: si un run de CI falla y hay que diagnosticarlo.

---

## 8. Checklist de arranque (haz esto primero)

- [ ] `git log --oneline -3` → debe salir `78416b2c` (sellado docs-only) sobre `e6b0dd5b` (fase).
- [ ] `git status --short` → **vacío**. Si hay ruido (`logs/`, `__pycache__/`, `.pytest_cache/`),
      es de tus propias pruebas.
- [ ] `git tag -l -n5 v2.41-beta` → tag anotado apuntando a `e6b0dd5b`.
- [ ] `git stash list` → hay un stash **ajeno y antiguo** (`all-v170`). **No lo toques**; si haces
      A/B con `git stash`, comprueba que el árbol vuelve a estar limpio.
- [ ] `package.json` → `1.66.0-beta` (el bump a `1.67.0-beta` es de esta fase).
- [ ] Head de Alembic → `042_portfolio_reservations` (confirmado hoy).
- [ ] Lee §3 de este documento **entero** y luego verifica en código **dos** de los siete huecos
      (el nº5 —stop congelado— y el nº6 —ATR sintético— son los más rentables).
- [ ] Pregunta al owner las **seis decisiones** de §4.2 **antes** de codificar.
- [ ] Elige: **2a** (FSM + protección real, sin migración) o **2b** (tiempo + tesis + ATR real +
      migración `043`).

---

## 9. Freeze (copiar en cualquier sesión)

`AUTO ⇒ SIMULATED` · LIVE bloqueado (`LIVE_EXECUTION_AUTHORIZED` + `LIVE_EXECUTION_UNLOCKED` false) ·
`AUTO_ENGINE_SIM_V2` **OFF por defecto** · `PAPER_D_EXECUTE` off · sin LLM en hot path · fail-closed
(ausencia de evidencia ≠ aprobación) · **ninguna salida protectora se veta jamás** por
reconciliación ni por medición · migraciones aditivas/nullables sin backfill con `downgrade()`
completo y **sin ENUM de PG** · long-only · Alembic head **`042_portfolio_reservations`** ·
**`POSITION = Σ APPLIED`** y **`exit_qty <= materialized_qty`** · lo pedido, lo llenado y lo
materializado son tres números distintos y los tres son auditables · **no existe aprobación sin
reserva ni reserva sin liberación** (`reserved_cash == Σ reservas vivas`) ·
`RETRY`/`CAPTURED`/`APPLYING`/`FAILED` **nunca** son posición ni realizado · ningún skip de gestión
queda mudo · **una posición siempre tiene estado persistido y verificable; un estado no verificable
degrada a `RECONCILIATION_REQUIRED`, nunca a "sin protección"** (`AUTO-2`).

**No hacer:** tocar las barreras LIVE · añadir un segundo motor de trading/FSM ·
leer `position_state`/`position_states` como autoridad de posición · contabilizar la cantidad
**pedida** · dejar dos fuentes de verdad del estado de posición · retirar `ProtectionConfig` sin
portar los tests que lo cubren · certificar sin correr los bloques de §6 · declarar CI de un tag que
aún no existe · meter ruido de `logs/` y caches en un commit · editar los ficheros de plan de Cursor
en `~/.cursor/plans/`.
