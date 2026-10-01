# Evidencia cruda — `v2.88.21-beta` (AUTO Operational Monitor · `M2`)

> **Objeto:** tag anotado **`v2.88.21-beta`** · package **`2.11.21-beta`** · Alembic head **`046_fill_reference_mid`** (**SIN migración**) · fecha **2026-10-01**.
> **Clase:** sello de **producto** (`Δ src ≠ 0`) que toca el motor de forma **aditiva** y **tras flag**: `AUTO_OPERATIONAL_AUDIT` **default OFF** ⇒ **`Δ = 0` por defecto** (mismo patrón que `AUTO_ENGINE_SIM_REAL_PRICE`). Con el flag ON, el motor **escribe** traza de auditoría en el spine `decision_journal_entries`, pero **ninguna decisión cambia**.
> **Origen:** `M1` (`v2.88.20-beta`) dejó declarados `NO MEDIDO` los pasos `SIGNAL`/`TOP_N`/`RISK`, el ownership de reservas y la concurrencia porque su productor (el journal de decisión AUTO y las decisiones de reservas) vivía **en memoria**. `M2` los hace **durables** sin migración, reutilizando el spine.
> **Padre:** [`evidence/v2.88.20/README.md`](../v2.88.20/README.md) (el sello hermano `M1`).
> **CI del tag:** **NO CITADO** — sello **local** por decisión del propietario (sin push). Ver §6.

---

## 0. Qué hace `M2`

**Módulo puro nuevo** `packages/py/application/src/bolsa_application/auto_operational_audit.py` (builders append-only + evaluador de flag):

