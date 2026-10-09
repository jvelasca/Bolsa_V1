# Evidencia `v2.88.100-beta` — `PAPER-2.1`: **conciliación estricta del material durable + panel de evidencia PAPER (`P2`) + identidad de la oportunidad en la decisión aprobada (`Δ motor ≠ 0` estricto · `Δ decisión = 0`)**

**Producto:** `V2.88.100-beta` · **Package:** `2.11.100-beta` · **AsOf:** 2026-10-09. **Sin migración nueva** (head `052_top3_opportunities`). Los 9 CLIs DÍA-D `v2_89`…`v2_97` sellan `2.11.100-beta` junto al `package.json` (guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py)).

> **Nota de árbol (honesta).** Sello **`Δ motor ≠ 0` en sentido ESTRICTO**: `git diff --name-only -- packages/py` **NO** está vacío. Añade **código Python read-only** de la evidencia PAPER (`paper_evidence_reconciliation.py`, `paper_evidence_reader.py`, `paper_evidence_adapter.py`) y del trazado del monitor (`auto_operational_monitor.py`, `auto_v2_entry.py`). Lo que **sí** es cero es la **decisión** (`Δ decisión = 0`): sin motor de decisión, sin worker, sin umbrales, sin Alembic, sin scheduler, sin cambios de comportamiento en endpoints existentes. El contrato HTTP **no cambia** (`contract:check` **OK**; el endpoint `GET /api/auto/paper-evidence` ya se selló en `v2.88.99`). **`replay-repro`** es el certificador y su cita es **POST-TAG**.

**Origen.** Endurece el contrato de evidencia PAPER de `PAPER-1` (`paper-confirmation-contract.ts`) y el adaptador de `PAPER-2` (`v2.88.99`): el material durable se cruza **sin admitir omisiones** (`closure_reconciliation`/`non_contradiction`), la superficie web pasa de **mapeo** a **panel visible** (`P2`) y se cierra la etapa `oportunidad → decisión` del recorrido AUTO destapada por la **auditoría interna del pipeline AUTO**. **Ningún** camino emite `CONFIRMED`.

---

## 1. Cambios (por bloque)

