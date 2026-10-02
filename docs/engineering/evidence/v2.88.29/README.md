# Evidencia cruda — `v2.88.29-beta` (AUTO · Golden Day 2.0 v2: hechos durables + precio real medidos en PG real)

> **Objeto:** package **`2.11.29-beta`** · Alembic head **`048_journal_entry_dedupe_key`** (**sin migración**) · fecha **2026-10-02**.
> **Clase:** sello de **certificación por medición**. Los tres tests PG de **proceso real** certificaban sólo la mecánica de trading **pre-`v2.88`**: corrían con los flags por defecto **OFF** (`AUTO_OPERATIONAL_AUDIT` ⇒ sumidero `None` ⇒ productores no-op) y con el precio plano `100.0` del `flat_price_script`. Este sello **enciende y mide** los seams post-`v2.88` (`AUDIT=1` + `REAL_PRICE=1` con barras D1), añade la **guarda hermética de `Δ motor = 0`** y cierra **dos defectos de producto** que sólo aparecieron al medir de verdad.
> **Padre:** [`evidence/v2.88.28/README.md`](../v2.88.28/README.md) (`PROTECTION` exactly-once determinista) · [`evidence/v2.88.27/README.md`](../v2.88.27/README.md) (`dedupe_key` + recuperación de `SETTLEMENT`) · [`evidence/v2.88.25/README.md`](../v2.88.25/README.md) (`ENTRY_ORDER`/`SETTLEMENT`/`price_source`).
> **Nomenclatura:** `AUTO engineering release = v2.88.29-beta` · `application package = 2.11.29-beta` (el tag de ingeniería **no** es el semver del paquete).

---

## 0. Qué produce este sello

| # | Hueco (hasta `v2.88.28`) | Hecho que se produce / se mide ahora |
|---|---|---|
| **H1 🔴** | El Golden Day PG corría sin `AUTO_OPERATIONAL_AUDIT` ⇒ sumidero `None` ⇒ **ningún** hecho durable se sellaba; el monitor declaraba `*_not_durable` y el exactly-once **no se ejercía**. | Golden Day con `AUDIT=1`: `auto_entry_order`, `auto_cycle_settlement` y `auto_protection_event` con `dedupe_key` **no nulo**, reconstrucción desde el monitor **sin** `*_not_durable`, cadena hasta `CYCLE_CLOSED`. |
| **H2 🔴** | El Golden Day PG usaba el precio plano `100.0`; el camino de **precio real** jamás se probaba en proceso real. | Variante con `REAL_PRICE=1` + barras D1: cada fill declara `price_source='MARKET_CLOSE'`, **ningún** precio es `100.0`, `reference_mid` medido. |
| **H3 🔴 · producto** | El *short-circuit* por barra (`reuse_bar_datum`) **no** refrescaba la fuente de precio (se recompone por sesión/tick): un turno dentro de la misma barra se quedaba **sin `execution`** y no podía marcar ni cerrar (*fail-closed* silencioso en el camino de precio real). | `_v2_refresh_price()` refactorizado: el precio se relee en **cada turno**; sin fuente real es no-op (`Δ = 0` para el `price_script`). |
| **H4 🔴 · producto** | Un `order_id` de venue largo rebasaba `decision_journal_entries.dedupe_key VARCHAR(160)` ⇒ `StringDataRightTruncation` al sellar el hecho. | `_bounded_dedupe_key()`: literales históricos **byte-idénticos** (`Δ = 0`); sólo al desbordar, `prefijo + ':' + sha256[:16]` determinista. |
| **H5 🟠** | El crash day no medía los hechos durables ni declaraba la matriz de inyección §14.B. | Foto de salud **antes/después** del crash (0 `NULL`, 0 duplicados, orden de entrada no re-emitida) + matriz §14.B **declarada** y mordiente. |
| **H6 🟠** | El PG concurrente no medía el exactly-once de los hechos ni unificaba el contrato terminal de reserva. | N sesiones ⇒ **exactamente 1** `auto_entry_order`; oráculo **OBS-18 único** (`tests/obs18_contract.py`) compartido con el gemelo hermético. |
| **H7 🟠** | Ningún test probaba que encender la auditoría **no** mueve el motor. | Guarda hermética `Δ motor = 0`: el informe del día es **idéntico** OFF vs ON; ON sólo **añade** hechos. |

---

## 1. Afirmaciones falsables (con su modo de ruptura)

