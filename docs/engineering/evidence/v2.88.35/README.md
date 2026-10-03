# Evidencia cruda — `v2.88.35-beta` (AUTO · **DÍA-D**: cierre de los **7 hallazgos** de la auditoría de `v2.88.34`)

> **Objeto:** package **`2.11.35-beta`** · Alembic head **`048_journal_entry_dedupe_key`** (**sin migración**) · fecha **2026-10-03**.
> **Clase:** corrección **semántica/instrumental** sobre el instrumento **DÍA-D AUTO** (advisory, read-only). Cierra, **uno por uno**, los 7 hallazgos abiertos en la auditoría de `v2.88.34`: identidad de ciclo única (D34-01), atribución temporal por `entryDay` (D34-02), semántica `OOS_SUPPORTED` (D34-03), eje `evidenceQuality` (D34-04), contrato `Universe(D)` (D34-05), aislamiento de cuenta **fail-closed** (D34-06) y trazabilidad de `meta.bump` (D34-07).
> **`Δ decisión motor = 0`:** **ningún** fichero de motor (`auto_simulation_worker.py`, `auto_v2_entry.py`, `sim_durable_store.py`, `market_operability.py`, `replay_oos.py`) se toca. `AUTO_ENGINE_SIM_REAL_PRICE` sigue **OFF**. Este sello **corrige la medida**, no mueve el motor.
> **Padre:** [`evidence/v2.88.34/README.md`](../v2.88.34/README.md) (bucle de realimentación por valor).
> **Nomenclatura:** `AUTO engineering release = v2.88.35-beta` · `application package = 2.11.35-beta`.

---

## 0. Qué entrega este sello

| # | Pieza | Qué corrige |
|---|---|---|
| **1 · Lógica pura** | `packages/py/application/src/bolsa_application/dia_d_auto.py` | Nuevo `cycle_closure_summary(opened_ids, closed_ids)` (**D34-01**): fija la identidad **D-cycle = ciclo cuya APERTURA ocurre en D** y devuelve el **mismo** `step` `1/0/None` para declarado y ejecutado. `limits` declara que el `cycle_id` del replay (memoria) y el durable (ventana PAPER) **no** se unen literalmente: se unifica la **regla**. |
| **2 · Lógica pura** | `packages/py/application/src/bolsa_application/dia_d_auto_feedback.py` | `VALUE_OOS_SUPPORTED` sustituye a `CONFIRMED` emitido (**D34-03**, `CONFIRMED` queda **reservado** a evidencia PAPER); nuevo `evidence_quality_for`/`EVIDENCE_*` (**D34-04**); `build_value_scorecard` atribuye `byDay` por **`entryDay`** (**D34-02**) y añade `evidenceQuality`; `summarize_feedback` → `oosSupported` + `byEvidenceQuality`; `build_dia_d_feedback_artifact` sella `matrixBasis = "entryDay"`. |
| **3 · Lógica pura** | `packages/py/application/src/bolsa_application/universe_point_in_time.py` (**NUEVO**) | Contrato **`Universe(D)`** (**D34-05**): `@dataclass UniverseMember(instrument_id, active_at, sector_at, availability_at)` + `Protocol PointInTimeUniverse.members(day)` + helper puro `universe_ids`. **Sin implementación ni cambio del watch.** |
| **4 · CLI del barrido** | `apps/api-python/scripts/v2_89_dia_d_auto_replay.py`, `apps/api-python/scripts/v2_90_dia_d_feedback.py` | `_read_executed_facts` gana `close_window_end` (horizonte OOS) y computa `CYCLE_CLOSED` con la identidad única (**D34-01**); sellan `meta.watchSource`/`meta.survivorBiasRisk` (**D34-05**) y `meta.bump = 2.11.35-beta` (**D34-07**). |
| **5 · Rutas read-only** | `apps/api-python/src/bolsa_api/api/v1/routes/auto_dia_d.py`, `auto_dia_d_feedback.py` | **Fail-closed por cuenta** (**D34-06**): `meta.account` ausente o `!= scope` ⇒ `available=false` + `artifact_not_found` (sin `values`/`steps`/`matrix`/`errors`); listados filtran por `scope`. DTOs: `evidenceQuality`, `oosSupported`/`byEvidenceQuality`, `supportedMinCycles`/`strongMinCycles`, `matrixBasis`. |
| **6 · Contrato** | `apps/web/api/openapi.json` + `apps/web/src/api/schema.d.ts` | Regenerado (`contract:gen`); `contract:check` OK. |
| **7 · UI** | `apps/web/src/features/auto-monitor/{dia-d-auto-feedback-panel.tsx,dia-d-auto-feedback-heatmap.tsx,dia-d-auto-feedback-panel.test.tsx}` | Veredicto **«Soportado OOS»** (nunca «Confirmado») + columna/badge **Evidencia**; leyenda del heatmap declara atribución **por día de entrada**. |
| **8 · Guardián** | `apps/api-python/tests/test_dia_d_bump_guard.py` (**NUEVO**) | **D34-07**: exige que `meta.bump` de `v2_89`/`v2_90` == `version` de `package.json` (evita la divergencia `2.11.33` vs `2.11.34`). |