| # | Bloque | Qué hace | Implementación |
| --- | --- | --- | --- |
| 1 | **Conciliación estricta (`PAPER-2.1`)** | Cada cruce que no se puede **probar** degrada a contradicción nombrada en vez de aceptarse por omisión: `settlement_pnl_unmeasured` (PnL FIFO o del cierre sin medir ⇒ **no** reconcilia; la ausencia no se colapsa a `0`), `settlement_quantity_unmeasured` (cierre sin cantidad declarada), `duplicate_settlement_cycle` (dos cierres del mismo `cycle_id`: se conserva el **primero**, se bloquea la limpieza) y `settlement_without_account` (cierre sin cuenta atribuible ⇒ excluido, fail-closed). | [`paper_evidence_reconciliation.py`](../../../../packages/py/application/src/bolsa_application/paper_evidence_reconciliation.py), [`test_paper_evidence_reconciliation.py`](../../../../packages/py/application/tests/test_paper_evidence_reconciliation.py) |
| 2 | **Aislamiento por cuenta (lector)** | Un cierre durable **sin `account_id`** (nulo/vacío) NO entra en el ámbito consultado y **no** se lee como evidencia de la cuenta; un cierre de **otra** cuenta tampoco. Se cuenta y se declara `unattributed_settlements_excluded` y una contradicción `settlement_without_account` (fail-closed). | [`paper_evidence_reader.py`](../../../../packages/py/application/src/bolsa_application/paper_evidence_reader.py), [`test_auto_paper_evidence_reader.py`](../../../../apps/api-python/tests/test_auto_paper_evidence_reader.py) |
| 3 | **Compositor sin código nuevo** | Las contradicciones nuevas degradan `closure_reconciliation` y `non_contradiction` **sin** tocar el compositor: la vara ya estaba definida, sólo se le da material que **no** puede sortear. | [`paper_evidence_adapter.py`](../../../../packages/py/application/src/bolsa_application/paper_evidence_adapter.py), [`test_paper_evidence_adapter.py`](../../../../packages/py/application/tests/test_paper_evidence_adapter.py) |
| 4 | **Panel de evidencia PAPER (`P2`)** | Superficie de primer nivel que pinta el veredicto reservado (`NO CONFIRMADO`) con sus **siete criterios**, origen durable, medición y bloqueos, montada una sola vez en el panel DÍA-D AUTO. Distingue «Incumplido» de «Sin dato todavía» (`data-status`, vocabulario `absent-data`); la jerga (fuentes/contradicciones) vive tras el `Detalle técnico`; **sin** cuenta visible declara el hueco (fail-closed). Sin rama que promocione la confirmación. | [`paper-evidence-panel.tsx`](../../../../apps/web/src/features/auto-monitor/paper-evidence-panel.tsx), [`paper-evidence-panel.test.tsx`](../../../../apps/web/src/features/auto-monitor/paper-evidence-panel.test.tsx), [`dia-d-auto-panel.tsx`](../../../../apps/web/src/features/auto-monitor/dia-d-auto-panel.tsx) |
| 5 | **Identidad de la oportunidad (auditoría AUTO)** | La decisión **APROBADA** (`auto_entry_decision`) sella `signalId`, `opportunityScore` y `rank` en su payload durable; el monitor lee el envoltorio **anidado** de la propia decisión (`payload.risk` para `quantity`/`riskAmount`/`riskPct`; `payload.tradePlan` para `entry`/`structuralStop`) y `SIGNAL`/`TOP_N`/`RISK` pasan a `STEP_REACHED` para una operación **tomada**. Un settlement **duplicado** en el monitor se declara (`duplicate_settlement_cycle`, `PARTIAL`), conservando el primero de forma determinista. | [`auto_v2_entry.py`](../../../../packages/py/application/src/bolsa_application/auto_v2_entry.py), [`auto_operational_monitor.py`](../../../../packages/py/application/src/bolsa_application/auto_operational_monitor.py), [`test_auto_opportunity_identity.py`](../../../../packages/py/application/tests/test_auto_opportunity_identity.py) |
| 6 | **Contrato ampliado** | §2.1 «Conciliación estricta y aislamiento por cuenta (PAPER-2.1)»: tabla de las 4 reglas con su código de contradicción y la consecuencia declarada (*fail-closed* reduce `reconciled == settlements` respecto a material histórico que reconciliaba por ausencia). | [`contrato-evidencia-paper-confirmacion-2026-10-09.md`](../../contrato-evidencia-paper-confirmacion-2026-10-09.md) |
| 7 | **Bump + barrido** | `package.json` (`2.11.100-beta`) + `meta.bump` de `v2_89`…`v2_97`; `paper-evidence-panel.tsx` y `paper-confirmation-contract-labels.ts` entran en el barrido de primer nivel. | [`test_dia_d_bump_guard.py`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py), [`barrido-global-first-level.test.tsx`](../../../../apps/web/src/features/barrido-global-first-level.test.tsx) |

## 2. Reglas que NO cambian

- **`UNKNOWN ≠ 0`.** Un PnL o una cantidad de cierre sin medir **no** reconcilia y **no** se colapsa a `0`. Fuente no leída ⇒ criterio `unknown` y contadores `null`; fuente leída y vacía ⇒ cero **medido**.
- **Confirmación reservada.** `verdict` es el literal `NO_CONFIRMED`; el token suelto `CONFIRMED` **no** aparece. Aunque los siete criterios se cumplan, el veredicto **sigue** siendo `NO_CONFIRMED`. El panel **no** tiene rama que lo promocione.
- **Aislamiento estricto.** Un cierre sin cuenta atribuible **no** es evidencia de la cuenta consultada; se declara y se cuenta. La lectura es **account-scoped** (fail-closed `no_account_scope`, nunca global).
- **Una sola noción de cierre.** La conciliación **no** reimplementa FIFO: cuelga de `cycles_from_fills` (la misma autoridad que el informe AUTO-7, la confianza y el readiness).
- **Motor/decisión intactos.** Sin motor de decisión, sin worker, sin umbrales, sin Alembic, sin scheduler, sin re-habilitar `CONFIRMED`. Lo añadido es **traza y evidencia**, no comportamiento.

