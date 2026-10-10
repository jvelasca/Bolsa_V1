# Evidencia `v2.88.105-beta` — **Cierre de auditoría AUTO: honestidad de lectura `S5` · identidad de estrategia · E2E reproducible · P&L realizado (`F2-3`) · motivo de ranking (`F2-4`) · DÍA-D declarado (`P4-3`) · simplificación UI** (UI + **motor aditivo** · **`Δ motor ≠ 0`** · **`Δ decisión = 0`** · contrato **ampliado** · sin migración)

**Producto:** `V2.88.105-beta` · **Package:** `2.11.105-beta` · **AsOf:** 2026-10-10. **Sin migración nueva** (Alembic head sigue `052_top3_opportunities`). Los 9 CLIs DÍA-D `v2_89`…`v2_97` sellan `2.11.105-beta` junto al `package.json` (guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py)).

> **Naturaleza (honesta).** Este sello **sí** mueve `packages/py/**` (a diferencia de `v2.88.104`, UI-only): son cambios **aditivos** y **`Δ decisión = 0`** (no se tocan umbrales, reparto, `TOP_N`/régimen/selección/protección). Amplía el contrato HTTP (`totalRealizedPnl` + `serving`; `contract:gen` regenerado, `contract:check` **OK**). Cierra las fases `F1`–`F7` del plan «Cierre de auditoría AUTO»; `replay-repro` debe seguir **`REPRODUCIDO`** (análisis en §4).
> **Origen.** Auditoría 1 (honestidad de lectura del puente `S5`, identidad de la estrategia ejecutada, E2E integrado reproducible) + deuda PARKED FASE 2 (`F2-3`/`F2-4`) + `P4-3` + simplificación de la UI AUTO.

**Base:** [`evidence/v2.88.104/README.md`](../v2.88.104/README.md) (puente AUTO → DÍA-D `S5`).
**Cita POST-TAG.** **Tag anotado `v2.88.105-beta`:** **PENDIENTE de completar** (objeto → commit + `Release tag CI` `VERDE`/`ROJO` + `replay-repro`) tras el run de CI del tag.

## 1. Cambios (por fase)

