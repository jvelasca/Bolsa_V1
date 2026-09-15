# Audit Pack — V2.40 / AUTO 2.0 · Investment Operating System (2026-09-15)

> **Punto de entrada único para auditoría externa desde GitHub**, sin acceso al entorno.
> Fase: **v2.40** — AUTO deja de ser _orquestador de investigación + promoción de estrategias_
> conectado a un simulador y pasa a ser un **sistema operativo de inversión** (qué comprar,
> cuándo, cuánto, cómo gestionar y cuándo salir).
>
> **Base auditada:** `v2.39.3-beta` (`b6c70595`).
> **Commits de código/test:** `c342330a` (espina cognitiva) · `c31de353` (decisión de cartera y
> gestión por posición) · `2e65e764` (estado V2 durable, migración 040) · `44ebafd8` (cableado en el
> worker) · `301a77a9` (reinicio real PG + head 040 en los roundtrips). Bump y certificación CI:
> `85438af0` (`1.64.3-beta` → **`1.65.0-beta`**). Documentación de auditoría: `97f004e7` y el commit
> de sellado.
> **Tag:** `v2.40-beta` (anotado) — el auditor lo resuelve con `git rev-list -n 1 v2.40-beta`.
> **Alembic head:** `040_auto_v2_durable_state` (**una migración nueva**, ver §5).
> **Flags:** `AUTO_ENGINE_SIM_V2` (**OFF por defecto**). Con el flag sin activar, AUTO se comporta
> exactamente como `v2.39.3-beta` (el camino clásico queda intacto). El resto de umbrales V2 se
> leen de env con **default seguro ante valor inválido** (§7).
>
> **Sello CI:** `release-tag-ci` **GREEN** — run [`34972246205`](https://github.com/jvelasca/Bolsa_V1/actions/runs/34972246205)
> (`status=completed`, `conclusion=success`, commit `97f004e7`; 10/10 jobs requeridos verdes +
> `certify` aggregate `success`; único skip: `playwright` integrado, opt-in). `python-ci` (por
> commit) **GREEN** — run [`34972246101`](https://github.com/jvelasca/Bolsa_V1/actions/runs/34972246101),
> con el job **nuevo** `auto-v2-durable-pg` en `success` (PostgreSQL real + `AUTO_V2_DURABLE_PG_REQUIRED=1`
>
> - paso _fail-if-skipped_). Siguiendo el patrón de las fases anteriores, el tag se re-apunta al
>   commit de sellado (solo documentación) por encima de `97f004e7`; el auditor resuelve siempre con
>   `git rev-list -n 1 v2.40-beta`.

---

## 0. Resumen ejecutivo

La auditoría externa de `v2.39.3-beta` dejó un diagnóstico explícito: **la infraestructura ya no
era el problema de AUTO; el problema era el modelo operativo**. AUTO funcionaba como orquestador de
Discovery/Grammar/Adaptive conectado a un simulador, no como un sistema que decide y gestiona.

Esta fase **cambia el corazón operativo**, y lo hace **sin tocar el dinero ni el settlement**: el
camino transaccional (ledger, finance SIM, reconciliación, idempotencia por fill) permanece
idéntico y toda intención nueva vuelve a pasar por el **mismo Single Decision Spine**
(`kill switch` → `simulation_gate_allows` → `risk_gate_auto_paper_dry` → settlement). Lo único que
cambia es **qué** intención se emite y **con qué contrato**.

| Capa            | Antes (`v2.39.3-beta`)                                | Ahora (`v2.40-beta`, flag `AUTO_ENGINE_SIM_V2=1`)                                     |
| --------------- | ----------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Señal → entrada | decider directo / propuesta de estrategia             | `OpportunityRanker` → `PortfolioDecisionEngine` → `TradePlan` (fail-closed)           |
| Sizing          | `lot_qty` de la propuesta                             | `RiskAllocator` (riesgo por operación + tope por posición/sector)                     |
| Gestión         | `ProtectionConfig` global (SL/T1/trailing por config) | `PositionState` + `ExitPlan` + `PositionDecision` **por operación**                   |
| Régimen         | gate de régimen no direccional                        | `MarketRegimeGate` **direccional** + régimen real de barras (`DiscoveryRegimeSource`) |
| Reentrada       | sin dedupe de oportunidad                             | `SignalIdentity` por barra: la MISMA señal no se re-emite (anti-_churn_)              |
| Crash/restart   | plan de posición reconstruido por ATR; dedupe en RAM  | **plan rehidratado exacto** + **señales consumidas durables** (migración 040)         |

**Veredicto:** AUTO 2.0 es un cambio de **modelo operativo** sobre infraestructura intacta, detrás
de un flag **OFF por defecto**, con los vetos en **fail-closed** (sin régimen operable no hay
entradas; sin plan durable se adopta explícitamente y se audita como `adopted`) y con el estado
crítico **durable** para que un crash no degrade la operativa.

---

## 1. P0 — Espina cognitiva (`bolsa_analytics.cognitive`)

Módulos **nuevos**, deterministas y puros (sin red, sin relojes ocultos, sin estado global):

| Módulo                       | Líneas | Responsabilidad                                                              |
| ---------------------------- | ------ | ---------------------------------------------------------------------------- |
| `auto_portfolio_snapshot.py` | 327    | `AutoPortfolioSnapshot`: foto **canónica e inmutable** del libro (`as_of`)   |
| `opportunity_ranker.py`      | 156    | `OpportunityRanker`: score determinista (edge, R:R, liquidez, concentración) |
| `risk_allocator.py`          | 274    | `RiskAllocator`: sizing por presupuesto de riesgo; SL/TP derivados de ATR    |
| `signal_identity.py`         | 172    | `SignalIdentity` + `bar_window`/`timeframe_seconds`: identidad y frescura    |
| `market_regime_gate.py`      | 142    | `MarketRegimeGate`: veto de entradas por régimen y **dirección**             |

`sector_from_package`/`edge_from_package` viven en la capa de aplicación (adaptadores del
`DecisionPackage` legado) y no contaminan analytics.

**Foco para el auditor:**

1. ¿`AutoPortfolioSnapshot` es **inmutable** (`frozen`) y su `as_of` procede de una única lectura
   coherente del tick, o hay ventanas en las que dos símbolos ven estados distintos del libro?
2. ¿El score del ranker es **total y determinista** (mismo input ⇒ mismo output) y **ordena de
   forma estable** ante empates? ¿Puede un empate producir un orden dependiente del orden de
   entrada (no determinista)?
3. ¿`RiskAllocator` **nunca** devuelve cantidad > tope por posición/sector, y qué hace ante ATR
   ausente o cero (¿fail-closed o sizing inventado?)?
4. `timeframe_seconds`/`bar_window`: ¿son **fail-closed** ante timeframe ilegible o `moment` sin
   zona horaria (devuelven `None`, no una barra adivinada)?

---

## 2. P1 — Decisión de cartera (`portfolio_decision_engine.py`)

`PortfolioDecisionEngine` (395 líneas) decide **ENTRY / NO-ENTRY** a nivel de **cartera**, no por
símbolo aislado, y publica un `TradePlan` (contrato del camino caliente) más la decisión auditada.

**Foco:**

1. Enumera **todos** los caminos que devuelven `approved=False` y comprueba que cada uno **deja
   `reason_codes`** (una negativa sin motivo es un fallo de auditoría).
2. **Exposición acumulada dentro del tick**: si dos oportunidades se aprueban en el mismo tick,
   ¿la segunda ve la exposición de la primera (sector/correlación/riesgo) o ambos ven el estado
   previo y pueden violar el límite **en conjunto**? Este es el punto donde un sistema de cartera
   suele romperse.
3. ¿Los vetos son **fail-closed** ante dato ausente (sector desconocido, correlación no calculable,
   régimen `UNKNOWN`) o degradan a "permitido"?
4. ¿El `TradePlan` emitido es autoconsistente (stop del lado correcto de la entrada, objetivos
   coherentes con dirección y R) y el adaptador `trade_plan_to_decision_package` **no relaja**
   ninguna guarda del contrato legado?

---

## 3. P2 — Gestión de posición (`position_manager.py` + `PositionState`)

`plan_v2_position_decision` / `PositionManager` conectan `PositionState` (estado) + `ExitPlan`
(política) + `PositionDecision` (intención): stop estructural, **T1/T2 parciales**, trailing,
`exit-only` por régimen y cierre de sesión.

**Foco:**

1. ¿Un T1 (parcial) puede **re-dispararse** en ticks sucesivos, o el estado (`target1_leg`) lo
   impide de forma durable?
2. ¿`regime_exit` (exit-only) tiene **precedencia** sobre cualquier otra intención, incluida una
   mejora de stop?
3. ¿El trailing **nunca empeora** el stop vigente (`clamp_stop_not_worsen`) y el máximo
   (`high_watermark`) sobrevive a un reinicio?
4. ¿El cierre por protección **hereda la atribución de versión** de estrategia (para que la serie
   observada no se trunque en NULL)?

---

## 4. P3 — Régimen real y sector

- `DiscoveryRegimeSource` (`auto_v2_entry.py`, ~línea 737): régimen operativo desde el clasificador
  **determinista de barras** `discovery_market_regime_v0` (el mismo de V2.39), con refresco por
  tick y **fail-closed** (error de lectura ⇒ `UNKNOWN` ⇒ exit-only, nunca entradas a ciegas).
- `MarketRegimeGate` **direccional**: un régimen alcista **no** autoriza cortos.
- **Sector**: viaja en la decisión (`PortfolioDecision.sector`), en el journal
  (`payload["sector"]`) y alimenta el gate de concentración; si no es resoluble, queda **desconocido**
  y el gate de concentración sectorial **no puede evaluarlo** (nunca se asume exento).

**Foco:** ¿existe algún camino en el que "no sé el sector" se convierta en "sin restricción de
sector"?

---

## 5. P4 — Durabilidad del estado V2 (migración `040_auto_v2_durable_state`)

**Migración nueva** (119 líneas, `down_revision = 039_research_trials_regime`):

- `sim_auto_positions.position_state` — **JSONB nullable**. Nullable es deliberado: _"sin plan
  vivo"_ es un estado válido y no se inventa un plan operativo que el motor no está siguiendo.
- `sim_consumed_signals` — `(account_id, engine_id, signal_id)` PK + índices por
  `(account_id, engine_id, bar_timestamp)`; se **poda** a la barra corriente.

**Worker (`auto_simulation_worker.py`):**

- `_persist_position` escribe el plan V2 en cada cambio de cantidad
  (`_v2_durable_state` → `PositionState.to_dict()` + `avg_price`/`stop_price`/`t1_state`/
  `trailing_state`).
- `readopt_positions` guarda el `position_state` leído y `_v2_restore_durable_position` lo
  **rehidrata exacto** (`position_state_from_dict`) en el primer uso. La cantidad se **re-ancla al
  ledger** (el plan manda en el CÓMO salir; el CUÁNTO lo dicta el ledger).
- Fallback explícito: sin plan durable se adopta con geometría reconstruida y se marca `adopted`.
- `_v2_load_consumed_signals` / `_v2_mark_signal_consumed` (solo tras **fill confirmado**) /
  `_v2_prune_consumed_signals` / `_v2_roll_consumed_bar`.
- Corregido un bug latente del camino de reconstrucción contra el canónico: el `upsert` no
  reenviaba `strategy_version_id` ni `position_state`, de modo que un `REBUILT` los borraba.

**Foco (crítico):**

1. Si el proceso muere **entre** el fill y la escritura del plan, ¿el reinicio deja la posición sin
   gestión? ¿O el fallback `adopted` garantiza que **nunca** queda huérfana (stop vivo)?
2. ¿Puede un plan durable **obsoleto** (de una posición ya cerrada) resucitarse por un símbolo
   reabierto? ¿El `delete` de la posición limpia también el plan?
3. ¿La clave de dedupe (`signal_id`) incluye **instrumento + acción + versión de estrategia +
   barra**, de modo que dos estrategias distintas sobre el mismo símbolo/barra **no** se bloqueen
   entre sí?
4. Comprueba que `_v2_mark_signal_consumed` **no** se invoca cuando el spine veta (kill/sim-gate/
   RiskGate/sin fill) — una señal quemada sin fill prohibiría una entrada legítima.

---

## 6. Cableado: del `TradePlan` al spine (sin atajos)

`auto_v2_entry.py` (790 líneas) es el punto de entrada del pipeline; el worker lo consume y sigue
liquidando por el camino de siempre.

**Foco:**

1. ¿Existe algún camino en el que una intención V2 llegue al settlement **sin** pasar por
   `risk_gate_auto_paper_dry` y `simulation_gate_allows`, o en el que el flag V2 active un
   settlement distinto?
2. Con `AUTO_ENGINE_SIM_V2` **sin definir**, ¿el comportamiento es **byte a byte** el de
   `v2.39.3-beta` (esto lo cubre `test_v2_off_by_default_keeps_legacy_path`)?
3. ¿Un fallo del pipeline V2 (excepción) se traduce en **no operar** (fail-closed) y no en operar
   por el camino clásico "de rebote"?
4. El readopt durable y la marca de señales, ¿están **inertes** con el flag OFF (no tocan la BD
   más allá de lo que ya hacía `v2.39.3-beta`)?

---

## 7. Flags y superficies de configuración

| Flag / env                              | Default           | Efecto en caso inválido                          |
| --------------------------------------- | ----------------- | ------------------------------------------------ |
| `AUTO_ENGINE_SIM_V2`                    | **OFF**           | se interpreta como OFF (solo `1/true/yes/on`)    |
| `AUTO_ENGINE_SIM_V2_REGIME`             | sin override      | sin régimen ⇒ `UNKNOWN` ⇒ **exit-only**          |
| `AUTO_ENGINE_SIM_V2_TOP_N`              | default del motor | valor no entero ⇒ default                        |
| `AUTO_ENGINE_SIM_V2_MIN_EDGE`           | default           | no numérico ⇒ default                            |
| `AUTO_ENGINE_SIM_V2_RISK_PER_TRADE_PCT` | default           | no numérico ⇒ default                            |
| `AUTO_ENGINE_SIM_V2_MAX_POSITION_PCT`   | default           | no numérico ⇒ default                            |
| `AUTO_ENGINE_SIM_V2_MAX_SECTOR_PCT`     | default           | no numérico ⇒ default                            |
| `AUTO_ENGINE_SIM_V2_MAX_CORRELATION`    | default           | no numérico ⇒ default                            |
| `AUTO_ENGINE_SIM_V2_ATR_MULT`           | default           | no numérico ⇒ default                            |
| `AUTO_ENGINE_SIM_V2_RISK_BUDGET_PCT`    | default           | no numérico ⇒ default                            |
| `AUTO_ENGINE_SIM_V2_ATR_PCT`            | default           | no numérico ⇒ default                            |
| `AUTO_ENGINE_SIM_V2_DEFAULT_EDGE`       | default           | no numérico ⇒ default                            |
| `AUTO_ENGINE_SIM_V2_EXIT_TEMPLATE`      | `moderate`        | vacío ⇒ default                                  |
| `AUTO_ENGINE_SIM_V2_TIMEFRAME`          | `1d`              | ilegible ⇒ **sin dedupe** (fail-open consciente) |

**Nota de honestidad para el auditor:** `TIMEFRAME` es el único caso _fail-open_ documentado: con un
timeframe ilegible **no hay barra**, y sin barra no hay identidad de señal, así que no se deduplica
(y el motor puede re-emitir). Se ha preferido eso a inventar una ventana. El timeout es el mismo que
en el resto del sistema: no re-emitir es una optimización, no un invariante de seguridad.

---

## 8. Verificación

**Local (pre-tag):**

- `ruff check` + `ruff format --check` **limpios**; `mypy` **sin incidencias** (módulos tocados).
- `packages/py/application/tests`: **1546 passed**.
- `packages/py/analytics/tests` + `packages/py/infrastructure/tests`: **816 passed, 1 xfailed**.
- Suites V2/worker/AUTO + migraciones + PG: **82 passed** (incluye roundtrip de la 040 y el reinicio
  real sobre PostgreSQL).
- Dos fallos **ajenos y preexistentes** en el suite completo de `apps/api-python`
  (`integration/test_tax_report` → `403` de auth; `test_workspaces_crud` → pasa aislado). Se anotan
  como deuda, **no** se tocan en esta fase.

**En CI (esta fase añade certificación explícita de AUTO 2.0) — todo verificado GREEN antes del tag:**

- `python-ci.yml` (por commit): los herméticos nuevos entran en la batería offline
  (`test_auto_v2_entry`, `test_auto_investment_system`, `test_portfolio_decision_engine`,
  `test_position_manager`, `test_active_strategy_runtime_state`, `test_sim_durable_v2_state`) y el
  test de PG real se excluye de la batería offline (`--ignore`) para que **no** pueda skipear en
  mudo.
- `python-ci.yml`: job **nuevo** `auto-v2-durable-pg` (PostgreSQL service + `alembic upgrade head` +
  `AUTO_V2_DURABLE_PG_REQUIRED=1`) con paso _"Fail on skipped"_ — un skip invalida la certificación.
  Evidencia: run [`34972246101`](https://github.com/jvelasca/Bolsa_V1/actions/runs/34972246101),
  job en `success` (ejecutado, no skipeado).
- `release-tag-ci.yml`: `test_auto_v2_durable_pg.py` se ejecuta en `lifecycle-pg` con
  `AUTO_V2_DURABLE_PG_REQUIRED=1` (ya dentro del agregado `certify`, así que un rojo no-GREENea el
  tag). Evidencia: run [`34972246205`](https://github.com/jvelasca/Bolsa_V1/actions/runs/34972246205),
  `lifecycle-pg` y `certify` en `success`.
- Migración 040: roundtrip **downgrade/upgrade** verificado sobre PG real
  (`test_migration_040_roundtrip`). Las cabezas esperadas de las pruebas de roundtrip 036–039 se
  unifican en una constante `_ALEMBIC_HEAD` (antes duplicadas, fuente de drift al añadir migración).

---

## 9. Fuera de alcance (anotado, no tocado)

- **No** se cambia el settlement, el ledger, la idempotencia por fill ni la reconciliación.
- **No** se activa ninguna feature por defecto: `AUTO_ENGINE_SIM_V2` sigue **OFF**.
- **No** se toca LIVE (imposible por diseño: AUTO es SIM-only, `simulation_gate_allows`).
- **No** se re-diseñan los ADR ni se unifican ledger/mesa.
- **No** se arreglan los dos fallos preexistentes y ajenos de `apps/api-python` (§8).
- **No** se aborda el _fail-open_ documentado de `TIMEFRAME` ilegible (§7): se anota aquí para que
  el auditor lo valore con su severidad.

---

## 10. Respuesta esperada

**(Pendiente — no inventar PASS).** Informe con `[severidad]` y veredicto **por cada foco**, con
evidencia `archivo:línea`, y delta real `v2.39.3-beta` → `v2.40-beta`. Marca explícitamente lo que
**no** puedas verificar desde GitHub y requiera entorno local (en particular: los tests con
PostgreSQL y las verificaciones **por mutación** — revertir `_v2_restore_durable_position`, desactivar
la carga durable de señales o romper la acumulación de exposición intra-tick y comprobar que las
suites se ponen **rojas**).
