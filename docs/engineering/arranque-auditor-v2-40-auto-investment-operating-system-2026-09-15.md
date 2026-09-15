# Arranque auditor externo — V2.40 / AUTO 2.0 (Investment Operating System) (2026-09-15)

Copia en chat nuevo (auditor):

---

Eres auditor externo de Bolsa V1 **candidato V2.40**. Auditas **desde GitHub**, sin acceso al
entorno local.

- **Delta:** `v2.39.3-beta` (`b6c70595`) → tag **`v2.40-beta`** (anotado) → peeled al commit de
  sellado de `main` (el auditor lo resuelve con `git rev-list -n 1 v2.40-beta`).
- **`main`:** incluye, por encima del código, los commits de documentación de auditoría; el tag
  re-sellado apunta al commit final (el auditor lo resuelve con `git rev-list -n 1 v2.40-beta`).
- **Package:** `1.65.0-beta` · **CHANGELOG:** `[1.65.0-beta]`.
- **Alembic head:** `040_auto_v2_durable_state` — esta fase **sí añade migración** (ver Foco 5).
- **Flags:** `AUTO_ENGINE_SIM_V2` **OFF por defecto**. Con el flag sin definir, AUTO debe comportarse
  como en `v2.39.3-beta`. Los umbrales V2 se leen de env con default seguro.

**Regla:** NINGÚN estado ambiguo → NO COMPRAR. No inventes PASS. Compara **línea por línea**
`v2.39.3-beta` → `v2.40-beta` y registra P0/P1/P2/P3 con evidencia `archivo:línea`.

**Punto de entrada único:** [`audit-pack-v2.40-auto-investment-operating-system-2026-09-15.md`](./audit-pack-v2.40-auto-investment-operating-system-2026-09-15.md)

---

## Resumen del delta (qué cambió y por qué)

AUTO pasa de _orquestador de investigación + promoción de estrategias_ a **sistema operativo de
inversión**: decide qué, cuándo, cuánto, cómo gestiona y cuándo sale. **Todo** el settlement sigue
intacto y pasa por el **mismo Single Decision Spine**.

| #   | Capa             | Cambio                                                                          |
| --- | ---------------- | ------------------------------------------------------------------------------- |
| 1   | Espina (P0)      | `AutoPortfolioSnapshot`, `OpportunityRanker`, `RiskAllocator`, `SignalIdentity` |
| 2   | Decisión (P1)    | `PortfolioDecisionEngine` (cartera, fail-closed) → `TradePlan`                  |
| 3   | Gestión (P2)     | `PositionManager`: `PositionState` + `ExitPlan` + `PositionDecision`            |
| 4   | Régimen (P3)     | `MarketRegimeGate` **direccional** + `DiscoveryRegimeSource` (barras reales)    |
| 5   | Durabilidad (P4) | Migración **040**: `position_state` (JSONB) + `sim_consumed_signals`            |
| 6   | Cableado         | `auto_v2_entry.py` + `AutoSimulationWorker`, **flag OFF por defecto**           |
| 7   | CI               | Batería offline + job PG nuevo `auto-v2-durable-pg` (fail-if-skipped)           |

---

## Foco 1 — La espina cognitiva es determinista, pura y no puede inventar datos

**Lee (fuentes reales, no solo docs):**

- `packages/py/analytics/src/bolsa_analytics/cognitive/auto_portfolio_snapshot.py`
- `packages/py/analytics/src/bolsa_analytics/cognitive/opportunity_ranker.py`
- `packages/py/analytics/src/bolsa_analytics/cognitive/risk_allocator.py`
- `packages/py/analytics/src/bolsa_analytics/cognitive/signal_identity.py`
- `packages/py/analytics/src/bolsa_analytics/cognitive/market_regime_gate.py`

**Foco:**

1. ¿`AutoPortfolioSnapshot` es inmutable (`frozen`) y su `as_of` proviene de **una** lectura
   coherente del tick (dos símbolos no pueden ver libros distintos)?
2. ¿El ranker es una **función total** (mismo input ⇒ mismo output) y con **orden estable** ante
   empates? ¿Un empate puede producir un orden dependiente del orden de iteración?
3. ¿`RiskAllocator` garantiza `qty` **nunca** > tope por posición ni > presupuesto de riesgo, y qué
   devuelve con ATR ausente/cero (¿rechazo o sizing inventado)?
4. ¿`signal_identity` es **fail-closed** ante timeframe ilegible o `moment` sin tz (`None`, no una
   barra adivinada)?
5. ¿Los módulos respetan el contrato `analytics-market-independence` (sin imports de market/app)?

---

## Foco 2 — El decider de cartera no puede dejar pasar una violación **conjunta**

**Lee:** `packages/py/application/src/bolsa_application/portfolio_decision_engine.py`

**Foco:**

1. Enumera **todos** los `return` con `approved=False` y comprueba que cada uno deja
   `reason_codes` (una negativa sin motivo es un fallo de auditoría).
2. **Exposición acumulada intra-tick:** si dos oportunidades se aprueban en el **mismo** tick, ¿la
   segunda ve el efecto de la primera (sector/correlación/riesgo) o ambas ven el estado previo y
   pueden violar el límite **en conjunto**? Intenta romperlo con un caso de dos señales del mismo
   sector en el mismo tick.
3. ¿Los vetos son **fail-closed** con dato ausente (sector desconocido, correlación no calculable,
   régimen `UNKNOWN`)?
4. ¿El `TradePlan` emitido es autoconsistente (stop del lado correcto, objetivos coherentes con
   dirección y R)? ¿`trade_plan_to_decision_package` **relaja** alguna guarda del contrato legado?

---

## Foco 3 — La gestión por posición no puede re-disparar un parcial ni empeorar un stop