---

## 1. Afirmaciones falsables (por hallazgo, con su modo de ruptura)

| # | Hallazgo | Afirmación | Cómo se rompe (falsación) | Evidencia |
|---|---|---|---|---|
| **D34-01** 🔴 | Identidad de ciclo | Un **D-cycle** nace con su **apertura (buy) en D**; cierra si tiene un **sell posterior** hasta el horizonte OOS. Declarado y ejecutado emiten el **mismo** `1/0/None`. Un ciclo abierto en `D-1` y cerrado en `D` **no** es un D-cycle. Sin aperturas ⇒ `None` (UNKNOWN). | Volver a contar fills «en D» o exigir BUY+SELL dentro de `D`; emitir un conteo en un lado y `1/0/None` en el otro. | `test_dia_d_auto.py::test_cycle_closure_{one_when_a_d_cycle_closes_later,zero_when_d_cycle_still_open,ignores_cycles_not_born_in_d,none_when_no_opening_is_reconstructible}` |
| **D34-02** 🟠 | Atribución temporal | `byDay`/matriz se atribuyen por **`entryDay`** (día de decisión), no por `exitDay`. Un ciclo sin `entryDay` legible **no** se atribuye a ningún día. | Caer a `exitDay` cuando falta `entryDay` (o al revés). | `test_by_day_attributes_by_entry_day_not_exit_day`, `test_cycle_without_entry_day_is_not_attributed_to_any_day`, `test_day_matrix_cell_outcomes` |
| **D34-03** 🔴 | Semántica | El veredicto de **replay** es **`OOS_SUPPORTED`**, no `CONFIRMED`. `CONFIRMED` queda **reservado** y **no** entra en `VALUE_VERDICTS`. | Emitir `CONFIRMED` desde el replay, o dejarlo en `VALUE_VERDICTS`. | `test_oos_supported_needs_positive_edge_hit_rate_and_supported_sample` (`assert VALUE_CONFIRMED not in VALUE_VERDICTS`) |
| **D34-04** 🟠 | Muestra | `evidenceQuality` = `NOT_MEASURED` (<5) · `PRELIMINARY` (5-19) · `SUPPORTED` (20-31) · `STRONG` (>=32); un positivo con muestra `PRELIMINARY` es `MIXED` (`preliminary_sample`), no `OOS_SUPPORTED`. | Etiquetar `OOS_SUPPORTED` con `n = 5`. | `test_evidence_quality_tiers_and_strong_boundary` (bordes 4/5/19/20/31/32), `test_positive_edge_with_preliminary_sample_is_mixed_not_supported` |
| **D34-05** 🟠 | Survivorship | El watch derivado del catálogo **declara** su sesgo (`meta.survivorBiasRisk = true`, `meta.watchSource = "catalog"`); `Universe(D)` es **solo contrato** (`UniverseMember` + `PointInTimeUniverse` + `universe_ids`), sin cambio de watch. | Implementar un watch PIT sin fuente de `active_at`/`sector_at`; no declarar el sesgo. | `packages/py/application/src/bolsa_application/universe_point_in_time.py`; `limits` del artefacto; `meta.watchSource`/`survivorBiasRisk` |
| **D34-06** 🔴 | Aislamiento de cuenta | Cuenta ausente o ajena ⇒ **indistinguible de inexistente**: `available=false` + `artifact_not_found`, **sin** payload. Los listados filtran por `scope`. | Devolver el artefacto con solo una *note* (`account_scope_mismatch`) o listar días de otra cuenta. | `test_auto_dia_d_route.py::test_account_mismatch_is_fail_closed`, `test_listing_only_returns_days_of_the_current_account`; `test_auto_dia_d_feedback_route.py::test_account_mismatch_is_fail_closed`, `test_listing_only_returns_windows_of_the_current_account` |
| **D34-07** 🟡 | Trazabilidad | `meta.bump` de ambos CLI == `package.json`. | Volver a sellar `2.11.33-beta` en un artefacto de otro sello. | `test_dia_d_bump_guard.py::test_dia_d_scripts_seal_the_package_version` |
| **C4** | `None ≠ 0` | Un hueco **nunca** se rellena con `0`: `0` es una **medición** y `None` un **hueco**. | Convertir el hueco en `0.0` en el pliegue. | `test_dia_d_auto_feedback.py` (aserciones de no-coerción) |
| **C6** | Determinismo | El artefacto es determinista (mismo estado ⇒ mismo payload; sin reloj/ULID). | Introducir un timestamp/ULID. | `test_artifact_shape_and_determinism` |
| **C8** | No regresión UI | La sub-vista de feedback **no** dispara queries al montarse en modo sandbox. | Consultar `getAutoDiaDFeedbackList` incondicionalmente. | `dia-d-auto-feedback-panel.test.tsx` |

