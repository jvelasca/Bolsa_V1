# Plan — `v2.79` / `AUTO-MATERIAL-7`: OPERABILITY CENSUS

> **AsOf:** 2026-09-27 · **Estado:** **propuesta** (requiere **ratificación del propietario**:
> rótulo `AUTO-MATERIAL-7`, bump `2.03.0-beta → 2.04.0-beta` y alcance).
> **Origen:** auditoría externa de `v2.78-beta` → `H-1` (MEDIUM), `H-2` (LOW), `H-3` (LOW).
> **Base:** `v2.78-beta` (`2.03.0-beta`) · **Alembic head:** `046_fill_reference_mid` (**SIN migración**).
> **Freeze:** `auto_simulation_worker.py` **intacto** · **Reparto:** `auto18-v1` / `auto15-v1`
> (`ALLOCATION = none`).

## 1. Motivo

`v2.78` separó las **atribuciones** de los **vetos** en la lectura de la operabilidad
(`split_journal_reasons`), pero el **censo seguía poblándose con todas las entradas del journal**. El
worker congelado anexa a ese mismo journal los eventos de **gestión de posición** (`event =
"auto_position_management"`, más los eventos `auto_position_decision`/`auto_position_skip` del motor
AUTO), cuyos motivos (`protect_requested`, `stop_ratchet_*`, `atr_geometry`, `lifecycle_*`,
`reconciliation_required`, `no_mark_data`, `fill_not_materialized`, `reservation_created`,
`reservation_released_fill`) **no son vetos de entrada**. Medido por la auditoría de `v2.78`:

```
journalReasons = ["regime_invalid:2", "approved:3", "risk_exit:1", "protect_requested:1"]
turnTotals     = {"vetoes": 2, ...}
=> vetoes=2  vetoCounted=3  other={'protect_requested': 1}
```

Es decir: el censo por familias se leía como **cota superior** justo en los días que **sí operan**, que
es cuando el propietario lo lee. `H-1` reabre `P3-6` para su caso general.

## 2. Invariante

> **El censo de vetos mide SOLO decisiones de ENTRADA.** Un evento de **gestión de posición** se
> **publica** por su canal propio (`positionEventByCode`) y **nunca** se cuenta como veto; **ninguna
> entrada del journal se descarta**.

Corolarios que la fase debe poder afirmar:

1. `vetoCounted` = Σ `reasonCodes` de los eventos de **entrada** (menos `approved`, que es atribución).
2. Los motivos de gestión de posición aparecen **exactamente una vez**: en `positionEventByCode`, no
   en `vetoByBucket`.
3. La partición `VETO_BUCKET_BY_REASON ∪ NON_VETO_REASON_CODES` es **exhaustiva y disjunta** sobre
   **todo** el vocabulario que puede llegar a `reasonCodes` (no solo `DecisionReasonCode`).
4. Las filas **ya escritas** (que mezclan ambos eventos) siguen leyéndose sin inflar `vetoCounted`.

## 3. Alcance (archivos)

| Fichero | Cambio |
|---|---|
| `packages/py/application/src/bolsa_application/auto_reason_codes.py` | publicar `POSITION_ATTRIBUTION_REASONS` (miembros **explícitos**; **excluye** los vetos de reserva `reservation_failed`/`reservation_unmeasurable`/`reservation_already_live`) |
| `packages/py/application/src/bolsa_application/market_operability.py` | constante `ENTRY_DECISION_EVENT`; conjunto `POSITION_JOURNAL_EVENTS`; puro `collect_journal_reasons(entries, *, events)`; `VETO_BUCKET_BY_REASON` declara `OPTIMIZER_REASONS` + `ADAPTIVE_STRATEGY_PAUSED` + los dos vetos fail-closed de reserva; `NON_VETO_REASON_CODES` incorpora `POSITION_ATTRIBUTION_REASONS`; `build_operability_record` publica `positionEventByCode`/`positionEventCounted`; render añade la línea `eventos/posicion: … (NO son vetos)` solo si existe |
| `apps/api-python/scripts/v2_76_forward_market_material.py` | `_journal_reasons` cuenta **solo entrada** (`ENTRY_DECISION_EVENT`); nuevo `_journal_position_reasons` (`POSITION_JOURNAL_EVENTS`); clave **aditiva** `positionEventReasons` en el JSON |
| `packages/py/application/tests/test_market_operability.py` | contrato exhaustivo de **todos** los dueños (`H-2`), disjunción (`H-3`), fixture del ejemplo de reversión, canal de posición publicado y descartado, contrato de eventos pined contra el productor |
| `apps/api-python/scripts/v2_44_mutation_audit.py` | `M214`–`M219` (matriz **213 → 219**) |
| `package.json` | `2.03.0-beta` → `2.04.0-beta` |
| `docs/engineering/*-v2-79-*`, `PROJECT_STATE.md`, `engineering-index-…`, `CHANGELOG.md` | docs de fase + índice + sello |

