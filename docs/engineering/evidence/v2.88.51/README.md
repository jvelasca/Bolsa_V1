# Evidencia `v2.88.51-beta` — `AUTO · UI`: **fix del PnL `PARTIAL` + congelación del AUTO UI SEMANTIC MODEL 1.0**

**Objeto:** el **siguiente chat, un auditor externo, o un Cursor distinto**. No es el historial (`PROJECT_STATE.md`).

**Producto:** `V2.88.51-beta` · **Package:** `2.11.51-beta` · **AsOf:** 2026-10-05 · **Nature:** `INVESTIGACION` · **Fase:** `V2.93…V2.97 DIA-D AUTO` · **Δ AUTO decision/execution motor = 0**.

**Schemas:** sin cambios (`dia-d-multi-band-v1`, `dia-d-thesis-exit-v5`, `dia-d-multi-cycle-ledger-v7`, `dia-d-thesis-stop-sequences-v2`). **Alembic:** head `048_journal_entry_dedupe_key` — **SIN migración**. **Contrato HTTP:** **sin cambio** (`contract:check` OK; `openapi.json`/`schema.d.ts` no se mueven).

**Padre:** [`v2.88.50`](../v2.88.50/README.md) (tag `f48975bb`, `Release tag CI` [`37297920781`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37297920781) VERDE) → [`v2.88.48`](../v2.88.48/README.md) → [`v2.88.47`](../v2.88.47/README.md) → [`v2.88.46`](../v2.88.46/README.md) → [`v2.88.45`](../v2.88.45/README.md).

**Decisión de alcance (declarada).** Sello **dirigido** que cierra el **único hallazgo nuevo** de la auditoría externa de `v2.88.50` y produce el entregable de diseño que el propio auditor pidió **antes** de extender la UI: el **`AUTO UI SEMANTIC MODEL 1.0`**. **NO** se re-corre el pipeline `DÍA-D` (A/C cerrada: reabrirla sería volver a preguntar lo mismo) y **NO** se implementa el refactor de pantallas. Las cifras OOS de `v2.88.50` se **heredan y citan**, no se re-miden.

---

## 0. Qué añade este sello (y qué NO)

Dos bloques, ambos **sin tocar el motor**:

1. **Fix del PnL que se publicaba `COMPLETE` con cierre `PARTIAL`.** El bloque `result` de `_build_cycle` sólo miraba `window_truncated`; un cierre degradado a `None`/`PARTIAL` por un `side` no clasificable (`unclassified_fills > 0`) **seguía publicando una cifra de dinero**. Corregido en backend (la condición usa la MISMA medición ya calculada) y en frontend (la cifra se rotula por su medición, no a fuego como `COMPLETE`).
2. **`AUTO UI SEMANTIC MODEL 1.0` (diseño congelado).** Documento que fija la semántica de las **14 etapas** antes de crear más pantallas, resolviendo `TOP_N ≠ DECISIÓN`, `SALIDA ≠ LIQUIDACIÓN` y `OPORTUNIDAD` como **contexto**.

**NO** toca el motor, los umbrales, `TOP_N`, la allocation ni las costuras de decisión. **NO** introduce contrafactuales. **NO** cierra la deuda de `stopBasisMismatchR`. **NO** re-mide `THESIS_EXIT`. **NO** sustituye ninguna pantalla ni toca el view-model `buildAutoOperationStory` (su migración al modelo es trabajo posterior, declarado en el propio documento).

> **Modelo de ejecución declarado:** `AUTO` **no deja una orden STOP en reposo**; el stop lo ejecuta el decider `D1`. Este sello **no** re-ejecuta nada.

---

## 1. Afirmaciones falsables (cada una con su forma de romperse)