---

## 2. Verificación (re-ejecutada en el momento del sello)

| Comando | Resultado |
|---|---|
| `python -m pytest .../test_dia_d_auto.py .../test_dia_d_auto_feedback.py apps/api-python/tests/test_auto_dia_d_route.py apps/api-python/tests/test_auto_dia_d_feedback_route.py apps/api-python/tests/test_dia_d_bump_guard.py -q` | **57 passed** (núcleo `+` 2 rutas `+` guardián de bump) |
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| `uv run lint-imports --config packages/py/.importlinter` | **Contracts: 4 kept, 0 broken** (650 ficheros, 3547 dependencias) |
| `uv run mypy packages/py/domain/src … packages/py/application/src apps/api-python/src --follow-imports=silent` | **Success: no issues found in 522 source files** |
| `pnpm --filter @bolsa/web contract:gen` | `OpenAPI dumped (217 paths, 461 schemas)` + `schema.d.ts` regenerado |
| `pnpm --filter @bolsa/web contract:check` | `contract:check OK — openapi.json y schema.d.ts coinciden con el commit.` |
| `pnpm --filter @bolsa/web typecheck` | **sin errores** (`tsc -b --noEmit`) |
| `pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor` | **4 ficheros / 14 tests passed** |
| `pnpm window:test` | **`tests 25 · pass 25 · fail 0`** |

---

## 3. Límites declarados (lo que este sello **NO** cierra)

