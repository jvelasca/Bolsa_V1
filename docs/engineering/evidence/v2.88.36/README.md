# Evidencia cruda — `v2.88.36-beta` (AUTO · **DÍA-D**: consolidación del instrumento — **PIT demostrable + robustez**)

> **Objeto:** package **`2.11.36-beta`** · Alembic head **`048_journal_entry_dedupe_key`** (**sin migración**) · fecha **2026-10-03**.
> **Clase:** corrección **instrumental** (advisory, read-only) sobre **DÍA-D AUTO**. Cierra, **uno por uno**, los 4 hallazgos abiertos en la auditoría de `v2.88.35`: intervalo de finalización del universo point-in-time (D35-01), identidad de ciclo None-safe (D35-02), validación numérica finita (D35-03) y lenguaje de la UI (D35-04).
> **`Δ decisión motor = 0`:** **ningún** fichero de motor (`auto_simulation_worker.py`, `auto_v2_entry.py`, `sim_durable_store.py`, `market_operability.py`, `replay_oos.py`) se toca. `AUTO_ENGINE_SIM_REAL_PRICE` sigue **OFF** en el instrumento.
> **Padre:** [`evidence/v2.88.35/README.md`](../v2.88.35/README.md) (cierre de los 7 hallazgos D34; contrato `Universe(D)` inicial).
> **Nomenclatura:** `AUTO engineering release = v2.88.36-beta` · `application package = 2.11.36-beta`.

---

## 0. Qué entrega este sello

| # | Pieza | Qué corrige |
|---|---|---|
| **1 · Lógica pura** | `packages/py/application/src/bolsa_application/universe_point_in_time.py` | **D35-01**: `UniverseMember` pasa de fechas de inicio único a **intervalos** (`active_from`/`active_until`, `availability_from`/`availability_until`) + predicado puro **`eligible_at(member, day)`**; `universe_ids` filtra por elegibilidad, deduplica y ordena. Sigue siendo **solo contrato** (sin fuente real ni cambio del watch). |
| **2 · Lógica pura** | `packages/py/application/src/bolsa_application/dia_d_auto.py` | **D35-03**: `finite_number` (nuevo, exportado) valida con `math.isfinite`; `_json_safe` deja de emitir `Infinity`. **D35-02**: `_cycle_id` descarta `None`/`""`/espacios y `cycle_closure_summary` no los normaliza a `"None"`. |
| **3 · Lógica pura** | `packages/py/application/src/bolsa_application/dia_d_auto_feedback.py` | Reutiliza `finite_number` (se elimina su `_opt_number` local) y precisa el `limits` de survivorship (el contrato PIT ya modela fin/delistado). |
| **4 · UI** | `apps/web/src/features/auto-monitor/{dia-d-auto-feedback-panel.tsx,dia-d-auto-feedback-panel.test.tsx}` | **D35-04**: el encabezado deja de decir «Confirma o refuta» ⇒ «Evalúa la evidencia OOS … y clasifica las incidencias»; aserción de regresión. |
| **5 · Sello** | `package.json`, `apps/api-python/scripts/{v2_89_dia_d_auto_replay.py,v2_90_dia_d_feedback.py}` | Bump `2.11.35-beta` → `2.11.36-beta`; `meta.bump` de ambos CLI alineado (guardián `test_dia_d_bump_guard.py`). |

---

## 1. Afirmaciones falsables (por hallazgo, con su modo de ruptura)

