# Evidencia `v2.88.131-beta` — evidencia funcional AUTO por valor de ESTUDIO (cadena de 9 etapas desde hechos durables + identidad ejecutada vs mejor puntuada)

> **Bump:** `2.11.130-beta` → **`2.11.131-beta`** (`package.json` + `meta.bump` del CLI OOS `v2_87`, de los 9 CLIs `v2_89`…`v2_97`, del certificador `v2_98` y del nuevo CLI `v2_99`; guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) verde, ahora **ampliado** con `v2_98`/`v2_99`).
>
> **Naturaleza:** incremento **mixto** — **dominio puro nuevo** (`auto_chain_durable_reader`), **CLI read-only** (`v2_99`), **proyección durable** del lado EJECUTADO del artefacto DÍA-D (`v2_89`), **gate PG** nuevo y **UI/shared** (etiquetado). **`Δ motor de decisión = 0`** (no se toca umbral, reparto, `TOP_N`, régimen, selección, protección ni ejecución) · **`Δ decisión = 0`** · **`Δ contrato HTTP = 0`** (no se amplía el endpoint read-only `/auto/estudio-audit`) · **SIN migración** (head `053_dia_d_cycle_verifications`). Tag **unsigned**.
>
> **Base:** `v2.88.130-beta`.

---

## 0. Qué cierra (y qué NO)

**Cierra** el hueco declarado en `v2.88.130`: la evidencia de la operativa AUTO **por cada valor del universo ESTUDIO y por ciclo** deja de medir solo **4 de 9** etapas en el lado EJECUTADO. Ahora la cadena completa se LEE de **hechos durables**:

```
SIGNAL -> TOP_N -> RISK -> RESERVATION -> ORDER -> FILL -> PROTECTION
       -> SETTLEMENT -> CYCLE_CLOSED (P&L conciliado) -> verificación DÍA D
```

Regla de honestidad rectora (**`UNKNOWN ≠ 0`**): una etapa sin traza durable viaja **`None`** con su `measurement` (hueco **declarado**); **nunca** un `0` de relleno (un `0` afirmaría «no ocurrió», que no es lo mismo que «no lo sé»).

**NO cierra** (se declara): la **ventana PAPER real** (`P3-2`/`P3-3`, ADR-046) ni la **rentabilidad/magnitud** del P&L — son **OPERACIÓN** + medición longitudinal; el gate CI ejerce el **worker real sobre ESTUDIO sembrado en PG** (evidencia de cadena **funcional**, no de mercado real); y el aislamiento XTB `G4`/`G6` + `G3` residual siguen abiertos.

---

## 1. Fuente durable de cada etapa

| Etapa | Fuente durable |
| --- | --- |
| `SIGNAL` | `decision_journal_entries` (`event_type = auto_entry_decision`) |
| `TOP_N` | `top3_opportunities` (foto del selector cross-asset, migración `052`) |
| `RISK` | `portfolio_reservations.reserved_risk` (riesgo de ciclo) |
| `RESERVATION` | `portfolio_reservations` por `cycle_id` |
| `ORDER` | `decision_journal_entries` (`event_type = auto_entry_order`) |
| `FILL` | `sim_fill_finance_context` + `execution_events` |
| `PROTECTION` | `auto_exit_orders` / `auto_protection_event` |
| `SETTLEMENT` | `decision_journal_entries` (`event_type = auto_cycle_settlement`) |
| `CYCLE_CLOSED` | `cycles_from_fills` + libro aplicado (`position_ledger`) |
| `DÍA D` | `dia_d_cycle_verifications` (migración `053`) por `cycle_id` |

---

## 2. Lector durable único — [`auto_chain_durable_reader.py`](../../../../packages/py/application/src/bolsa_application/auto_chain_durable_reader.py)

Núcleo **puro/read-only** que proyecta la cadena COMPLETA por ciclo reutilizando el lector único canónico [`read_operational_monitor`](../../../../packages/py/application/src/bolsa_application/auto_operational_monitor.py) (**sin** un segundo FIFO de P&L ni reimplementar el motor) y la foto `top3_opportunities`. Reutiliza la tupla canónica `OPERATIONAL_STEPS` como **fuente única** (`CANONICAL_STEPS`).