## 3. Verificación (local)

- `uv run pytest packages/py/application/tests -q` → **2562 passed** (+13 sobre `v2.88.99`).
- `uv run pytest apps/api-python/tests/test_auto_paper_evidence_reader.py apps/api-python/tests/test_auto_paper_evidence_route.py apps/api-python/tests/test_dia_d_bump_guard.py -q` → **8 passed** (5 del lector + 2 de la ruta + 1 del guardián).
- `uv run pytest apps/api-python/tests/test_auto_paper_evidence_pg.py -q` → **6 passed** contra **PostgreSQL real** (cadena durable, ausencia medida, cierre contradictorio, duplicidad y aislamiento por cuenta).
- `uv run mypy packages/py/application/src/bolsa_application/{paper_evidence_reconciliation,paper_evidence_adapter,paper_evidence_reader,auto_operational_monitor,auto_v2_entry}.py` → **Success** (5 ficheros).
- `uv run ruff check` (módulos y tests del sello) → **All checks passed** (10 `I001` de orden de imports corregidos).
- `pnpm --filter @bolsa/web run typecheck` (`tsc -b --noEmit`) → **OK** (exit 0).
- `pnpm --filter @bolsa/web run lint` → **0 errores** (23 avisos `react-hooks/exhaustive-deps` preexistentes, ajenos a este sello).
- `pnpm --filter @bolsa/web run test` → **290 ficheros / 2021 passed** (+1 fichero / +10 tests sobre `v2.88.99`); el bloque `auto-monitor` aislado → **12 ficheros / 82 passed**.
- `pnpm --filter @bolsa/web run contract:check` → **OK** (sin cambio de contrato HTTP).
- `uv run pytest apps/api-python/tests/test_dia_d_bump_guard.py -q` → **1 passed** (`2.11.100-beta`).
- **`Δ decisión = 0`**: sin motor de decisión, umbrales, Alembic ni scheduler; lo único que cambia en el camino AUTO es **qué se escribe en el journal durable** (identidad de la oportunidad) y **qué se declara** en el read-model, no **lo que se decide**. `replay-repro` lo certifica en el CI del tag.

## 4. Qué no cambia / deuda declarada

- **Motor de decisión/ejecución**, worker, umbrales, Alembic (head `052_top3_opportunities`) y scheduler: **intactos**.
- **`Δ motor ≠ 0` estricto:** se añade/endurece código Python **read-only** y trazado; ningún camino que decida o ejecute cambia. La evidencia lo declara en vez de esconderlo tras un `git diff` vacío que sería falso.
- **El panel `P2` es de lectura.** Consume el hook read-only (`useAutoPaperEvidence`) y **no** re-deriva el veredicto: `buildPaperConfirmationVerdict` sigue siendo la única autoridad.
- **La confirmación de la ejecución real PAPER sigue RESERVADA.** Ningún criterio aislado confirma la operativa; este sello hace la evidencia **más difícil de satisfacer**, no más fácil.
- **`E2E integrado`** del sello se declara `skipped` (opt-in) en el CI, **no** como prueba superada.
- **`CHANGELOG` de `2.11.99` (backfill).** El sello `v2.88.99` se taggeó sin entrada de `CHANGELOG`; se rellena aquí desde su evidencia durable, sin reescribir el tag ni su árbol.

## 5. Cita POST-TAG

**Pendiente.** Tag previsto **`v2.88.100-beta`** (objeto y commit se anclarán al cerrar; `Release tag CI` verde + `replay-repro` **`REPRODUCIDO`** ⇒ `Δ decisión = 0` certificado por CI). La cita se añadirá aquí y en el `CHANGELOG` una vez emitido el tag.