| # | Hallazgo | Afirmación | Cómo se rompe (falsación) | Evidencia |
|---|---|---|---|---|
| **D35-01** 🟠 | Universo PIT | Ser elegible en `D` es **demostrable**: `eligible_at` exige `D` dentro de `[active_from, active_until]` **y** `[availability_from, availability_until]` (fin `None` = abierto). Un instrumento **delistado** (`D > active_until`) deja de ser elegible. Inicio desconocido ⇒ **inelegible** (fail-closed). | Volver a fechas de inicio único; tratar un inicio ausente como elegible; no filtrar por elegibilidad en `universe_ids`. | `test_universe_point_in_time.py::test_delisted_member_is_not_eligible_after_active_until`, `test_unknown_start_cannot_be_demonstrated`, `test_universe_ids_filters_ineligible_deduplicates_and_sorts` |
| **D35-02** 🟡 | Robustez | Un id `None`/`""`/solo-espacios **nunca** es un id de ciclo: se descarta; sin aperturas reales el paso es `None`/UNKNOWN (no el literal `"None"`). | Normalizar con `str(value)` antes de filtrar. | `test_dia_d_auto.py::test_cycle_closure_treats_none_and_blank_ids_as_no_opening`, `test_cycle_closure_discards_blank_ids_but_keeps_real_ones` |
| **D35-03** 🟡 | Datos finitos | `finite_number` rechaza `NaN`, `+inf` y `-inf`; `_json_safe` no emite `Infinity`; un `±inf` no cuenta como ciclo ni contamina `expectancyR`/`realizedRTotal`/matriz. | Aceptar `±inf` como medible o serializarlo a JSON. | `test_dia_d_auto.py::test_finite_number_rejects_nan_and_infinities`, `test_artifact_declares_infinite_values_as_gaps_and_stays_deterministic`; `test_dia_d_auto_feedback.py::test_infinite_realized_r_is_not_a_cycle` |
| **D35-04** 🟡 | UX/semántica | El encabezado **evalúa evidencia OOS**, no «confirma/refuta» (coherente con `OOS_SUPPORTED`). | Volver a «Confirma o refuta». | `dia-d-auto-feedback-panel.test.tsx` (contiene «Evalúa», no «Confirma») |
| **C4** | `None ≠ 0` | Un hueco **nunca** se rellena con `0`. | Convertir el hueco en `0.0` en el pliegue. | `test_dia_d_auto_feedback.py` (aserciones de no-coerción) |
| **C6** | Determinismo | El artefacto es determinista (mismo estado ⇒ mismo payload; sin reloj/ULID). | Introducir un timestamp/ULID. | `test_dia_d_auto.py::test_artifact_declares_infinite_values_as_gaps_and_stays_deterministic` |
| **C8** | No regresión UI | La sub-vista de feedback **no** dispara queries al montarse en modo sandbox. | Consultar `getAutoDiaDFeedbackList` incondicionalmente. | `dia-d-auto-feedback-panel.test.tsx` |

---

## 2. Verificación (re-ejecutada en el momento del sello)

| Comando | Resultado |
|---|---|
| `python -m pytest .../test_dia_d_auto.py .../test_dia_d_auto_feedback.py .../test_universe_point_in_time.py apps/api-python/tests/test_auto_dia_d_route.py apps/api-python/tests/test_auto_dia_d_feedback_route.py apps/api-python/tests/test_dia_d_bump_guard.py -q` | **69 passed** |
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| `uv run lint-imports --config packages/py/.importlinter` | **Contracts: 4 kept, 0 broken** (650 ficheros, 3547 dependencias) |
| `uv run mypy packages/py/domain/src … packages/py/application/src apps/api-python/src --follow-imports=silent` | **Success: no issues found in 522 source files** |
| `pnpm --filter @bolsa/web contract:check` | `contract:check OK — openapi.json y schema.d.ts coinciden con el commit.` |
| `pnpm --filter @bolsa/web typecheck` | **sin errores** (`tsc -b --noEmit`) |
| `pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor` | **4 ficheros / 14 tests passed** |
| `pnpm window:test` | **`tests 25 · pass 25 · fail 0`** |

---

## 3. Límites declarados (lo que este sello **NO** cierra)

