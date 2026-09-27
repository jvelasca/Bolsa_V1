# Audit-pack — `v2.79` / `AUTO-MATERIAL-7`: OPERABILITY CENSUS

> **AsOf:** 2026-09-27 · **Versión:** `2.04.0-beta` · **Base (diff):** `v2.78-beta` (`2.03.0-beta`)
> · **Alembic head:** `046_fill_reference_mid` (**SIN migración**) · **Freeze:**
> `auto_simulation_worker.py` **intacto** · **Reparto:** `auto18-v1` / `auto15-v1` (`ALLOCATION = none`).
> **Cierra:** `H-1` (MEDIUM), `H-2` (LOW), `H-3` (LOW) de la [auditoría de `v2.78`](./auditoria-v2-78-auto-material-6-operability-accounting-2026-09-27.md).

## §1. Qué cambia (observable)

| Antes (`v2.78`) | Después (`v2.79`) |
|---|---|
| `journalReasons` mezcla **todas** las entradas del journal | `journalReasons` cuenta **solo** eventos `auto_entry_decision`; `positionEventReasons` publica los de **gestión de posición** |
| `protect_requested`/`atr_geometry`/… caen en `other` e **inflan** `vetoCounted` | se publican en `positionEventByCode` y **no** tocan `vetoCounted` |
| El contrato del dueño se validaba solo sobre `DecisionReasonCode` | se valida sobre **todo** el vocabulario que llega a `reasonCodes` |
| `optimizer_*`/`adaptive_strategy_paused`/`reservation_unmeasurable`/`reservation_already_live` caían en `other` | tienen **familia** declarada (ya no engordan `other` por desconocimiento) |
| La disjunción veto/no-veto no tenía test | `test_veto_buckets_and_non_veto_codes_are_disjoint` la exige |

**Claves nuevas del JSON de evidencia** (aditivas, sin migración): `positionEventReasons` (runner),
`positionEventByCode`/`positionEventCounted` (fila de operabilidad). Un consumidor antiguo que ignore
las claves nuevas no se rompe.

**Lectura de filas ya escritas**: una fila con `journalReasons` mezclado sigue separando las
atribuciones por `NON_VETO_REASON_CODES` (que ahora incluye todo `POSITION_ATTRIBUTION_REASONS`), así
que **no** se re-infla `vetoCounted`.

## §2. Matriz afirmación → código → test (por hallazgo)

### `H-1` — El censo es de decisiones de ENTRADA; la posición no lo infla

| Afirmación | Código | Test |
|---|---|---|
| Solo los eventos pedidos entran en el censo | `market_operability.collect_journal_reasons(..., events=…)` | `test_collect_journal_reasons_filters_by_event` |
| El evento de entrada es `auto_entry_decision` y los de posición son `auto_position_management`/`auto_position_decision`/`auto_position_skip` | `ENTRY_DECISION_EVENT`, `POSITION_JOURNAL_EVENTS` | `test_position_event_constants_match_the_producer_payloads` |
| Un evento de gestión **no** infla `vetoCounted` (ejemplo de reversión exacto) | `build_operability_record` | `test_the_audit_reversal_example_is_caught` |
| El motivo de gestión **no** aparece como veto y **sí** se publica | `positionEventByCode`/`positionEventCounted` | `test_position_management_events_are_not_entry_vetoes`, `test_position_management_events_are_published_not_discarded` |
| El runner ya no lee la gestión de posición como veto | `v2_76_…. _journal_reasons` | `M214` |
| El canal de posición no se descarta | `build_operability_record` | `test_position_management_events_are_published_not_discarded`, `M215` |
| Una fila legacy mezclada no re-infla el censo | `NON_VETO_REASON_CODES ⊇ POSITION_ATTRIBUTION_REASONS` | `test_legacy_merged_rows_still_read_their_position_codes_as_non_veto` |
| El render declara los eventos de posición aparte | `_position_event_summary` | `test_render_declares_position_events_apart_from_vetoes` |

### `H-2` — Contrato exhaustivo de TODOS los dueños

| Afirmación | Código | Test |
|---|---|---|
| Cada código de cualquier dueño está **exactamente** en un lado | `VETO_BUCKET_BY_REASON` ⊕ `NON_VETO_REASON_CODES` | `test_every_owner_reason_code_is_declared_exactly_once` |
| El optimizador y el Adaptive son vetos con familia (no `other`) | `_OPTIMIZER_BUCKET_OVERRIDES` + `OPTIMIZER_REASONS` + `ADAPTIVE_STRATEGY_PAUSED` | `test_optimizer_and_adaptive_codes_are_declared_as_vetoes` |
| Los dos vetos fail-closed de reserva están declarados | `RESERVATION_UNMEASURABLE`/`RESERVATION_ALREADY_LIVE` | `test_every_owner_reason_code_is_declared_exactly_once`, `M219` |
| El optimizador no vuelve a `other` | `VETO_BUCKET_BY_REASON` | `M216` |
| El Adaptive no vuelve a `other` | `VETO_BUCKET_BY_REASON` | `M217` |

