# Arranque del auditor — V2.42 / AUTO-2 · slice 2b: `TIME_EXIT`, `THESIS_EXIT`, ATR real y cierre de H-1..H-7 (`1.67.1-beta`)

> **Para quién es esto:** la persona (o el agente) que audita `v2.42.1-beta` sin acceso al entorno de
> desarrollo. Orden de lectura, afirmaciones verificables, mapa de código, comandos y preguntas abiertas.
> **Pack completo:** [`audit-pack-v2.42.1-auto-2-slice-2b-2026-09-17.md`](./audit-pack-v2.42.1-auto-2-slice-2b-2026-09-17.md).
> **Base sobre la que se asienta:** [`audit-pack-v2.42-auto-2-position-lifecycle-2026-09-17.md`](./audit-pack-v2.42-auto-2-position-lifecycle-2026-09-17.md)
> (slice 2a, tag `v2.42-beta`). Su **§9** es el origen de los siete hallazgos que este slice cierra: si
> vas a auditar 2b, **lee el §9 primero** — ahí está la lista de lo que estaba mal.
> **Decisiones de alcance firmadas por el owner:** [`traspaso-relevo-post-v2-42-auto-2-2026-09-17.md`](./traspaso-relevo-post-v2-42-auto-2-2026-09-17.md) §4.2 (D1..D6).
> **Hoja de ruta:** [`roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md`](./roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md) §4.

**Bump:** `1.67.0-beta` → `1.67.1-beta`. **Migración: NINGUNA** (Alembic head sigue en
`042_portfolio_reservations`; el techo y el nivel de invalidación viven en el JSONB
`sim_auto_positions.position_state`, decisión **D5**).

**Alcance del slice:** cierra **E1** (`TIME_EXIT`), **E2** (ATR real cableado y medido, veto tras flag) y
**E3** (`THESIS_EXIT`, con la firma **D2** del owner) y los **siete hallazgos de código** del §9 de 2a
(H-1..H-7). **Fuera:** la evidencia de journal de un **día completo** en producción, la entrada del
régimen en el FSM como evento con motivo propio (`REGIME_EXIT` existe en el camino legacy, con
precedencia absoluta, pero **no** es un evento del FSM), `RISK_EXIT` (llega con el gobernador de `AUTO-3`)
y flipar el veto de ATR (D3 pedía medir primero).

---

## 1. Qué afirma esta versión (y qué no)

**Afirma**

1. Una posición tiene **techo de mantenimiento congelado** en su nacimiento y, alcanzado, **vende** con
   motivo `time_exit`; el FSM lo registra como `TIME_EXIT`.
2. Una **tesis invalidada confirmada vende** (`EXIT`, no `REVIEW`), con el nivel de invalidación
   congelado y el **peor adverso persistido** como testigo; un stop-out **no** se disfraza de salida por
   tesis.
3. La **marca del tick** (pico del trailing y `maeR`) **persiste** cuando cambia, con dos sensores
   independientes cada uno con su test (H-2).
4. El **ATR real** se usa cuando hay barras y su origen se **declara** en el journal; con
   `AUTO_ENGINE_SIM_V2_ATR_REQUIRED=1` (default **OFF**) una señal sin ATR real **no entra** y cae por
   `atr_unknown`.
5. Los **siete hallazgos** del §9 de 2a están cerrados, cada uno con su mutación medida (13/13 rojos).

**No afirma**

- **No** afirma haber medido **PG real** en la máquina del slice: el DSN local **cuelga** (medido). Los
  tests PG son la evidencia **de CI**.
- **No** afirma que el **criterio de salida de `AUTO-2`** esté completo: falta **evidencia de journal de
  un día completo** y `REGIME_EXIT`/`RISK_EXIT` (roadmap §4).
- **No** afirma que el veto de ATR esté listo para producción: nace **OFF** a propósito (D3).

---

## 2. Qué cierra exactamente (y de dónde venía)

| Deuda de 2a                                                        | Qué la cierra                                                                |
| ------------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| `TIME_STOP` inalcanzable (`expires_at` nunca llegaba)              | `resolve_holding_horizon` + `holdingDeadlineAt` + `_v2_journal_exit_request` |
| `THESIS_INVALIDATION ⇒ REVIEW` (la posición sobrevivía a su tesis) | `is_thesis_invalidated` + D2 en `position_decision` + evento `THESIS_EXIT`   |
| ATR sintético fabricado en el origen                               | `AtrSource` + `_v2_atr_geometry` + `atr_unknown` + veto tras flag            |
| Marca adversa no durable                                           | `_mark_observation_changed` (pico y `maeR`, dos sensores)                    |
| §9 H-1..H-7                                                        | `position_lifecycle` / `position_state` + sus tests y mutaciones             |

---

## 3. Dónde mirar el código (mapa mínimo)