- `project_cycle_steps(cycle)` — proyección por paso: `1` si el hecho durable lo enciende, **`None`** si no (nunca `0`).
- `chain_gaps(cycle)` — etapas encendidas/no encendidas **con su estado** (`reached`/`unknown`/`absent`/`pending`); **sin `unknown` silencioso**.
- `executed_rank(cycle)` / `executed_identity(cycle)` — puesto y identidad **EJECUTADA** leídos del hecho durable del ciclo (`payload.rank`, `strategyPresetKey`/`strategyVersion`); **nunca** inferidos del ranking (sin identidad declarada ⇒ `None` + `measurement = UNKNOWN`).
- `best_scored_asset(snapshot)` — fila `rank == 1` de la foto `top3_opportunities`; es la **referencia «mejor puntuada»**, no la ejecutada.
- `resolve_executed_vs_best(...)` — veredicto `executedIsTopRanked` / `executedIsBestScoredAsset` que **nunca** afirma `False` sin término de comparación (`None` si falta la foto o el `rank`). Declara además `bestScoredPresetKey` (siempre `None`: la foto cross-asset **no** sella identidad de estrategia ⇒ el emparejamiento por preset es un **hueco declarado**, `presetMatch = None`, nunca un relleno con el de la ejecutada).
- `value_strategy(cycles)` — identidad **EJECUTADA** que declara el **VALOR**, **reutilizando** los resolutores canónicos de [`estudio_audit`](../../../../packages/py/application/src/bolsa_application/estudio_audit.py) (`_cycles_for_symbol`: clave canónica `cycleId`, orden natural, dedup declarada; `_strategy_for_symbol`: identidad única o **AMBIGUA**). Un valor con ciclos de identidades distintas **no** elige «ganadora»: `presetKey = None` + `presetKeyAmbiguous = True`.
- `value_strategy_from_dia_d(verifications)` — misma identidad resuelta sobre la **verificación DÍA-D** (`dia_d_cycle_verifications`): **fuente durable INDEPENDIENTE** del ciclo, para contrastar sin derivar una segunda verdad.
- `executed_vs_dia_d(...)` — coincidencia de identidad entre el ciclo y su verificación DÍA-D: `True`/`False` solo con **ambas** partes; con una sola, `None` (`UNKNOWN ≠ 0`).
- `dia_d_link(...)` — declara `linkable` + el borrador de `upsert` **reutilizando** [`build_dia_d_cycle_verification_draft`](../../../../packages/py/application/src/bolsa_application/dia_d_cycle_verification.py) (sin duplicar sus precondiciones); borrador incompleto ⇒ `None` + `linkable = False`.
- `pnl_reconciliation(cycle)` — conciliación `CYCLE_CLOSED.pnl` vs `SETTLEMENT.pnl` **al quantum del dinero** (`NUMERIC(18,6)`, `ROUND_HALF_UP` `1e-6`); sin ambas cifras ⇒ `None` (nunca un `True` optimista).
- `build_chain_evidence_artifact(...)` — artefacto canónico **puro y determinista** (`kind: AUTO_ESTUDIO_CHAIN_EVIDENCE`, `schemaVersion: auto-estudio-chain-v1`, `readOnly: true`): agrupa por valor de ESTUDIO, publica por ciclo la cadena + identidad + `executedVsBest` + `executedVsDiaD`/`diaDLink` + P&L y por valor `strategy`/`strategyDiaD`, y declara aparte los ciclos **fuera** del universo ESTUDIO (`cyclesOutsideEstudio`) **sin** descartarlos en silencio.
- `read_top3_snapshot` / `read_dia_d_verifications` / `read_estudio_chain_evidence` — lectores **read-only** (`SELECT`) que enlazan la foto TOP3 y la verificación DÍA-D por `cycle_id` (la verificación viaja con `instrument_id`/`symbol` para poder recomponer su borrador canónico).
- `day_durable_chain_counts(session, account_id, day)` — cuentas durables por etapa contable (`SIGNAL`/`TOP_N`/`RISK`/`ORDER`/`SETTLEMENT`) del día `[00:00, +24h)` UTC; fuente ilegible ⇒ `None` (hueco declarado, nunca `0`).