### `H-3` — Disjunción veto/no-veto guardada

| Afirmación | Código | Test |
|---|---|---|
| Ningún código es veto y atribución a la vez | `VETO_BUCKET_BY_REASON ∩ NON_VETO_REASON_CODES == ∅` | `test_veto_buckets_and_non_veto_codes_are_disjoint` |
| Los vetos de reserva **no** se descatalogán como atribución | `POSITION_ATTRIBUTION_REASONS` | `test_position_attribution_literals_are_read_from_their_owner`, `M218` |

## §3. Matriz de mutaciones (`213 → 219`)

| Etiqueta | Mutación | Rojos observados |
|---|---|---|
| `M214` | el censo deja de filtrar por evento | `test_collect_journal_reasons_filters_by_event` |
| `M215` | el canal de posición no se publica | `test_position_management_events_are_published_not_discarded`, `test_render_declares_position_events_apart_from_vetoes`, `test_the_audit_reversal_example_is_caught` |
| `M216` | `OPTIMIZER_REASONS` sin familia | `test_every_owner_reason_code_is_declared_exactly_once`, `test_optimizer_and_adaptive_codes_are_declared_as_vetoes` |
| `M217` | `ADAPTIVE_STRATEGY_PAUSED` sin familia | `test_every_owner_reason_code_is_declared_exactly_once`, `test_optimizer_and_adaptive_codes_are_declared_as_vetoes` |
| `M218` | un veto de reserva entra como atribución de posición | `test_veto_buckets_and_non_veto_codes_are_disjoint`, `test_position_attribution_literals_are_read_from_their_owner`, `test_every_owner_reason_code_is_declared_exactly_once` |
| `M219` | los vetos fail-closed de reserva quedan sin declarar | `test_every_owner_reason_code_is_declared_exactly_once`, `test_optimizer_and_adaptive_codes_are_declared_as_vetoes` |

Matriz **completa**: `219/219`, restauración byte a byte, árbol intacto. Evidencia:
`evidencia-matriz-mutaciones-v2.79-219-2026-09-27.txt`.

## §4. Breaking declarado

- **No hay migración** (head `046_fill_reference_mid`).
- **No hay cambio de decisión**: el motor, el gobernador, `TOP_N` y el reparto quedan **idénticos**.
- **Cambio de vocabulario de lectura**: `optimizer_*`, `adaptive_strategy_paused`,
  `reservation_unmeasurable` y `reservation_already_live` cambian de familia (`other` → `risk`/`top_n`/
  `liquidity`/`data`). Es una mejora de la lectura; se declara en el `CHANGELOG`.
- **Claves nuevas aditivas** en el JSON: `positionEventReasons`, `positionEventByCode`,
  `positionEventCounted`.

## §5. Límites declarados

- No se cierra `P3-2`/`P3-3` (requieren material PAPER real con diversidad de mercado).
- `OBS-5` (el parser descarta conteos `<= 0` ante un mapping crudo) sigue **declarada**.
- El evento de gestión «rico» del worker V2 es `auto_position_management`; los eventos
  `auto_position_decision`/`auto_position_skip` los emite el motor AUTO clásico. El lector cubre los
  **tres**; un evento futuro con otro literal caería fuera de ambos conjuntos — por eso
  `collect_journal_reasons` con `events=None` **no descarta** nada y el contrato de eventos del lector
  está pined contra sus productores.

## §6. Verificación local (batería exacta)

```
uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml     # All checks passed!
uv run --no-sync lint-imports --config packages/py/.importlinter                    # 4 kept, 0 broken
uv run --no-sync mypy packages/py/{domain,market,infrastructure,application}/src \
    apps/api-python/src --follow-imports=silent                                    # 0 issues (505 files)
uv run --no-sync python -m pytest packages/py/application/tests -q                  # 2038 passed
uv run --no-sync python -m pytest packages/py/application/tests/test_market_operability.py -q  # 48 passed
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py             # 219/219
```

## §7. CI

Este documento **no** afirma la CI de un tag aún no publicado. `test_market_operability.py` ya está
registrado **explícito** en el job `quality` de `python-ci.yml` y en el job `python` de
`release-tag-ci.yml`; la fase **no** toca ningún workflow. La cita del CI del tag vive **post-tag**
(patrón `v2.74`–`v2.78`), declarada en la cabecera de la evidencia.