| # | Afirmación | Cómo se rompe (falsación) | Comando / evidencia |
|---|---|---|---|
| **C1** | **PG real**: el Golden Day con `AUDIT=1` sella ≥1 `auto_entry_order` por orden BUY y ≥1 `auto_protection_event` de nacimiento, **todos** con `dedupe_key` no nulo. | Desactivar el flag / no sellar identidad ⇒ `nullKey > 0` o conteo 0. | `AUTO_GOLDEN_DAY_V2_PG_REQUIRED=1 … test_golden_day_v2_process_pg.py` |
| **C2** | **PG real**: el monitor reconstruye la cadena desde lo durable **sin** `protection_not_durable`/`settlement_not_durable` y llega a `CYCLE_CLOSED`. | No emitir el hecho ⇒ el paso queda `unknown`/`not_durable`. | `test_golden_day_v2_process_pg.py::test_golden_day_v2_real_process_opens_and_closes_the_book_pg` |
| **C3** | **PG real**: con `REAL_PRICE=1` cada fill declara `price_source='MARKET_CLOSE'` y **ningún** precio es `100.0`. | Caer al `flat_price_script`/`SYNTHETIC` ⇒ la aserción de fuente/precio falla. | `test_golden_day_v2_process_pg.py::test_golden_day_v2_real_price_process_opens_and_closes_the_book_pg` |
| **C4** | **producto**: el precio real se refresca en cada turno (también con `reuse_bar_datum`); sin fuente real es no-op. | Quitar `_v2_refresh_price()` ⇒ el turno intra-barra queda sin `execution` (el día real no marca/cierra). | `test_auto_v2_bar_short_circuit.py` + el día real (`C3`) |
| **C5** | **producto**: la clave de deduplicación acotada es determinista y `≤ 160`; los literales cortos son **idénticos** a los de siempre. | No acotar ⇒ `StringDataRightTruncation`; acotar sin determinismo ⇒ dos órdenes colapsan. | `packages/py/application/tests/test_auto_operational_audit.py` (**+2**) |
| **C6** | **PG real**: el crash/restart **no** duplica hechos durables ni re-emite la orden de entrada ya sellada (`antes == después`), y el ciclo readoptado sella su liquidación. | `ON CONFLICT` roto / re-emisión ⇒ duplicados o `antes != después`. | `AUTO_CRASH_RECOVERY_PG_REQUIRED=1 … test_crash_recovery_day_process_pg.py` |
| **C7** | La matriz §14.B está completa: cada punto inyectable cita un test que **existe**; cada punto no inyectable declara su motivo. | Editar la tabla a la ligera / citar un test renombrado ⇒ el test muerde. | `test_crash_recovery_day_process_pg.py::test_crash_injection_matrix_is_declared_and_covered` |
| **C8** | **PG real**: N sesiones contendientes sobre la MISMA señal ⇒ **exactamente 1** `auto_entry_order`, 0 `NULL`, 0 duplicados. | Clave no determinista ⇒ >1 fila o duplicados. | `AUTO_CONCURRENT_PG_REQUIRED=1 … test_concurrent_auto_pg.py` |
| **C9** | **OBS-18**: el contrato terminal de una reserva con fill parcial es único (liberada ENTERA, `remaining=0`, `tail_dead`, `status != OPEN`, `reserved_cash=0`) y lo comparten el gemelo hermético (`real_turn`) y el PG. | Divergir semántica ⇒ uno de los dos gemelos falla. | `tests/obs18_contract.py`; `test_auto_v46_concurrent.py`; `test_concurrent_auto_pg.py` |
| **C10** | **`Δ motor = 0`**: el mismo día con flags OFF y ON (sumidero inyectado) produce el **mismo** informe; ON sólo **añade** hechos con identidad. | El overlay altera el artefacto ⇒ `_report(on) != _report(off)`. | `test_auto_v2_bar_short_circuit.py::test_the_operational_audit_overlay_is_delta_zero_on_the_motor_report` |
| **C11** | Las mutaciones **muerden**: `M294` (PROTECCIÓN sin `revision_id` ⇒ `dedupe_key=None`) y `M295` (`uuid4` en vez de contenido ⇒ exactly-once roto). | Aplicar la mutación ⇒ el test citado **rojo**; restaurar ⇒ verde byte a byte. | `v2_44_mutation_audit.py M294 M295` |
| **C12** | El contrato no drifta: **sin migración** (head `048`) y `openapi.json`/`schema.d.ts`/shared sin cambios. | Tocar el DTO / la cadena ⇒ `contract:check`/`alembic heads` rojo. | `uv run alembic heads` → `048_journal_entry_dedupe_key (head)` |