---

## 3. Cierre de los 5 huecos en el artefacto DÍA-D ([`v2_89`](../../../../apps/api-python/scripts/v2_89_dia_d_auto_replay.py))

`_read_executed_facts` proyectaba solo `RESERVATION`/`FILL`/`PROTECTION`/`CYCLE_CLOSED` y declaraba `SIGNAL`/`TOP_N`/`RISK`/`ORDER`/`SETTLEMENT` como huecos. Ahora esos cinco pasos **tienen fuente durable** y se cuentan como el lado DECLARADO (que también son cuentas) vía `day_durable_chain_counts`; una fuente ilegible deja el paso en `None`.

---

## 4. CLI read-only de evidencia — [`v2_99_auto_estudio_chain_evidence.py`](../../../../apps/api-python/scripts/v2_99_auto_estudio_chain_evidence.py)

Por cuenta y ventana, itera el **universo ESTUDIO** (camino canónico `resolve_estudio_universe`, sin reimplementar ESTUDIO) y emite por valor y por `cycle_id`: las **9 etapas** con su `measurement`, la identidad **EJECUTADA** (`strategyPresetKey`/`strategyVersion` + `rank`) contrastada con `bestScoredPresetKey` (hueco declarado: la foto no sella identidad), el contraste **independiente** con la verificación DÍA-D (`executedVsDiaD` + `diaDLink`), el **P&L conciliado** (monitor ↔ `auto_cycle_settlement` ↔ libro aplicado) y el resolutor canónico del valor (`strategy`/`strategyDiaD`, con ambigüedad declarada).

- Salida JSON **determinista** (`sort_keys`) en `operability_runs/estudio-chain/<...>.json`, `readOnly=true`.
- La tabla humana añade dos columnas de **veredicto separadas**: `vs MEJOR` (`mejor puntuada` / `no #1` / `n/d`) y `vs DIA D` (`identidad =` / `identidad !=` / `sin verif.` / `n/d`), para que el `#1` de referencia no se confunda con lo ejecutado **ni** con el eslabón DÍA-D.
- `--cycle-id` (drill-down a UN ciclo) / `--instrument-id` / `--watch` (allowlist que **intersecta** ESTUDIO) / `--json` / `--out`.
- Sale `0` aunque no haya ciclos (declarar el hueco **no** es un fallo); `2` si el material no se pudo leer.
- **No** amplía el contrato HTTP: el bloque aditivo opcional en `GET /auto/estudio-audit` **no** se aplicó (se mantiene `Δ contrato HTTP = 0`).

---

## 5. Gate CI obligatorio (fail-if-skipped) — [`test_auto_estudio_chain_evidence_pg.py`](../../../../apps/api-python/tests/test_auto_estudio_chain_evidence_pg.py)

Test **PG-gated** (gate propio `AUTO_ESTUDIO_CHAIN_PG_REQUIRED=1`) que conduce el **PROCESO real** (`python -m bolsa_api.workers.scheduler_worker`) sobre el universo **ESTUDIO** sembrado (`AUTO_ENGINE_SIMULATED_WATCH_FROM_ESTUDIO=1` + `AUTO_OPERATIONAL_AUDIT=1`) y, por cada valor y ciclo, asserta:

