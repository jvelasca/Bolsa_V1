# Evidencia `v2.88.84-beta` — `AUTO · TOP3`: **productor durable del TOP3 cross-asset + degradación explícita**

**Producto:** `V2.88.84-beta` · **Package:** `2.11.84-beta` · **AsOf:** 2026-10-07. **Sin migración nueva** (head `052_top3_opportunities`). **`Δ motor = 0`** (el TOP3 persistido es observabilidad: no vuelve a la decisión, y el scoring del plan recibe el MISMO `evidence` leído una sola vez). **Contrato HTTP sin cambio**. **Tag anotado** por crear.

**Padre de producto:** [`v2.88.83`](../v2.88.83/README.md). Auditoría que motivó el sello:
[`auditoria-composition-root-evidence-top3-v2.88.83-2026-10-07.md`](../../auditoria-composition-root-evidence-top3-v2.88.83-2026-10-07.md).

## Qué cambia

Cierra los DOS huecos no bloqueantes que dejó abiertos la auditoría de `v2.88.83`, sin tocar el motor:

1. **Productor del TOP3 cross-asset (el que faltaba).** La cadena `OpportunityBoard` →
   `select_top3_assets` → `PostgresTop3OpportunitySink` (tabla `top3_opportunities`, migración
   052) estaba probada pero **sin llamante productivo**: `GET /top3-opportunities/latest`
   devolvía siempre `runId=""`. Ahora `AutoSimRuntime.run_tick` compone
   `build_top3_opportunity_sink(session)` por sesión/tick y el worker escribe la foto del TOP3
   desde el ranking REAL del tick (`plan.ranked`), **una por barra** (`_v2_top3_bar`).
2. **Degradación explícita.** Un activo puntuado sin campeón ACTIVE (scoring histórico
   `edge`+`liquidity`) lleva el motivo `scoring_historico_sin_campeon` en su slot y se declara
   en el log. Antes, un slot puntuado a ciegas se leía igual que uno con evidencia.

## Invariantes de honestidad (no negociables)

- El TOP3 se escribe desde el **ranking real** del tick (los mismos `OpportunityScore` que el
  motor usó), nunca desde un cómputo paralelo.
- La `evidence` del plan y la procedencia declarada por slot salen del **MISMO** lookup leído
  una sola vez en el tick.
- Sin sink inyectado es un **no-op** (`Δ = 0`). Un fallo del sink se **declara** y no tumba el
  turno (es observabilidad, no decisión).
- `asset_id` es el **activo base**: una clave de candidata `SÍMBOLO#versión`
  (`allow_distinct_strategies`) se colapsa al símbolo.

## Verificación

- **Hermético (aplicación):** `packages/py/application/tests/test_top3_opportunities.py` —
  `test_select_top3_records_declares_historical_scoring` y
  `test_select_top3_records_collapses_candidate_key_to_asset`.
- **PG end-to-end (API):** `apps/api-python/tests/test_auto_v88_84_top3_producer_pg.py`.
  - Bloque A — `_v2_persist_top3` escribe la tabla 052 UNA vez por barra e inyecta el motivo por
    slot (`reasons == []` con evidencia; `reasons == ["scoring_historico_sin_campeon"]` sin
    ella) y la segunda llamada dentro de la misma barra es un no-op.
  - Bloque B — `AutoSimRuntime.run_tick` (ruta de producción, sin inyectar el sink) deja el TOP3
    LEÍDO por el repositorio: el activo con campeón ACTIVE sale sin motivo y con sus componentes
    LAB; el activo sin campeón sale declarado. **Falsable:** si se elimina
    `top3_opportunity_sink=` de `run_tick`, el Bloque B se cae (verificado por mutación).
- **Censo de CI:** el fichero nuevo queda cubierto por `python-ci.yml` (suite
  `auto-v2-durable-pg`) y `release-tag-ci.yml` (suite `lifecycle-pg`) e ignorado en los pases
  offline (`test_ci_test_selection_census.py` verde).
- **Suite:** `ruff`, `mypy` y pytest (paquetes + API) verdes.
- **Sello DÍA-D:** `test_dia_d_bump_guard` verde — los CLI `v2_89`…`v2_97` (`meta.bump`) sellan
  `2.11.84-beta` junto al `package.json` (sin este paso, el bump dejaba el guardián rojo).

## Qué no cambia

Núcleo financiero (`ExecuteTrade`, ledger, posiciones, settlement), el scoring del plan
(`plan_v2_tick` recibe el MISMO `evidence`) y el contrato HTTP. El tag `v2.88.76-beta`
permanece; el tag anotado de este sello se crea en el paso POST-TAG.

## Cita POST-TAG

Pendiente: tag anotado `v2.88.84-beta` + `Release tag CI` VERDE + `replay-repro` reproducido
(⇒ `Δ motor` confirmado por CI).