| `event_type` | Cuándo | Hecho durable |
|---|---|---|
| `auto_entry_decision` | flush del `_v2_journal` del turno | la decisión de entrada con `cycleId`/`rank`/`opportunityScore` ⇒ `SIGNAL`/`TOP_N`/`RISK` dejan de ser `unknown` |
| `auto_reservation_claim` | `save_claim` en `_v2_persist_tick_reservations` | claim **ganado**/**perdido** (`claimed`, `caller`) ⇒ ownership + `duplicateClaims` |
| `auto_reservation_reconciliation` | `_v2_reconcile_reservations` | decisión `KEEP`/`RELEASE`, `reason`, `mine`, `aged`, `graceWindowSeconds` (cada hueco con su medición) |

**Sink** `build_operational_audit_sink(session)` — idéntico patrón al de régimen/adaptativo: **commit propio** y **`rollback` en fallo**, best-effort: **nunca** tumba el turno. Se inyecta en `_WorkerRunner` **sólo** si `operational_audit_enabled()`.

**Puntos de enganche (aditivos):** `_v2_journal_entry_decisions` (flush del journal del turno), `_v2_journal_reservation_claims` (`save_claim`), `_v2_journal_reconciliation_decisions` (`_v2_reconcile_reservations`).

**Costura de honestidad medida:** la columna `decision_journal_entries.session_id` tiene **FK a `decision_sessions`**. Estampar ahí la sesión del motor habría exigido **inventar una fila** (o migrar). Por eso la identidad de sesión viaja en **`payload.caller`** con su `callerMeasurement`, y el monitor la resuelve de ahí (aceptando también la columna si un productor legítimo la trae). Verificado contra PG real: la primera versión reventaba con `ForeignKeyViolation` y se corrigió **antes** del sello.

---

## 1. Afirmaciones falsables (con su modo de ruptura)

| # | Afirmación | Cómo se rompe (falsación) | Comando / evidencia |
|---|---|---|---|
| **B1** | Con el flag **OFF**, `operational_audit_enabled()` es `False` (ausente/vacío/`0`/`false`). | Tratar la ausencia como ON ⇒ el test muere. | `uv run python -m pytest packages/py/application/tests/test_auto_operational_audit.py -q` → **7 passed** |
| **B2** | El `decision_id` de las entradas auditadas se **deriva** del `cycle_id` (`cyc-` ↔ `dec-`), sin recalcular digest; sin ciclo se declara `cycleIdDerived = false`. | Cambiar la derivación ⇒ el assert de identidad falla. | idem B1 |
| **B3** | Ownership durable = **claim ganado**; un claim **perdido** **no** es propiedad (`ownerSession = null` + `UNKNOWN`). | Inventar el dueño o tomar el perdedor ⇒ el test falla. | `uv run python -m pytest packages/py/application/tests/test_auto_operational_monitor.py -q` → **16 passed** |
| **B4** | `lastConflict` = la carrera **perdida** más reciente; con claims sin carrera es `null` + `COMPLETE`; sin claims, `UNKNOWN`. | Marcar conflicto siempre / nunca ⇒ el test falla. | idem B3 |
| **B5** | La cadena **real** en PG se proyecta de verdad: `SIGNAL`/`TOP_N` `reached` con su `rank`, `CYCLE_CLOSED` `reached` con PnL, `ownerSession = sess-owner`, `graceWindowKeeps = 1`. | Persistir la decisión sin `cycleId` / perder el claim ⇒ el test PG falla. | `uv run python -m pytest apps/api-python/tests/test_auto_operational_monitor_pg.py -q` → **2 passed** (PG real local) |
| **B6** | Ausencia ⇒ `unknown` **declarado**, nunca `0`: sin journal ni claims, `SIGNAL = unknown` y `notes` incluye `decision_journal_not_durable` + `owner_session_not_durable`. | Materializar `0` / omitir la nota ⇒ el test PG falla. | idem B5 |
| **B7** | Un sink que revienta **no** tumba el turno, pero **se declara** (`ERROR` con la etiqueta del hecho). | Tragarse la excepción en silencio ⇒ el test de `caplog` falla. | `uv run python -m pytest apps/api-python/tests/test_auto_m2_operational_audit_seam.py -q` → **7 passed** |
| **B8** | El sink real **commitea** (`add`→`flush`→`commit`) y, si falla el commit, **hace `rollback`** (deja la sesión del tick limpia). | Quitar el commit (no hay durabilidad) o el rollback (envenena el turno) ⇒ el test falla. | idem B7 |
| **B9** | La sesión **no** se escribe en la columna con FK: viaja en `payload.caller` (`session_id is None`). | Volver a estampar la columna ⇒ `ForeignKeyViolation` en PG (medido) y el test unitario falla. | idem B1 + B5 |

**Mutaciones que muerden (diseño):** `owner` inventado (B3), claim siempre «ganado» (B7/`claimed`), `KEEP`↔`RELEASE` (B1), `0`/`100.0` cuando no hay medida (B6), commit sin durabilidad o sin `rollback` (B8), estampar `session_id` (B9).

---

## 2. Dónde `M2` convierte cada `NO MEDIDO` de `M1` en dato

| Panel | `M1` | `M2` (con flag ON y productor durable) |
|---|---|---|
| `SIGNAL`/`TOP_N`/`RISK` | `unknown` | `reached` desde `auto_entry_decision` (`cycleId` + `rank`) |
| ownership de reservas | `NO MEDIDO` | `ownerSession` del claim ganado (`payload.caller`) |
| `duplicateClaims`/`reservationRaces` | `NO MEDIDO` | conteo de claims perdidos |
| `reconciliations`/`graceWindowKeeps`/`forcedReleases` | `NO MEDIDO` | reconciliaciones del spine + `release_reason` |

---

## 3. Verificación (re-ejecutada en el momento del sello)

| Comando | Resultado |
|---|---|
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | `All checks passed!` |
| `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent` | `Success: no issues found in 515 source files` |
| `uv run python -m pytest packages/py/application/tests/test_auto_operational_audit.py -q` | **7 passed** |
| `uv run python -m pytest packages/py/application/tests/test_auto_operational_monitor.py -q` | **16 passed** |
| `uv run python -m pytest apps/api-python/tests/test_auto_m2_operational_audit_seam.py apps/api-python/tests/test_auto_operational_monitor_pg.py -q` | **9 passed** (PG real: 2 de ellos) |
| `uv run python -m pytest packages/py/application/tests -q` (batería de aplicación, pase de directorio del CI) | **2067 passed** |
| `pnpm --filter @bolsa/web contract:check` | `contract:check OK` |

---

## 4. Límites declarados (lo que `M2` **NO** hace)

1. **No se enciende por defecto.** `AUTO_OPERATIONAL_AUDIT` es OFF: el motor escribe **byte-idéntico** salvo que el propietario lo active en la ventana PAPER. Encenderlo queda declarado como **operación**, no como parte del sello.
2. **`activeSessions` es un SUELO, no un censo.** Cuenta sesiones que **ya escribieron** en la ventana; no hay productor de latido durable. El hueco se declara (`MEASUREMENT_PARTIAL`/`UNKNOWN`).
3. **No cierra `P3-2`/`P3-3` ni las compuertas `G1`–`G7`.** `M2` es el instrumento que `G4`/`W5` podrán usar.
4. **No certifica precio real / protección OHLC** (`W5`) ni habilita `NEXT_BAR_OPEN`.
5. **Sin migración**: Alembic head sigue en `046_fill_reference_mid`; todo reutiliza `decision_journal_entries`.
6. **La certificación PG de `M1`+`M2` viaja en este sello** (`test_auto_operational_monitor_pg.py` depende de los builders de `M2`), por eso `M1` lo declaró diferido.
7. **`replay-repro` no medido**: con el flag OFF el artefacto OOS no puede moverse (el camino del motor no añade escrituras); se declara como **razón**, no como medición. Se medirá al empujar el tag.

---

## 5. Comandos (reproducir)

```bash
uv run python -m pytest packages/py/application/tests/test_auto_operational_audit.py -q
uv run python -m pytest packages/py/application/tests/test_auto_operational_monitor.py -q
uv run python -m pytest apps/api-python/tests/test_auto_m2_operational_audit_seam.py -q
uv run python -m pytest apps/api-python/tests/test_auto_operational_monitor_pg.py -q   # exige PG real
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
    packages/py/application/src apps/api-python/src --follow-imports=silent
```

---

## 6. Sello y CI

- **Sello local** (por decisión del propietario, **sin push**): este commit + tag anotado `v2.88.21-beta`, sobre `M1` (`v2.88.20-beta`, commit `4a3e78f6`).
- **Alta en CI**: los ficheros nuevos entran en **ambos** workflows ([`python-ci.yml`](../../../.github/workflows/python-ci.yml), [`release-tag-ci.yml`](../../../.github/workflows/release-tag-ci.yml)); el puro del monitor y el de auditoría por el pase de directorio con ancla explícita, la costura del worker por el pase de `apps/api-python/tests`, y el PG en `--ignore` del job offline + registrado en `auto-v2-durable-pg` / `lifecycle-pg` con gate `AUTO_OPERATIONAL_MONITOR_PG_REQUIRED=1` (fail-if-skipped).
- **CI del tag NO CITADO**: al no empujar, no hay run de `Release tag CI` que citar. **Hueco declarado**, no certificación heredada; se citará (POST-TAG, patrón `OBS-3`/`OBS-4`) cuando el propietario decida empujar.