1. que las **NUEVE etapas** se encienden **desde hechos durables** (un `None` es hueco real, no se admite);
2. que la identidad **EJECUTADA** viaja sellada por el ciclo y **no** se cae al `#1` cuando no resuelve (en el sandbox la estrategia es **sin versión** ⇒ `preset`/`version` son huecos **explícitos** y el `rank` durable **sí** viaja: prueba de que no se inventa la identidad);
3. que el contraste con la **mejor puntuada** nunca fabrica veredicto (`in (True, False, None)`) y que `bestScoredPresetKey`/`presetMatch` viajan `None` (la foto cross-asset **no** sella identidad: no se rellena con la de la ejecutada);
4. que el resolutor canónico del valor declara identidad **única o AMBIGUA** (nunca una «ganadora») y clasifica **todo** ciclo (`enlazables + sin cycleId + repetidos == total`);
5. que el último eslabón se contrasta con fuente **INDEPENDIENTE**: `diaDLink.linkable is (diaD is not None)` y, sin verificación durable, `executedVsDiaD.matches is None` + `measurement == UNKNOWN` (**jamás** un `False` con una sola parte);
6. la conciliación de P&L: `CYCLE_CLOSED.pnl == SETTLEMENT.pnl` por ciclo y la suma cuadra **EXACTA** al **libro aplicado** (fuente INDEPENDIENTE) al quantum del dinero (`realized_notional_from_applied_fills`);
7. **control negativo**: un `cycleId` ajeno **NO** hereda hechos ni completa su cadena (`SIGNAL is None`, `complete is False`, `diaDLink.linkable is False`, `executedVsDiaD.matches is None`);
8. que el día mueve notional bruto **> 0** (si no, la conciliación no diría nada) y que **NUNCA** publica al bridge LIVE.

Sin PostgreSQL real hace `pytest.skip`; con `AUTO_ESTUDIO_CHAIN_PG_REQUIRED=1` un skip silencioso es **FALLO**.

**Cableado CI:** en [`release-tag-ci.yml`](../../../../.github/workflows/release-tag-ci.yml) se añade `AUTO_ESTUDIO_CHAIN_PG_REQUIRED: '1'` y el test entra al paso DEDICADO `lifecycle-pg` (`Pytest AUTO universe coverage + DÍA-D trace + daily watch ESTUDIO + PAPER window + ESTUDIO chain (PG, fail if skipped)`) manteniendo el guard **anti-skip** (log no vacío + `grep` de `skipped` ⇒ `::error`).

---

## 6. UI: «mejor puntuada (Finalistas)» vs «ejecutada (identidad del ciclo)»

Rótulos canónicos nuevos en [`auto-operation-strategy.ts`](../../../../apps/web/src/features/auto/auto-operation-strategy.ts): `AUTO_OPERATION_STRATEGY_BEST_SCORED_LABEL = "Mejor puntuada (Finalistas)"` y `AUTO_OPERATION_STRATEGY_EXECUTED_IDENTITY_LABEL = "Ejecutada (identidad del ciclo)"`. Se aplican para que el usuario **nunca** confunda el `#1` (referencia) con lo ejecutado:

| Superficie | Cambio |
| --- | --- |
| [`strategy-monitor-panel.tsx`](../../../../apps/web/src/features/backtests/strategy-monitor-panel.tsx) | el `#1 {slot1Label} ★` pasa a `Mejor puntuada (Finalistas): #1 …` y la adopción se declara aparte como `Ejecutada (identidad del ciclo)` |
| [`instrument-strategy-top-panel.tsx`](../../../../apps/web/src/features/backtests/instrument-strategy-top-panel.tsx) | leyenda del slot `#1`: «`Mejor puntuada (Finalistas)`; la estrategia ejecutada se declara por ciclo (`Ejecutada (identidad del ciclo)`).» |
| [`mesa-candidates-panel.tsx`](../../../../apps/web/src/features/mesa/mesa-candidates-panel.tsx) | refuerza que el ranking es de **candidatas** (`#1 = Mejor puntuada (Finalistas)`) y que estar arriba —o ser `#1`— **no** implica compra |
| [`asesor-opiniones-panel.tsx`](../../../../apps/web/src/features/research/asesor-opiniones-panel.tsx) + [`operativa-dictamen.tsx`](../../../../apps/web/src/features/trading/operativa-dictamen.tsx) (señal diaria) | el `TOP ★n` se rotula como referencia **mejor puntuada**, con leyenda «…la ejecutada se declara por ciclo» |
| [`estudio-audit-panel.tsx`](../../../../apps/web/src/features/auto-monitor/estudio-audit-panel.tsx) | «Estrategia elegida» → **«Estrategia ejecutada (identidad del ciclo)»** |
| [`instrument-daily-opinion.ts`](../../../../packages/shared/src/instrument-daily-opinion.ts) (`@bolsa/shared`) | JSDoc de `strategyStars`/`topId`/`topVersion`: referencia «mejor puntuada», **no** la ejecutada (la identidad ejecutada se sella por ciclo) |