| # | Afirmación | Cómo se rompe (falsación) | Evidencia |
| --- | --- | --- | --- |
| **1** | **Un cierre `PARTIAL` NO publica PnL.** En un ciclo que cierra (`buy`+`sell`) **más** un fill de `side` ilegible, `cycles_from_fills` reconstruye el `pnl` pero `result` sale `None`. | Que `result` publique una cifra con `closed_measurement != COMPLETE`. | §3.1; test `test_cycle_result_not_published_when_close_is_partial_by_unclassified_side` (**falla** sin el fix: publicaba `{'pnl': 100, ...}`). |
| **2** | **La cifra de PnL en la UI hereda la medición del cierre.** Un ciclo `PARTIAL` pinta `PARCIAL`; sólo `COMPLETE` muestra el número. | Que la UI pinte el número sin su medición. | §3.2; `auto-monitor.test.tsx` (2 tests nuevos). |
| **3** | **`Δ AUTO decision/execution motor = 0`.** Ninguna línea de motor cambia; sólo un read-model (`auto_operational_monitor.py`) y la UI. | Que `git diff` del motor no esté vacío. | §2 (`git diff` vacío en `auto_simulation_worker.py`/`simulated_broker.py`/`v2_87_…`); el artefacto del replay `v2.88.50` no se re-mide (sin cambio de motor). |
| **4** | **Sin cambio de contrato HTTP.** `openapi.json`/`schema.d.ts` no se mueven. | Que `contract:check` no coincida. | §2 (`contract:check OK`). |
| **5** | **El modelo semántico se congela por escrito, no en código.** Existe el documento y **no** se ha tocado ninguna pantalla. | Que falte el documento o que se haya reescrito el story-model. | §4; `git diff` sin cambios en `apps/web/src/features/auto-monitor/*` más allá de `auto-cycle-timeline.tsx`. |

---

## 2. Verificación (gates)