1. **`Δ motor = 0`.** El instrumento **observa y mide**; no decide. Ningún umbral (`TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B) cambia.
2. **Sin migración:** Alembic head sigue `048_journal_entry_dedupe_key`.
3. **`Universe(D)` sigue siendo SOLO CONTRATO (D35-01):** el contrato ya **puede** representar delistado y huecos de sector, pero **no existe fuente real** de fechas de baja ni de historial de sector (la tabla `instruments` solo tiene `is_active` actual + `created_at`/`updated_at`). El watch por catálogo sigue sujeto a **survivorship bias**, ahora **declarado** (`meta.survivorBiasRisk`).
4. **El lado «ejecutado»** sigue `NOT_MEASURED` en días históricos sin ventana PAPER: es un hueco declarado, nunca `0`.
5. **`CONFIRMED` queda reservado** a evidencia PAPER real; hoy **no** se emite.

---

## 4. Comandos (reproducir)

```bash
# Tests puros + rutas + guardián
python -m pytest packages/py/application/tests/test_dia_d_auto.py packages/py/application/tests/test_dia_d_auto_feedback.py \
  packages/py/application/tests/test_universe_point_in_time.py \
  apps/api-python/tests/test_auto_dia_d_route.py apps/api-python/tests/test_auto_dia_d_feedback_route.py \
  apps/api-python/tests/test_dia_d_bump_guard.py -q

# Gates de CI (comandos EXACTOS)
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent

# Contrato + UI
pnpm --filter @bolsa/web contract:check
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor

# Runner de la ventana (sin regresión)
pnpm window:test
```

---

## 5. Sello

- **Versión:** `2.11.36-beta` (base `2.11.35-beta`); **SIN migración** — Alembic head sigue `048_journal_entry_dedupe_key`.
- **Ficheros añadidos:** `packages/py/application/tests/test_universe_point_in_time.py`, `docs/engineering/evidence/v2.88.36/README.md`.
- **Ficheros modificados:** `packages/py/application/src/bolsa_application/{universe_point_in_time.py,dia_d_auto.py,dia_d_auto_feedback.py}`, `packages/py/application/tests/{test_dia_d_auto.py,test_dia_d_auto_feedback.py}`, `apps/api-python/scripts/{v2_89_dia_d_auto_replay.py,v2_90_dia_d_feedback.py}`, `apps/web/src/features/auto-monitor/{dia-d-auto-feedback-panel.tsx,dia-d-auto-feedback-panel.test.tsx}`, `scripts/lib/window-forward.mjs`, `package.json`, `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`.
- **`Δ motor = 0`:** ningún fichero de motor tocado.
- **Freeze del runner (re-anclado):** este sello **mueve el árbol** `apps`/`packages`; `WINDOW_CONFIG` se **re-ancló** al árbol del commit funcional **`e9af4ada`** (`git rev-parse "HEAD:apps" "HEAD:packages"`): `apps` = `5cdd066671257c48f444a4d31002aae69701619c`, `packages` = `eb2242ea874027c5d2d759015ee11d23ba1fa983`. Editar el pin no mueve el árbol (el módulo vive en `scripts/`). `pnpm window:test` (25/25) no se ve afectado. Pin anterior (sello `v2.88.35-beta`): `apps` `9bba8571…` / `packages` `2ac1927b…` (`commit` = `1f31576c`).
- **CI DE TAG (POST-TAG, 2026-10-03):** `Release tag CI` run [`37118140439`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37118140439) (`ref=refs/tags/v2.88.36-beta`, HEAD `c2543adc`) → **`SUCCESS`**: **11 jobs `success`** (`security`, `shared`, `decision-spine`, `python`, `replay-repro`, `dr-verify`, `a7-gate`, `frontend`, `lifecycle-pg`, `playwright (mock E2E)`, `certify`) + `playwright (integrated E2E, opt-in)` `skipped` por diseño. `shared` **Window runner guards** (`pnpm window:test`) → `# tests 25 · # pass 25 · # fail 0`. `python`: **`4393 passed, 45 skipped`** ( **+12** sobre `v2.88.35` ) · `Contracts: 4 kept, 0 broken.` · `mypy 522 source files`. `frontend`: **`237` ficheros / `1359` tests** + `contract:check` OK. `replay-repro` → `REPRODUCIDO` (`1E3ADAC2…`). Tag anotado `v2.88.36-beta` → objeto `2898963d`, commit `c2543adc` (tip de `main`).
- **Sello previo de la cadena:** el commit funcional es `e9af4ada`; el tag apunta al tip de sellado `c2543adc` (re-anclaje del freeze + hashes), igual que `v2.88.35-beta` apuntaba a `d59ef8ea`.