**No** se toca la lógica de decisión ni el contrato HTTP (los rótulos son copy + comentarios de tipo; `openapi.json`/`schema.d.ts` **no** se mueven). Tests de UI existentes **actualizados**: `auto-operation-strategy.test.ts` (+1 test de separación de rótulos) y `estudio-audit-panel.test.tsx` (+1 aserción del rótulo «Estrategia ejecutada (identidad del ciclo)»).

---

## 7. Verificación (local)

| Comprobación | Resultado |
| --- | --- |
| Lector durable (unitario puro) + gate PG de cadena (`test_auto_chain_durable_reader.py` + `test_auto_estudio_chain_evidence_pg.py`) | **14 passed** (13 unitarios + 1 PG real); PG en **9.11s** con `AUTO_ESTUDIO_CHAIN_PG_REQUIRED=1` |
| `pytest packages/py/application/tests` | **2744 passed** |
| `ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed** |
| `lint-imports --config packages/py/.importlinter` | **4 kept / 0 broken** |
| `mypy` (lista CI: domain/market/infrastructure/application/api, `--follow-imports=silent`) | **no issues found in 555 source files** |
| Censo de selección ([`test_selection.py --report`](../../../../scripts/ci/test_selection.py)) | **universo 623 / ejecutado 623 / NO ejecutado 0 / SIN DECLARAR 0 / obsoletas 0** |
| Guardián de bump ([`test_dia_d_bump_guard.py`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py)) | **1 passed** (`2.11.131-beta`) |
| `pnpm --filter @bolsa/web test` | **299 ficheros / 2195 passed** |
| `pnpm --filter @bolsa/web typecheck` | **OK** |
| `pnpm --filter @bolsa/web lint` | **0 errores / 23 warnings** (preexistentes) |
| `pnpm --filter @bolsa/web contract:check` | **OK** (`openapi.json`/`schema.d.ts` coinciden ⇒ `Δ contrato HTTP = 0`) |
| `Δ motor` / `Δ decisión` / `Δ contrato HTTP` | **0 / 0 / 0** |
| `alembic heads` (desde `packages/py/infrastructure`) | `053_dia_d_cycle_verifications` (**sin migración**) |

**Ficheros del sello:** nuevo `packages/py/application/src/bolsa_application/auto_chain_durable_reader.py`, nuevo `packages/py/application/tests/test_auto_chain_durable_reader.py`, nuevo `apps/api-python/scripts/v2_99_auto_estudio_chain_evidence.py`, nuevo `apps/api-python/tests/test_auto_estudio_chain_evidence_pg.py`; modificados `apps/api-python/scripts/v2_89_dia_d_auto_replay.py`, `apps/api-python/tests/test_dia_d_bump_guard.py` (+`v2_98`/`v2_99`), `.github/workflows/release-tag-ci.yml`, `apps/web/src/features/**` (5 superficies) + `packages/shared/src/instrument-daily-opinion.ts`, `package.json` + `meta.bump` de los CLIs `v2_87`/`v2_89`…`v2_99` y docs.

---

## 8. Límites declarados (sin fabricar) + falsabilidad

- **La cadena se LEE de hechos durables; no se fabrica.** Una etapa sin traza declara `None` + `measurement = UNKNOWN`; un valor sin ciclos declara `cycles = []` y `complete = False`. La foto TOP3 es **cross-asset del MOTOR** y **best-effort**: sin foto, la «mejor puntuada» es un **hueco declarado**; y **aunque haya foto**, esa foto **no** sella identidad de estrategia, así que `bestScoredPresetKey`/`presetMatch` son `None` (nunca se rellenan con el preset de la ejecutada).
- **La identidad ejecutada no se infiere.** El contraste `executedVsBest` es `True`/`False`/`None` y **nunca** fabrica un `False` sin término de comparación. El valor se resuelve con el resolutor canónico reutilizado: identidad **única** o **AMBIGUA** declarada (jamás una «ganadora» elegida por conveniencia).
- **El eslabón DÍA-D no se finge.** `executedVsDiaD.matches` exige **ambas** fuentes durables; sin verificación, `None` + `UNKNOWN` y `diaDLink.linkable = False` (el borrador canónico no se rellena).
- **NO certifica la operación real.** El gate corre sobre **ESTUDIO sembrado** en PG (cadena funcional), no sobre mercado real; la **ventana PAPER** y la **rentabilidad** siguen **NO MEDIDAS**.
- **`Δ contrato HTTP = 0`:** el bloque aditivo opcional en `GET /auto/estudio-audit` **no** se aplicó; el instrumento vive en el CLI read-only.

**Falsabilidad.**
- Si una etapa dejara de tener fuente durable, `test_auto_estudio_chain_evidence_pg.py` **rompe** (`steps[etapa] != 1`) y el CLI declararía el hueco.
- Si la identidad ejecutada se inventara (p. ej. cayendo al `#1`), la aserción de `rank` durable + `preset` honesto **rompe**.
- Si el lector de cadena dejara de reutilizar el resolutor canónico y «eligiera ganadora» con identidades dispares, la aserción de `presetKeyAmbiguous`/`presetKey is None` **rompe**.
- Si el preset de la mejor puntuada se rellenara con el de la ejecutada, las aserciones `bestScoredPresetKey is None` / `presetMatch is None` **rompen**.
- Si el eslabón DÍA-D fabricara veredicto con una sola parte, la aserción `matches is None` + `linkable is (diaD is not None)` **rompe**.
- Si `CYCLE_CLOSED.pnl != SETTLEMENT.pnl` o la suma no cuadrara con el libro aplicado, la conciliación **rompe**.
- Si el guard anti-skip no viera el log o detectara `skipped`, el paso de `lifecycle-pg` **falla** la certificación.
- Si `meta.bump` de cualquier CLI se desincronizara de `package.json`, el guardián **rompe**.

---

## 9. `Release tag CI` del sello — **VERDE**

**Tag** `v2.88.131-beta` (**lightweight**, unsigned) ⇒ apunta **directamente** al commit `6fec78b1611f8eb4024e7070cee960d3aec73b8e` (**no** hay objeto de tag). **Base:** `v2.88.130-beta`.

**`Release tag CI`:** [run **`38594446027`**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38594446027) — **`SUCCESS`** en **~13 min** (`2026-10-14T16:01:11Z` → `16:14:33Z`), **todos los jobs verdes**:

| Job | Conclusión |
| --- | --- |
| `decision-spine` | success |
| `security (gitleaks)` | success |
| `playwright (mock E2E)` | success |
| `shared (build/typecheck/test)` | success |
| `playwright (integrated AUTO S5)` | success |
| `python (ruff/imports/mypy/pytest offline)` | success |
| `dr-verify (battery DB_DR / TCP CI)` | success |
| `lifecycle-pg (Alembic + auth + golden restart)` | success |
| `a7-gate (A7 C3 chaos live_a7 · dedicated real-PG)` | success |
| `frontend (typecheck/lint/test/build + contract:check)` | success |
| `replay-repro (regenera el artefacto del sello desde el fixture)` | success |
| `certify (aggregate + artifact)` | success |
| `playwright (integrated E2E, opt-in)` | **skipped** (opt-in por diseño) |

**Lo decisivo:** el job `lifecycle-pg` —donde entra el **gate de cadena ESTUDIO** (`AUTO_ESTUDIO_CHAIN_PG_REQUIRED=1`, paso DEDICADO con guard anti-skip)— queda **`success`**; `replay-repro` **REPRODUCIDO** ⇒ `Δ decisión = 0` confirmado por CI; `frontend` verde ⇒ `contract:check` OK (`Δ contrato HTTP = 0`); `certify` agrega y **certifica** con todos los obligatorios verdes.

**Desviación honesta declarada.** A diferencia de los sellos previos (tag **anotado**), `v2.88.131-beta` es **lightweight**: el re-tag a anotado fue **bloqueado por el auto-review** al tratarse de reescribir un tag **ya publicado**. Funcionalmente es **idéntico** (mismo commit; `Release tag CI` dispara igual con `push: tags: v*`), y el run citado **es el real** de este tag.