| Gate | Resultado |
| --- | --- |
| `pytest packages/py/application/tests/test_auto_operational_monitor.py apps/api-python/tests/test_dia_d_bump_guard.py` | **53 passed** |
| `pytest packages/py/application/tests` (directorio completo) | **2492 passed** (`207.62 s`) |
| `ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| `lint-imports --config packages/py/.importlinter` | **4 kept / 0 broken** |
| `mypy` (gate CI: `domain/market/infrastructure/application/src` + `api-python/src`, `--follow-imports=silent`) | **Success: no issues found in 531 source files** |
| Web `vitest` (`src/features/auto-monitor`) | **24 passed** (7 ficheros; **+2** sobre `22` de `v2.88.50`) |
| `@bolsa/web` `typecheck` (`tsc -b --noEmit`) | limpio |
| `@bolsa/web` `lint` | **0 errores** (`24` warnings pre-existentes) |
| `@bolsa/web` `contract:check` | **OK** — `openapi.json`/`schema.d.ts` coinciden |
| `@bolsa/shared` `vitest` | **804 passed | 1 todo** (97 ficheros) |
| `@bolsa/shared` build | limpio |
| Guard de versión | `test_dia_d_bump_guard.py` verde ⇒ `meta.bump` de `v2_89`…`v2_97` == `package.json` (`2.11.51-beta`) |

> **Nota de método (auditable).** El test de regresión del backend **se verificó en rojo**: se revirtió temporalmente el fix y el caso falla con `assert {'pnl': Decimal('100'), ...} is None` (el bug medido), y vuelve a verde al restaurarlo. No se relaja ninguna aserción.

---

## 3. El fix, en detalle

### 3.1 Backend — `result` se rige por la medición del cierre

`packages/py/application/src/bolsa_application/auto_operational_monitor.py` (`_build_cycle`, ~L721): el bloque `result` pasa de `None if closed is None or window_truncated` a regirse por la **misma** medición ya calculada arriba:

```python
"result": (
    None
    if closed is None or closed_measurement != MEASUREMENT_COMPLETE
    else {"pnl": closed.get("pnl"), "closedAt": closed.get("closedAt")}
),
```

`closed_measurement` se degrada a `PARTIAL` cuando `window_truncated or unclassified_fills > 0`, así que ahora un cierre no afirmable **no** publica cifra de dinero. (Es la familia de fallo que la auditoría viene señalando: un hueco declarado que se pierde en el último paso de la proyección.)

### 3.2 Frontend — la cifra hereda la medición

`apps/web/src/features/auto-monitor/auto-cycle-timeline.tsx`: la cifra de PnL usa `cycle.closedMeasurement ?? "UNKNOWN"` en vez de `"COMPLETE"` a fuego, y cuando la medición no es `COMPLETE` **rotula la medición** (`formatMeasurementLabel` ⇒ `PARCIAL`/`NO MEDIDO`) en lugar de presentar el número sin ambigüedad. Añade `data-testid="auto-monitor-cycle-pnl"` / `data-pnl-measurement` para la aserción. `formatMonitorFactValue` por sí solo **no** bastaba: devuelve el número para un valor no nulo, por lo que el rotulado exigía el branch explícito (detalle declarado porque un caller futuro podría repetir el patrón).

---

## 4. `AUTO UI SEMANTIC MODEL 1.0` (resumen del entregable)

`docs/engineering/spec-auto-ui-semantic-model-1-2026-10-05.md` (estado **DISEÑO CONGELADO**). Congela, antes de extender la UI:

- Las **14 etapas** (`OPORTUNIDAD → … → EXPLICACIÓN`) y su **clase**: hecho durable / derivada / contexto / explicación.
- Los **dos ejes** (no confundir): **estado de etapa** (`REACHED/PENDING/ABSENT/NOT_MEASURED`) y **medición del hecho** (`COMPLETE/PARTIAL/UNKNOWN`), con la regla `UNKNOWN ≠ 0`.
- Definiciones duras con criterio de admisión (hecho, derivación, contexto, decisión, explicación).
- Las **tres correcciones** al piloto de `v2.88.50`: **`TOP_N ≠ DECISIÓN`** (separa SELECCIÓN/TOP-N de la decisión de cartera; sin traza propia, `NOT_MEASURED`), **`SALIDA ≠ LIQUIDACIÓN`** (intención vs hecho financiero; sin traza propia, se pliega con `derivedNote`) y **`OPORTUNIDAD` como contexto** (bloque «contexto que la originó», no un `NO MEDIDO` suelto).
- La **navegación objetivo** (`OPERAR · CARTERA · RIESGO · ANÁLISIS · SISTEMA`; el usuario no navega por conceptos internos) y el **plan de migración post-1.0** (Operación por defecto, enlace EXPLICACIÓN→DÍA-D, `MeasurementValue` único, persistencia en URL).
- **Límites:** PIT histórico institucional (P3); los `23 orden_creada_sin_fill` van a una futura **Execution Analysis** separada de la UI principal; `CONFIRMED` **NO** se emite.

**No** toca código de pantallas: es contrato de significado.

---

## 5. Límites declarados (NO se cierran aquí)

- **El fix es de proyección/UI, no de motor:** el hueco de `result` era un read-model; el motor no cambia.
- **`unclassified_fills` es un caso raro pero real:** sólo se dispara con fills cuyo `side` no es `buy`/`sell` legible; el fix es barato y elimina la última vía por la que una cifra de dinero podía viajar junto a un cierre no afirmable.
- **El modelo semántico NO se implementa aquí:** las 3 correcciones conceptuales (SELECCIÓN, SALIDA, CONTEXTO) se congelan por escrito; el piloto `buildAutoOperationStory` sigue como está hasta la migración.
- **PIT histórico institucional** (listings/delistings/sector) sigue **abierto** (P3 científico).
- **REPLAY/OOS ≠ PAPER:** `P3-2`/`P3-3` **ABIERTAS**; `CONFIRMED` **NO** se emite.
- **`n` pequeño** en DÍA-D y banda global que cruza cero (heredado de `v2.88.50`, sin cambios): nada de esto es citable como punto.

---

## 6. Cómo se reproduce

```bash
# 1) Fix + regresión del backend (53 passed; el test de regresión falla sin el fix).
uv run --no-sync python -m pytest \
  packages/py/application/tests/test_auto_operational_monitor.py \
  apps/api-python/tests/test_dia_d_bump_guard.py -q