| Zona                                 | Fichero                                                                           | Qué mirar                                                                                                                 |
| ------------------------------------ | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Horizonte (puro)                     | `packages/py/analytics/src/bolsa_analytics/cognitive/exit_policy.py`              | `resolve_holding_horizon`, `HoldingHorizon`, `DEFAULT_MAX_HOLDING_PERIOD_DAYS`                                            |
| Estado tipado y rehidratación (puro) | `.../cognitive/position_state.py`                                                 | `holding_deadline_at`, `invalidation_price`, `_invalidation_level`, H-5/H-6                                               |
| Juicio de la tesis (puro)            | `.../cognitive/exit_plan.py`                                                      | `worst_adverse_price`, `is_thesis_invalidated`                                                                            |
| FSM (puro)                           | `.../cognitive/position_lifecycle.py`                                             | `TIME_EXIT`/`THESIS_EXIT`, `_LIFECYCLE_LADDER`/`_forward_target` (H-7), H-1, H-3, H-4                                     |
| Decisión (puro)                      | `.../cognitive/position_decision.py`                                              | D2 (`EXIT` por invalidación), `_next_event` → `TIME`                                                                      |
| Worker                               | `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py`              | `_v2_journal_exit_request`, `_v2_atr_geometry`, `_v2_atr_journaled`, `_mark_observation_changed`, `_v2_protect_noop_stop` |
| Entrada/ATR                          | `packages/py/application/src/bolsa_application/auto_v2_entry.py`                  | `AtrSource`, `atr_required`, `_as_ohlcv_bar`                                                                              |
| Motivos                              | `packages/py/application/src/bolsa_application/auto_reason_codes.py`              | `TIME_EXIT`, `THESIS_EXIT`, `ATR_GEOMETRY`, `ATR_SOURCE_*`                                                                |
| Decisión de cartera                  | `packages/py/application/src/bolsa_application/portfolio_decision_engine.py`      | `atr_unknown`                                                                                                             |
| Tests herméticos de excepción        | `packages/py/analytics/tests/test_exit_plan.py`, `.../test_position_lifecycle.py` | E1/E3, H-1..H-7                                                                                                           |
| Tests de worker                      | `apps/api-python/tests/test_auto_v2_lifecycle_clock_thesis.py` (nuevo, 11 tests)  | E1/E2/E3 punta a punta                                                                                                    |
| Tests PG                             | `apps/api-python/tests/test_auto_v2_lifecycle_pg.py` (6 nuevos)                   | durabilidad del techo, la invalidación y la geometría                                                                     |

---

## 4. Cómo verificar (comandos listos)

```bash
# 1) Suites herméticas del slice (segundos)
uv run pytest packages/py/analytics/tests/test_position_lifecycle.py \
    packages/py/analytics/tests/test_exit_plan.py \
    packages/py/analytics/tests/test_position_decision.py \
    packages/py/application/tests/test_auto_v2_entry.py \
    packages/py/application/tests/test_position_manager.py \
    packages/py/application/tests/test_v127_golden_path_fail.py \
    apps/api-python/tests/test_auto_v2_lifecycle_clock_thesis.py \
    apps/api-python/tests/test_auto_v2_worker_integration.py -q

# 2) PG real (durabilidad). Un skip es FALLO.
AUTO_V2_LIFECYCLE_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_auto_v2_lifecycle_pg.py -q

# 3) Estático con la invocación EXACTA de CI (NO añadas packages/py/analytics/src)
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
    packages/py/application/src apps/api-python/src --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter
```

### Matriz de mutación (13 mutaciones, 13 rojos)

Reproducible con el script declarado en §7 del pack. Las que más valor tienen para un auditor nuevo:
**M2** (el techo no se congela: 5 rojos), **M12** (la escalera retrocede: H-7), **M13** (la marca no
persiste por `maeR`) y **M5** (la conducta de 2a vuelve a `REVIEW`). Si alguna **no** cae en tu árbol, no
concluyas "el pack miente": falta el test que la mata ⇒ se declara y se añade.

### Ya auditado (2026-09-17, slice 2a) — **no repitas lo hecho, amplía**

- FSM: transiciones inválidas rechazadas, producto cartesiano total, degradación fail-closed.
- Ratchet real, `PROTECT` no mudo (ahora con H-2), trailing en R y clamp nunca-empeorar.
- Durabilidad PG del estado y de las señales consumidas.
- El sello del tag `v2.42-beta` y sus runs de CI.
- **Lo que sí queda por romper de 2a/2b está en §9 del pack de 2b** (seis preguntas concretas).

---

## 5. Preguntas abiertas que el auditor debería intentar romper

1. **E1**: ¿existe algún camino que **recalcule** el techo después del nacimiento (debe ser inmutable)?
2. **E1**: ¿puede `TIME_STOP` dispararse **sin** `expires_at` (hint gratis = dinero)?
3. **E3**: ¿puede `is_thesis_invalidated` decir "sí" sin nivel declarado, o el journal atribuir
   `thesis_exit` a un stop-out?
4. **E2**: ¿puede el worker fabricar geometría sintética **sin** declararla, o el veto activarse dejando
   entrar la candidata?
5. **H-2**: ¿hay un cambio de marca (pico **o** `maeR`) que **no** se persista? Son dos sensores: el
   test que los separa es la clave.
6. **H-7**: ¿hay una secuencia de eventos que haga retroceder un estado por la escalera
   `OPEN < PROTECTED < T1_REACHED < PARTIAL_EXIT < TRAILING < EXIT_PENDING < CLOSED`?
7. **H-1**: ¿se puede salir de `RECONCILIATION_REQUIRED` con una cantidad que contradice el estado
   resuelto?
8. **CI**: ¿existe alguna **ruta inexistente** en las listas de `python-ci.yml`/`release-tag-ci.yml`? Con
   la invocación de pytest eso es **exit 4** (job rojo), y no lo ve un runner que use una copia a mano de
   la lista: en esta fase pasó y se corrigió antes del sello (§8.2 del pack). Un buen chequeo de apertura
   es comparar cada ruta de los dos `run:` con el sistema de ficheros.
9. **Alcance**: ¿el slice declara en algún sitio algo que no haya medido? (el pack declara
   explícitamente que **PG no se midió en local**: si encuentras una afirmación de lo contrario, es un
   hallazgo).