| Fase | Bloque | Qué demuestra | Implementación |
| --- | --- | --- | --- |
| `F0` | **Gate de viabilidad** | Nota read-only que fija UI-only vs motor: `F3` es UI-only (el ciclo solo publica el **sello** `strategyVersion`, no el `strategyDefinitionId`); `F4` es motor + contrato sin Alembic; `F5`/`F6` motor. | [`gate-f0-identidad-estrategia-y-pnl-realizado-2026-10-10.md`](../../gate-f0-identidad-estrategia-y-pnl-realizado-2026-10-10.md) |
| `F1` | **Honestidad de lectura `S5`** | El fallo del **catálogo de instrumentos** (`instrumentsQuery.isError`) se propaga al puente y se declara **`No disponible`** (fallo), **no** «Sin dato todavía» (ausencia); manda sobre `loading` y sobre el hueco de instrumento; fail-closed de `verifyHref`. | [`auto-operation-strategy.ts`](../../../../apps/web/src/features/auto/auto-operation-strategy.ts), [`use-auto-operation-strategy.ts`](../../../../apps/web/src/features/auto/use-auto-operation-strategy.ts) |
| `F2` | **E2E integrado reproducible** | El journey AUTO → `POST /api/backtests/run` **deja de saltarse por falta de ciclo**: el `beforeAll` siembra un ciclo AUTO durable reutilizando el CLI dev `seed_auto_cycle_for_ui.py` como **subproceso** (sin reimplementar lógica de backend) y el `afterAll` limpia (simétrico `--cleanup` + assert sin residuo). Un `skipped` sigue siendo **declarado**, nunca fingido. | [`auto-cycle-seed.ts`](../../../../apps/web/e2e/helpers/auto-cycle-seed.ts), [`gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts`](../../../../apps/web/e2e/gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts) |
| `F3` | **Identidad de la estrategia ejecutada** | Se **separan** en superficie «Mejor estrategia del valor (Finalistas TOP #1)» (lo disponible) de «Estrategia ejecutada declarada por el ciclo» (el sello `cycle.strategyVersion`), y se **declara** que la coincidencia es **heurística textual por token completo** — no una identidad exacta que el read-model aún no materializa. | [`auto-operation-strategy-card.tsx`](../../../../apps/web/src/features/auto-monitor/auto-operation-strategy-card.tsx), [`auto-operation-strategy.ts`](../../../../apps/web/src/features/auto/auto-operation-strategy.ts) |
| `F4` | **`F2-3` P&L realizado agregado** (motor + contrato) | Se publica el **realizado de todo el historial** en el resumen de cuenta (`totalRealizedPnl`) y se pinta a primer nivel en AUTO («Resultado realizado»). Reutiliza la máquina **canónica** del tax report (`_compute_realized_gains`, FIFO/avg, mismas fees) sin el filtro de ejercicio ⇒ **concilia** con `net_realized_gain`. `null`⇒«Sin dato todavía» (**nunca** `0`). | [`tax_report.py`](../../../../packages/py/domain/src/bolsa_domain/tax_report.py), [`summary.py`](../../../../packages/py/application/src/bolsa_application/accounts/summary.py), [`accounts.py`](../../../../apps/api-python/src/bolsa_api/schemas/accounts.py), [`auto-account-figures.ts`](../../../../apps/web/src/features/auto/auto-account-figures.ts) |
| `F5` | **`F2-4` motivo de ranking por ciclo** (motor + shared) | El productor **sella** el desglose del score (`OpportunityScore.components` ⇒ `opportunityComponents`) en `auto_entry_decision` (clave **omitida** si no hay ⇒ la ausencia es información); el paso `TOP_N` lo publica con su medición; la historia AUTO materializa el contexto `RANKING` («Motivo de selección») humanizado. Un código no catalogado degrada a «Sin dato todavía». | [`auto_v2_entry.py`](../../../../packages/py/application/src/bolsa_application/auto_v2_entry.py), [`auto_operational_monitor.py`](../../../../packages/py/application/src/bolsa_application/auto_operational_monitor.py), [`auto-ranking-motive.ts`](../../../../packages/shared/src/cognitive/auto-ranking-motive.ts), [`auto-operation-story.ts`](../../../../packages/shared/src/cognitive/auto-operation-story.ts) |
| `F6` | **`P4-3` DÍA-D declarado** (motor/rutas) | La superficie **declara** su modo real `serving = PRECOMPUTED_ARTIFACT` (artefacto precalculado por job offline; **no** se recalcula en vivo ni a demanda). El cómputo canónico exige un **replay durable pesado + `ensure_migrated`**: inviable en el ciclo de una petición. **No se simula** «en vivo». | [`auto_dia_d_feedback.py`](../../../../apps/api-python/src/bolsa_api/api/v1/routes/auto_dia_d_feedback.py), [`dia-d-auto-feedback-panel.tsx`](../../../../apps/web/src/features/auto-monitor/dia-d-auto-feedback-panel.tsx) |
| `F7` | **Simplificación UI AUTO** | Se eliminan duplicidades inequívocas: el TOP3 **colapsa** un mismo `assetId` repetido (el espejo durable no tiene clave natural única); `rankNote` (`ranking ≠ decisión`) se declara **una sola vez** por superficie; se retira un bloque **inalcanzable** en Riesgo y la nota de ranking duplicada en Operar. | [`auto-top3-opportunities.ts`](../../../../apps/web/src/features/auto/auto-top3-opportunities.ts), [`auto-top3-panel.tsx`](../../../../apps/web/src/features/auto/auto-top3-panel.tsx), [`auto-operar-page.tsx`](../../../../apps/web/src/features/auto/auto-operar-page.tsx), [`auto-riesgo-page.tsx`](../../../../apps/web/src/features/auto/auto-riesgo-page.tsx) |
| Bump | — | `package.json` (`2.11.105-beta`) + `meta.bump` de `v2_89`…`v2_97`. | [`test_dia_d_bump_guard.py`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) |

## 2. Reglas que NO cambian

- **`Δ decisión = 0`.** Sin motor de decisión, sin umbrales, sin reparto de capital, sin `TOP_N`/régimen/protección/selección. `F4` añade una **lectura** agregada; `F5` **sella** un hecho que el ranker ya calculaba y lo **proyecta**; `F6` solo **declara** metadatos. Ninguno cambia la decisión.
- **Sin migración.** Alembic head sigue `052_top3_opportunities`.
- **`UNKNOWN ≠ 0` y carga ≠ hueco.** Un dato ausente se rotula «Sin dato todavía»; un fallo de lectura se rotula «No disponible»; jamás se colapsa a `0`. `F4`: `0.0` solo con historial genuinamente vacío (hecho conocido). `F5`: sin desglose durable, el hueco es `UNKNOWN`.
- **`ranking ≠ decisión`.** El motivo de `F5` describe la **selección** (por qué entró en el TOP-N), no la cartera; la nota lo declara literalmente.
- **`propuesta ≠ posición materializada`** y **separación SIM/real**: intactas; la cifra de `F4` viaja como «en la cuenta simulada».
- **Sin `CONFIRMED`.** `F6` conserva las cuatro capas no equivalentes y `CONFIRMED` sigue **reservado** y **no emitido** (el techo real es `OOS_SUPPORTED`).

## 3. Verificación (local)

- `pnpm --filter @bolsa/web exec tsc --noEmit` → **OK** (exit 0).
- `pnpm --filter @bolsa/web exec eslint src` → **0 errores** (23 avisos `react-hooks/exhaustive-deps` preexistentes).
- `pnpm --filter @bolsa/web exec vitest run` → **294 ficheros / 2074 tests verdes**.
- `pnpm --filter @bolsa/web run build` → **OK**.
- `pnpm --filter @bolsa/web run contract:check` → **OK** (contrato regenerado: `totalRealizedPnl` + `serving`).
- `uv run ruff check packages/py apps/api-python --config pyproject.toml` → **All checks passed** (exit 0).
- `uv run lint-imports --config packages/py/.importlinter` → **4 contratos kept, 0 broken** (exit 0).
- `uv run mypy … --follow-imports=silent` → **Success: no issues found in 544 source files** (exit 0).
- `uv run pytest packages/py/domain/tests packages/py/application/tests -q` → **2706 passed** (exit 0).
- `uv run pytest test_dia_d_bump_guard + api-python tocados -q` → **46 passed** (exit 0).
- **E2E integrado `S5`** (`gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts`, opt-in) → **3/3 verdes** contra stack real (FastAPI + PostgreSQL), con **teardown sin residuo** (0 reservas/fills/ciclos); hermano **mock** → **2/2**.
- **Web shared** (`auto-ranking-motive` + `auto-operation-story`) → **27 passed** (F5).

## 4. Fiabilidad y `replay-repro` (**`Δ motor ≠ 0`**)

Este sello **sí** toca `packages/py/**`, así que `replay-repro` debe **regenerar el artefacto del sello y seguir `REPRODUCIDO`**. Análisis de por qué los cambios son **aditivos y fuera de la superficie capturada** del artefacto congelado (`v2_87_replay_oos_durable_cycle.py`):

- **`journalReasons`** agrega **solo** `reasonCodes` (`collect_journal_reasons`). `F5` añade la clave **`opportunityComponents`** —distinta— ⇒ el agregado **no cambia**.
- **`cycleDetail`** (lo único que lee el journal de gestión por ciclo) va **apagado por defecto** (`capture_cycle_detail=False`): «con la costura apagada la clave NO se añade, de modo que el artefacto congelado de `replay-repro` sale **byte a byte igual**».
- **`F4`** (realizado de cuenta) y **`F6`** (ruta/DTO/panel) **no** participan del camino del replay.

⇒ **Los bytes del artefacto congelado no cambian.** La **autoridad** es el job CI `replay-repro` del tag (regenera desde el fixture y ASSERTA el SHA-256); se declara aquí para que el sello no quede a ciegas.

## 5. Qué no cambia / deuda declarada

- **Motor de decisión/ejecución**, umbrales, Alembic (head `052_top3_opportunities`). Sin `contract:gen` **fuera** de lo declarado.
- **`P4-3`** se **declara** (modo `PRECOMPUTED_ARTIFACT`), **no** se resuelve como «en vivo»: el feedback DÍA-D **sigue** siendo artefacto precalculado por CLI.
- **E2E integrado `opt-in`** (un `skipped` **no** certifica); la ejecución del job CI `playwright-integrated` **no** se corrió en local (sí el journey, contra stack real).
- **`23` warnings `react-hooks/exhaustive-deps`** (`eslint`, **0 errores**): preexistentes, ajenos a este sello.
- **Tag `unsigned`.**