# 2) Gates estáticos.
uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml
uv run --no-sync lint-imports --config packages/py/.importlinter
uv run --no-sync mypy packages/py/domain/src packages/py/market/src \
  packages/py/infrastructure/src packages/py/application/src \
  apps/api-python/src --follow-imports=silent

# 3) UI.
pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web lint
pnpm --filter @bolsa/web contract:check
pnpm --filter @bolsa/shared exec vitest run
```

**No** se reproduce el pipeline `DÍA-D` en este sello (declarado): las cifras OOS se **citan** de `v2.88.50`.

---

## 7. Sello

- **Añadidos:** `docs/engineering/spec-auto-ui-semantic-model-1-2026-10-05.md`, `docs/engineering/evidence/v2.88.51/README.md`.
- **Modificados:** `packages/py/application/src/bolsa_application/auto_operational_monitor.py` (guard de `result`), `packages/py/application/tests/test_auto_operational_monitor.py` (test de regresión), `apps/web/src/features/auto-monitor/auto-cycle-timeline.tsx` (medición del PnL), `apps/web/src/features/auto-monitor/auto-monitor.test.tsx` (2 tests), `package.json` (`2.11.51-beta`), `v2_89`…`v2_97` (`meta.bump`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`.
- **`Δ AUTO decision/execution motor = 0`:** ningún fichero de motor tocado; el cambio vive en un read-model (`bolsa_application`) y en la UI; el contrato HTTP no se mueve.
- **Tag:** `v2.88.51-beta` (**anotado**, objeto `ad878fb1…`) → commit `fa487409` (`feat` funcional `b05de1b5` + `chore(window)` de re-anclaje del freeze a `b05de1b5`). **`Release tag CI` run [`37305844986`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37305844986) VERDE** (`ref=refs/tags/v2.88.51-beta`, `attempt 1`, `2026-10-05T11:53:28Z`): **`11 jobs success`** (`python`, `security`, `dr-verify`, `playwright (mock E2E)`, `shared`, `lifecycle-pg`, `a7-gate`, `decision-spine`, `replay-repro`, `frontend`, `certify`) + `playwright (integrated E2E, opt-in)` `skipped` por diseño; `certify` `success`. Job `python`: **`4538 passed, 45 skipped`** (`83.63 s`; **`+1`** sobre `4537` de `v2.88.50` = el test de regresión del PnL `PARTIAL`), `ruff` `All checks passed!`, `imports` `4 kept, 0 broken`, `mypy` limpio (`531` ficheros). Job `replay-repro`: **`VEREDICTO REPRODUCIDO`** `sha256 1E3ADAC2…` = sello `24066225…` (`3 445 622 B` CRLF / `3 340 728 B` LF) ⇒ **`Δ motor = 0` confirmado por CI**.
- **`GitHub Release` `v2.88.51-beta` publicado** (pre-release): <https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.88.51-beta>.

> **Límite estructural (declarado):** `Release tag CI` **sólo** corre al **empujar** el tag ⇒ **ningún tag puede contener su propio resultado de CI**. El fichero **dentro** del tag declara la cita como `POST-TAG`; la cita real viaja en **esta** §7 (escrita en `main` **después** del tag) y en el **`Release`**.

- **Entrega a auditoría externa (MIA):** [`docs/engineering/entrega-auditoria-externa-mia-v2.88.51-2026-10-05.md`](../../entrega-auditoria-externa-mia-v2.88.51-2026-10-05.md) — pack autocontenido (§7 = guion de auditoría desde GitHub: tag → evidencia → `Release` → artefacto del replay → reproducción).
