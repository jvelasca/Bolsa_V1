# Arranque del auditor — `v2.79-beta` (`AUTO-MATERIAL-7`: OPERABILITY CENSUS)

> **AsOf:** 2026-09-27 · **Objeto:** tag **anotado** `v2.79-beta` → commit del sello (feat + docs) ·
> **Versión:** `2.04.0-beta` · **Base (diff):** `v2.78-beta` (`2.03.0-beta`) · **Alembic head:**
> `046_fill_reference_mid` (**SIN migración**)
> **Freeze:** `auto_simulation_worker.py` **intacto** · **Reparto:** `auto18-v1` / `auto15-v1`
> (`ALLOCATION = none`).
> **Regla de lectura:** esta fase **corrige el INSTRUMENTO de lectura**, no decide. Cierra `H-1`
> (MEDIUM), `H-2` (LOW) y `H-3` (LOW) de la auditoría de `v2.78` **sin** tocar el motor, el
> gobernador, `TOP_N` ni un umbral.

## Qué auditar (12 puntos)

1. **El freeze no se toca**: `auto_simulation_worker.py`, `portfolio_decision_engine.py`,
   `opportunity_ranker.py`, `market_regime_gate.py`, `aggregate_trial_regime`, `TOP_N` y
   `paper_material_readiness.py` **idénticos** a `v2.78-beta`. El runner cablea el worker; no lo edita.
2. **`H-1` — el censo es de ENTRADA**: `collect_journal_reasons(entries, *, events)` es la **única
   puerta** del censo; el runner la llama con `{ENTRY_DECISION_EVENT}`. Un evento
   `auto_position_management` (`protect_requested`, `atr_geometry`, …) **no** puede entrar en
   `vetoCounted`. Verifica con `_AUDIT_REVERSAL_DAY`: `vetoCounted == vetoes == 2`, `other` vacía.
3. **`H-1` — el canal de posición se PUBLICA, no se descarta**: `positionEventByCode`/
   `positionEventCounted` salen de `positionEventReasons`; el render añade
   `eventos/posicion: … (NO son vetos)` **solo** si existe. ¿Puede perderse un conteo de posición?
4. **`H-1` — compatibilidad legacy**: una fila antigua con `journalReasons` **mezclado** sigue
   separando las atribuciones por `NON_VETO_REASON_CODES` (que ahora incluye
   `POSITION_ATTRIBUTION_REASONS`), sin re-inflar `vetoCounted`.
5. **`H-2` — contrato exhaustivo de TODOS los dueños**:
   `test_every_owner_reason_code_is_declared_exactly_once` recorre
   `DecisionReasonCode ⊕ TOP_N_EXCLUDED ⊕ OPTIMIZER_REASONS ⊕ ADAPTIVE_STRATEGY_PAUSED ⊕
   DAY_EXIT_REASONS ⊕ POSITION_SKIP_REASONS ⊕ MATERIALIZATION_REASONS ⊕ RESERVATION_REASONS ⊕
   POSITION_LIFECYCLE_REASONS ⊕ NO_MARK_DATA`. Busca un `Literal` de motivos que alimente el journal
   y quede fuera. Los vetos fail-closed de reserva (`reservation_unmeasurable`,
   `reservation_already_live`) deben **tener familia**.
6. **`H-3` — disjunción**: `VETO_BUCKET_BY_REASON ∩ NON_VETO_REASON_CODES == ∅`, y
   `POSITION_ATTRIBUTION_REASONS` **excluye** los tres vetos de reserva (`reservation_failed`,
   `reservation_unmeasurable`, `reservation_already_live`). Comprueba que no se ha descatalogado
   ninguno como "no-veto".
7. **Contrato de eventos pined contra el productor**:
   `test_position_event_constants_match_the_producer_payloads` exige `ENTRY_DECISION_EVENT ==
   EVENT_ENTRY_DECISION` (de `auto_investment_system`), que `EVENT_POSITION_DECISION`/
   `EVENT_POSITION_SKIP` estén en `POSITION_JOURNAL_EVENTS`, y que un
   `build_position_management_journal_entry` real emita un evento del conjunto. Verifica que el
   lector **no** edita el productor.