**No** se toca: `auto_simulation_worker.py` (congelado), `portfolio_decision_engine.py`,
`opportunity_ranker.py`, `market_regime_gate.py`, `paper_material_readiness.py`, ni ningún workflow
(`test_market_operability.py` ya está registrado explícito en `python-ci.yml` y `release-tag-ci.yml`).

## 4. Pasos

1. **Dueño** (`auto_reason_codes.py`): `POSITION_ATTRIBUTION_REASONS` = `POSITION_LIFECYCLE_REASONS` ∪
   `MATERIALIZATION_REASONS` ∪ `POSITION_SKIP_REASONS` ∪ `{no_mark_data, reservation_created,
   reservation_released_*}`. Se compone **por miembros**, jamás uniendo `RESERVATION_REASONS` entero
   (contiene vetos reales).
2. **Población** (`market_operability.py`): `collect_journal_reasons` es la **única puerta** del censo;
   `ENTRY_DECISION_EVENT = "auto_entry_decision"`; `POSITION_JOURNAL_EVENTS = {auto_position_management,
   auto_position_decision, auto_position_skip}`.
3. **Contrato de veto** (`market_operability.py`): declarar los `OPTIMIZER_REASONS` (default `risk`,
   con `top_n`/`liquidity`/`data` explícitos), `ADAPTIVE_STRATEGY_PAUSED` (`risk`),
   `reservation_unmeasurable` y `reservation_already_live` (`risk`).
4. **Canal de posición** (`market_operability.py`): `positionEventByCode`/`positionEventCounted` +
   línea de render. **No** se descarta el dato.
5. **Runner** (`v2_76_…py`): separar los dos canales en el JSON (aditivo, sin romper consumidores).
6. **Tests**: `H-2`, `H-3`, canal de posición (publicado/descartado), ejemplo de reversión, legacy.
7. **Mutaciones** `M214`–`M219` y matriz completa.
8. **Sello**: bump, docs, índice, `CHANGELOG`, tag `v2.79-beta`.

## 5. Criterios de aceptación

- `ruff` limpio · import-linter `4 kept, 0 broken` · `mypy` `0 issues` · head `046`.
- `test_market_operability.py`: **37 → 48 passed** (los puros de la fase).
- Con el ejemplo de reversión: `vetoCounted == vetoes == 2`, `other` vacía, `positionEventCounted == 1`.
- `M214`–`M219` **muerden** y restauran **byte a byte**; matriz completa **219/219**.
- Árbol idéntico antes/después de la matriz; `git status` limpio tras el sello.

## 6. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| El runner deja de ver un motivo al filtrar por evento (se pierde el diagnóstico) | el canal de posición es **aditivo** y se publica; ningún conteo se descarta |
| Un evento desconocido (de una fase futura) cae fuera de ambos conjuntos | `collect_journal_reasons` con `events=None` sigue agregando todo; el canal de entrada/posición se declara como contrato del **lector** |
| Los literales de evento del lector divergen de los del productor | test que pinea `ENTRY_DECISION_EVENT`/`POSITION_JOURNAL_EVENTS` contra `auto_investment_system`/`auto_v2_entry` (**sin** editarlos) |
| Cambiar de familia códigos del optimizador altera lecturas históricas | es **lectura**: el histórico se puede releer; el cambio se declara en el `CHANGELOG` |

## 7. Fuera de alcance

- Material PAPER real / ventana de mercado (`P3-2`/`P3-3`): **no** se aborda aquí.
- El `freeze` del worker y el gobernador: **no** se tocan.
- `OBS-5` (el parser descarta conteos `<= 0` ante mapping crudo): queda declarada.

## 8. Decisión pendiente del propietario

Ratificar (a) el rótulo **`AUTO-MATERIAL-7`**, (b) el bump a **`2.04.0-beta`** y (c) el alcance de
arriba. La auditoría de `v2.78` ya está emitida y su remediación natural es exactamente esta fase.