---

## 2. Verificación (re-ejecutada en el momento del sello)

| Comando | Resultado |
|---|---|
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | `All checks passed!` |
| `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent` | `Success: no issues found in 517 source files` (mismos ficheros que `v2.88.28`; `obs18_contract.py` es de `tests`, no cuenta) |
| `uv run lint-imports --config packages/py/.importlinter` | `Contracts: 4 kept, 0 broken.` |
| `uv run python -m pytest packages/py/analytics/tests packages/py/application/tests -q` | **3578 passed** (`v2.88.28` = 3576; **+2** = los tests de la clave acotada) |
| `uv run python -m pytest packages/py/analytics/tests/test_position_revision.py -q` | **19 passed** |
| `uv run python -m pytest packages/py/application/tests/test_auto_operational_audit.py -q` | **25 passed** (`v2.88.28` = 23; **+2** de la clave acotada) |
| `uv run python -m pytest apps/api-python/tests/test_auto_v46_concurrent.py apps/api-python/tests/test_auto_v88_28_protection_exactly_once.py packages/py/analytics/tests/test_position_revision.py apps/api-python/tests/test_auto_v2_worker_integration.py -q` | **75 passed** |
| `uv run python -m pytest apps/api-python/tests/test_auto_v2_bar_short_circuit.py apps/api-python/tests/test_auto_m2_operational_audit_seam.py packages/py/analytics/tests/test_position_revision.py -q` | **46 passed** (incluye el nuevo `Δ motor = 0`) |
| `AUTO_GOLDEN_DAY_V2_PG_REQUIRED=1 AUTO_CRASH_RECOVERY_PG_REQUIRED=1 AUTO_CONCURRENT_PG_REQUIRED=1 uv run python -m pytest apps/api-python/tests/test_golden_day_v2_process_pg.py apps/api-python/tests/test_crash_recovery_day_process_pg.py apps/api-python/tests/test_concurrent_auto_pg.py -q` | **7 passed** (PG real, gate *fail-if-skipped*: un `skip` sería fallo duro) |
| `uv run python apps/api-python/scripts/v2_44_mutation_audit.py M294 M295` | `M294` **rojo** en `test_protection_is_persisted_with_account_and_engine`; `M295` **rojo** en `test_seal_protection_transition_without_change_shares_content_id`; ambos `restaurado byte a byte: si`; `intacto: la sonda no alteró el árbol` |
| `uv run alembic heads` (en `packages/py/infrastructure`) | `048_journal_entry_dedupe_key (head)` (**sin migración**) |
| **CI de tag** — `Release tag CI` run [`37034237594`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37034237594) (`ref=refs/tags/v2.88.29-beta`, HEAD `2b67a2fa`, `2026-10-02T16:29:04Z → 16:37:58Z`) | **`SUCCESS`**: **11 jobs `success`** (`security`, `decision-spine`, `python`, `replay-repro`, `dr-verify`, `a7-gate`, `frontend`, `shared`, `lifecycle-pg`, `playwright (mock E2E)`, `certify`) + `playwright (integrated E2E, opt-in)` `skipped` por diseño. Job `python`: `All checks passed!` · `Contracts: 4 kept, 0 broken.` · `mypy no issues found in 517 source files` · **`4324 passed, 45 skipped, 7 warnings in 132.65s`** (`v2.88.28` = `4321 passed, 45 skipped` ⇒ **+3 passed** = `test_auto_operational_audit.py` +2 y el `Δ motor = 0` hermético +1; **mismos `45` skips**). `lifecycle-pg` **VERDE** con gates *fail-if-skipped*: **Golden Day 2.0 `2 passed`** (`17.48s`) · **Crash/Recovery Day `2 passed`** (`7.92s`) · **Concurrent AUTO `3 passed`** (`1.96s`). `replay-repro` → `VEREDICTO REPRODUCIDO (mismo CONTENIDO; el sello está en CRLF y este fichero en LF)` con `sha256 1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7` / `3340728 B` (**idéntico a `v2.88.25`/`26`/`27`/`28`**), **2ª corrida IDÉNTICA** ⇒ **`Δ motor = 0` confirmado en el runner.** |

> Nota de honestidad: la corrida local completa de `apps/api-python/tests` contra PG real tiene fallos de **caos/concurrencia** conocidos (documentados en `v2.88.27`/`v2.88.28`) que desaparecen al re-ejecutarlos en aislamiento; aquí se citan las suites **aisladas** que este sello toca. El job `python`/`lifecycle-pg` del CI es quien certifica el árbol completo.