8. **Sin migración y sin umbrales movidos**: `alembic heads` = `046_fill_reference_mid`; `min cycles`
   32, `min R`, `folds` 3, `min_is` 8, `min_oos` 4, `min_episodes` **intactos**;
   `DATA_GATE_POLICY_VERSION` sigue `auto15-v1`.
9. **Mutaciones**: `M214`–`M219` deben **morder** y restaurar **byte a byte**; la matriz pasa de
   **213/213** a **219/219**. Reejecuta la matriz **completa** y comprueba el árbol al final.
10. **CI sin huecos nuevos**: `test_market_operability.py` sigue registrado **explícito** en el job
    `quality` de `python-ci.yml` y en el job `python` de `release-tag-ci.yml`; **ningún** workflow
    cambia. El job `python` del tag debe subir en **+11** respecto a `v2.78` (los casos nuevos).
11. **La sonda I/O sigue read-only**: `v2_77_market_operability.py` no se modifica ni abre
    PostgreSQL; el journal vive en `operability_runs/` (gitignoreado).
12. **El runner sigue sin escribir material por su cuenta**: `v2_76_forward_market_material.py` solo
    **lee** el journal en memoria (`_journal_reasons`/`_journal_position_reasons`); el `--out` sigue
    siendo la única escritura y `--preflight-only` sigue sin escribir.

## Evidencia que debes mirar (cruda, en `docs/engineering/`)

| Fichero | Qué acredita |
|---|---|
| `evidencia-matriz-mutaciones-v2.79-219-2026-09-27.txt` | 219/219, restauración byte a byte, árbol intacto, mordida de `M214`–`M219` |
| [`auditoria-v2-78-…`](./auditoria-v2-78-auto-material-6-operability-accounting-2026-09-27.md) | el veredicto `H-1`/`H-2`/`H-3` que esta fase remedía |
| `evidencia-auditoria-v2.78-2026-09-27.txt` | identidad y compuertas de la auditoría de `v2.78` |

## Comandos

```bash
git clone https://github.com/jvelasca/Bolsa_V1.git && cd Bolsa_V1
git checkout v2.79-beta && uv sync
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
    packages/py/application/src apps/api-python/src --follow-imports=silent
cd packages/py/infrastructure && uv run alembic heads && cd -     # 046_fill_reference_mid
uv run --no-sync python -m pytest packages/py/application/tests/test_market_operability.py -q   # 48 passed
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py                         # 219/219
```

## Trampas conocidas (no confundir con hallazgos)

- **El smoke NO cambia**: tenía `proposals=0`, así que no había eventos de gestión. La corrección de
  `H-1` se demuestra con el **día operado** (`_AUDIT_REVERSAL_DAY`), no con el smoke.
- **`other` vacía en el smoke** es correcto, no prueba `H-1`.
- **Cambio de familia declarado**: `optimizer_*`, `adaptive_strategy_paused`,
  `reservation_unmeasurable` y `reservation_already_live` pasan de `other` a su familia real. **No**
  es una regresión de `other`.
- La matriz de mutaciones tarda ~10 min: no la interpretes como colgada.
- **No hubo ventana**: `P3-2`/`P3-3` siguen abiertas.
- **Deuda PG pre-existente**: `apps/api-python/tests/test_auto_v70_auto23_evidence_validation.py`
  (`assert 17 == 26`) se **salta** en CI sin Postgres; es ajena al diff.
- **`OBS-5`** sigue declarada.

## Veredicto esperado

`APROBADO CON OBSERVACIONES` o `APROBADO` si: el censo no cuenta eventos de posición, el canal de
posición se publica y no se descarta, la partición es exhaustiva y disjunta sobre todos los dueños, el
contrato de eventos está pined contra el productor y las mutaciones `M214`–`M219` muerden/restauran.
Lo que **no** puede afirmarse: que `P3-2`/`P3-3` estén cerradas ni que exista material de mercado
diverso — **no hubo ventana**.