1. **`Δ motor = 0`.** El instrumento **observa y mide**; no decide. Ningún umbral (`TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B) cambia.
2. **Sin migración:** Alembic head sigue `048_journal_entry_dedupe_key`.
3. **El lado «ejecutado»** sigue `NOT_MEASURED` en días históricos sin ventana PAPER: es un hueco declarado, nunca `0`.
4. **`Universe(D)` es solo contrato** (D34-05): el watch por catálogo sigue sujeto a **survivorship bias**, ahora **declarado** (`meta.survivorBiasRisk`). No se implementa un watch point-in-time (no existe fuente de `active_at`/`sector_at`).
5. **La unión literal replay↔durable por `cycle_id` no es posible** (memoria vs. hechos durables): se unifica la **regla de identidad** y se compara el `step` `1/0/None` (D34-01).
6. **`CONFIRMED` queda reservado** a evidencia PAPER real (ejecución + muestra suficiente + datos íntegros); hoy **no** se emite.

---

## 4. Comandos (reproducir)

```bash
# Tests puros + rutas + guardián
python -m pytest packages/py/application/tests/test_dia_d_auto.py packages/py/application/tests/test_dia_d_auto_feedback.py \
  apps/api-python/tests/test_auto_dia_d_route.py apps/api-python/tests/test_auto_dia_d_feedback_route.py \
  apps/api-python/tests/test_dia_d_bump_guard.py -q

# Gates de CI (comandos EXACTOS)
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent

# Contrato + UI
pnpm --filter @bolsa/web contract:gen
pnpm --filter @bolsa/web contract:check
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor

# Runner de la ventana (sin regresión)
pnpm window:test
```

---

## 5. Sello

- **Versión:** `2.11.35-beta` (base `2.11.34-beta`); **SIN migración** — Alembic head sigue `048_journal_entry_dedupe_key`.
- **Ficheros añadidos:** `packages/py/application/src/bolsa_application/universe_point_in_time.py`, `apps/api-python/tests/test_dia_d_bump_guard.py`, `docs/engineering/evidence/v2.88.35/README.md`.
- **Ficheros modificados:** `packages/py/application/src/bolsa_application/{dia_d_auto.py,dia_d_auto_feedback.py}`, `packages/py/application/tests/{test_dia_d_auto.py,test_dia_d_auto_feedback.py}`, `apps/api-python/scripts/{v2_89_dia_d_auto_replay.py,v2_90_dia_d_feedback.py}`, `apps/api-python/src/bolsa_api/api/v1/routes/{auto_dia_d.py,auto_dia_d_feedback.py}`, `apps/api-python/tests/{test_auto_dia_d_route.py,test_auto_dia_d_feedback_route.py}`, `apps/web/api/openapi.json`, `apps/web/src/api/schema.d.ts`, `apps/web/src/features/auto-monitor/{dia-d-auto-feedback-panel.tsx,dia-d-auto-feedback-heatmap.tsx,dia-d-auto-feedback-panel.test.tsx}`, `scripts/lib/window-forward.mjs`, `package.json`, `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`.
- **`Δ motor = 0`:** ningún fichero de motor tocado.
- **Freeze del runner (re-anclado):** este sello **mueve el árbol** `apps`/`packages`; `WINDOW_CONFIG` se **re-ancló** al árbol del commit **`1f31576c`** (`git rev-parse "HEAD:apps" "HEAD:packages"`): `apps` = `9bba85710d8ad099133d668f1ff1726b1ad0d063`, `packages` = `2ac1927b1c2db713c405d04aa92ae9593035281c` (`commit` = `1f31576c`). Pin anterior (cierre `G2`/`OBS-19`, `05c429a8`): `apps` `71c3024c…` / `packages` `21b2585b…`. Editar el pin no mueve el árbol (el módulo vive en `scripts/`). `pnpm window:test` (25/25) no se ve afectado.
- **CI DE TAG (POST-TAG):** **PENDIENTE** — se cita tras el push del tag anotado `v2.88.35-beta`.

---

## 6. Gobernanza al día (`G7`)

- [`docs/CURRENT_SYSTEM.md`](../../../CURRENT_SYSTEM.md): **AsOf `V2.88.35`** (+ línea `V2.88.34` demovida a *anterior*) y fila nueva del tramo `v2.88.35` en la tabla `v2.88.20`…`v2.88.35`.
- [`docs/engineering/versioning.md`](../../versioning.md): tabla de las **5 verdades** actualizada (Product `V2.88.35-beta` · Package `2.11.35-beta`; último **tag** sigue `v2.88.34-beta` → `a98996ed`).
- [`CHANGELOG.md`](../../../../CHANGELOG.md): entrada `2.11.35-beta` con los 7 hallazgos.

**Nada de esto toca motor ni contrato:** es semántica del instrumento + documentación de sistema.