---

## 3. Límites declarados (lo que este sello **NO** hace)

1. **`Δ motor = 0` con flags OFF.** El único cambio que toca el *fill* es `AUTO_ENGINE_SIM_REAL_PRICE=1` (deja de fabricar `100.0`); por eso se **re-mide** con barras sembradas, no se asume.
2. **Deuda P3 del hash** (`sha256[:16]`) sin tocar.
3. **Recovery de AUSENCIA** de `PROTECTION` y de `ENTRY_ORDER` sigue fuera (sólo exactly-once).
4. **Crash *mid-tick* del broker SIM** no es inyectable por construcción: se **declara** en la matriz §14.B.
5. **Sin migración / sin backfill** (reutiliza la columna y el índice de la `048`).
6. **La ventana PAPER ≥4 días** es el salto operativo **siguiente**, sobre este árbol ya congelado; no se cierra aquí.
7. **`PROJECT_STATE.md`/engineering-index no se tocan** (mismo criterio que `v2.88.25`–`v2.88.28`).

---

## 4. Comandos (reproducir)

```bash
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
    packages/py/application/src apps/api-python/src --follow-imports=silent
uv run python -m pytest packages/py/application/tests/test_auto_operational_audit.py -q
uv run python -m pytest apps/api-python/tests/test_auto_v46_concurrent.py -q
uv run python -m pytest apps/api-python/tests/test_auto_v2_bar_short_circuit.py -q
AUTO_GOLDEN_DAY_V2_PG_REQUIRED=1 AUTO_CRASH_RECOVERY_PG_REQUIRED=1 AUTO_CONCURRENT_PG_REQUIRED=1 \
  uv run python -m pytest apps/api-python/tests/test_golden_day_v2_process_pg.py \
    apps/api-python/tests/test_crash_recovery_day_process_pg.py \
    apps/api-python/tests/test_concurrent_auto_pg.py -q         # exige PG real
uv run python apps/api-python/scripts/v2_44_mutation_audit.py M294 M295
uv run alembic heads   # en packages/py/infrastructure
```

---

## 5. Sello

- **Versión:** `2.11.29-beta` (base `2.11.28-beta`); **SIN migración** — Alembic head sigue `048_journal_entry_dedupe_key`.
- **Ficheros de producto:** `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` (`_v2_refresh_price()` en cada turno), `packages/py/application/src/bolsa_application/auto_operational_audit.py` (`_bounded_dedupe_key()`) + tests + docs.
- **Ficheros de test:** `apps/api-python/tests/obs18_contract.py` (oráculo OBS-18 único), `test_golden_day_v2_process_pg.py`, `test_crash_recovery_day_process_pg.py`, `test_concurrent_auto_pg.py`, `test_auto_v46_concurrent.py`, `test_auto_v2_bar_short_circuit.py`, `test_auto_m2_operational_audit_seam.py`, `packages/py/application/tests/test_auto_operational_audit.py`, `apps/api-python/scripts/v2_44_mutation_audit.py` (M294/M295).
- **CI:** los tres ficheros PG ya están cableados en `lifecycle-pg` (`release-tag-ci.yml`) con sus gates `AUTO_GOLDEN_DAY_V2_PG_REQUIRED`/`AUTO_CRASH_RECOVERY_PG_REQUIRED`/`AUTO_CONCURRENT_PG_REQUIRED`; los herméticos entran por el pase de directorio de `python-ci.yml` (`obs18_contract.py` es módulo de apoyo, no `test_*` ⇒ no se ignora ni se recolecta).
- **CITA REAL DEL CI (POST-TAG, 2026-10-02):** `Release tag CI` run [`37034237594`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37034237594) (`ref=refs/tags/v2.88.29-beta`, HEAD `2b67a2fa`, `2026-10-02T16:29:04Z → 16:37:58Z`) → **`SUCCESS`**: 11 jobs `success` + `playwright (integrated E2E, opt-in)` `skipped` por diseño, `certify` `success`. Job `python` `4324 passed, 45 skipped, 7 warnings in 132.65s`; `lifecycle-pg` **VERDE** (Golden Day 2.0 `2 passed`, Crash/Recovery Day `2 passed`, Concurrent AUTO `3 passed`; gates *fail-if-skipped* cumplidos); `replay-repro` **REPRODUCIDO** (`1E3ADAC2…` / `3340728 B`, 2ª corrida IDÉNTICA) ⇒ `Δ motor = 0`.