**Lee:** `packages/py/application/src/bolsa_application/position_manager.py` +
`position_state.py` (pre-existente, DEX-5) + `tests/test_position_manager.py`

**Foco:**

1. ¿Un T1 parcial puede **re-dispararse** en ticks sucesivos, o el estado (`target1_leg.status`) lo
   impide de forma **durable**?
2. ¿`regime_exit` (exit-only) tiene **precedencia** sobre cualquier otra intención, incluida una
   mejora de stop?
3. ¿`clamp_stop_not_worsen` impide **siempre** empeorar el stop y el `high_watermark` sobrevive al
   reinicio?
4. ¿El cierre por protección mantiene la **atribución de versión** de estrategia (la serie
   observada no debe truncarse en NULL)?

---

## Foco 4 — Régimen y sector: "no lo sé" no puede convertirse en "permitido"

**Lee:** `packages/py/application/src/bolsa_application/auto_v2_entry.py`
(`DiscoveryRegimeSource`, `tunables_from_env`), `market_regime_gate.py`, y el writer del journal
(`payload["sector"]`).

**Foco:**

1. ¿`DiscoveryRegimeSource` deriva el régimen del clasificador **determinista de barras** y es
   **fail-closed** (error ⇒ `UNKNOWN` ⇒ **exit-only**, nunca entradas)?
2. ¿`MarketRegimeGate` es **direccional** (un `BULL_TREND` **no** autoriza cortos)? Verifícalo por
   mutación: quitar la dirección del gate ¿pone rojo algún test?
3. ¿Existe **algún** camino donde "sector desconocido" se convierta en "sin restricción de sector"?
   ¿El sector llega al journal para poder auditar después la decisión?

---

## Foco 5 — Durabilidad V2 (migración 040): ningún crash puede degradar la operativa

**Lee:**

- `packages/py/infrastructure/alembic/versions/040_auto_v2_durable_state.py`
- `packages/py/application/src/bolsa_application/sim_durable_store.py`
  (`SimConsumedSignalStore`, `SimDurableUnitOfWork`, `SimPositionProjection`)
- `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py`
  (`_v2_durable_state`, `_persist_position`, `readopt_positions`, `_v2_restore_durable_position`,
  `_v2_load_consumed_signals`, `_v2_mark_signal_consumed`, `_v2_prune_consumed_signals`,
  `_v2_roll_consumed_bar`, `_v2_adopt_position`)

**Foco:**

1. ¿La 040 hace roundtrip limpio (`downgrade` borra columna y tabla) y `down_revision` es
   `039_research_trials_regime`?
2. `position_state` es **nullable** a propósito. ¿Está justificado, o hay un camino donde "sin plan"
   se trate como "sin stop" (posición huérfana)?
3. Si el proceso muere **entre** el fill y la persistencia del plan, ¿el reinicio deja la posición
   sin gestión o el fallback `adopted` garantiza stop vivo (y **queda auditado** como adoptado)?
4. ¿Un plan durable **obsoleto** puede resucitarse sobre un símbolo reabierto? ¿El cierre/limpieza
   de la posición limpia también el plan?
5. ¿`position_state` rehidratado **re-ancla la cantidad al ledger** (el ledger manda en el CUÁNTO y
   el plan en el CÓMO), de modo que no puede aparecer cantidad fantasma?
6. ¿La clave de dedupe incluye instrumento + acción + **versión de estrategia** + barra (dos
   estrategias distintas sobre el mismo símbolo/barra **no** deben bloquearse)?
7. ¿`_v2_mark_signal_consumed` se invoca **solo** tras fill confirmado (nunca si el spine veta:
   kill switch / sim gate / RiskGate / sin fill)? Una señal quemada sin fill prohibiría una entrada
   legítima.

---

## Foco 6 — Nada de esto puede tocar el dinero ni saltarse el spine

**Lee:** `auto_v2_entry.py`, `trade_plan_to_decision_package`, `AutoSimulationWorker`
(`_v2_plan_tick`, `_settle`, camino de ejecución).

**Foco:**

1. Con `AUTO_ENGINE_SIM_V2` **sin definir**, ¿el comportamiento es el de `v2.39.3-beta`? Cúbrelo con
   `test_v2_off_by_default_keeps_legacy_path`.
2. ¿Alguna intención V2 puede llegar al settlement **sin** `risk_gate_auto_paper_dry` y
   `simulation_gate_allows`?
3. ¿Una excepción del pipeline V2 se traduce en **no operar** (fail-closed) y no en operar por el
   camino clásico "de rebote"?
4. ¿Con el flag OFF el readopt durable y la marca de señales quedan **inertes** (no escriben más que
   `v2.39.3-beta`)?
5. **Verifica por mutación:** romper la acumulación de exposición intra-tick y desactivar la carga
   durable de señales ¿ponen **rojas** las suites correspondientes?

---

## No pedir

LIVE · bump de versiones · unificar ledger/mesa · re-diseñar ADR · activar `AUTO_ENGINE_SIM_V2` por
defecto · arreglar los dos fallos preexistentes y ajenos de `apps/api-python`
(`integration/test_tax_report` → `403` de auth; `test_workspaces_crud` → pasa aislado) · features
fuera del alcance. La regla de **fail-closed** y los gates CPCV/PBO/DSR/WFE/OOS **no se relajan**.

---

## Respuesta esperada

**(Pendiente — no inventar PASS).** Informe con `[severidad]` y veredicto **por cada foco**, con
evidencia `archivo:línea` y el delta real `v2.39.3-beta` → `v2.40-beta`. Marca explícitamente lo que
**no** puedas verificar desde GitHub y requiera entorno local (en particular, los tests con
PostgreSQL y las verificaciones **por mutación**).
