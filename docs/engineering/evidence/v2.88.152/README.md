# Evidencia `v2.88.152-beta` — evidencia por valor ESTUDIO y DÍA-D del valor bajo demanda

> **Bump:** `2.11.151-beta` → **`2.11.152-beta`** (`package.json` + `meta.bump` de los **13**
> CLIs; guardián
> [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py)
> **2 passed**). Tag **unsigned**.
>
> **Cambio:** **`Δ motor = 0`** · **`Δ decisión = 0`** ·
> **contrato HTTP ampliado ADITIVO** (dos endpoints read-only nuevos y un `kind` de job;
> `openapi.json`/`schema.d.ts` regenerados, `contract:check` **OK**) · **SIN migración**
> (head `056_auto_ops_jobs`). No se toca el motor de decisión, umbrales, pesos A/B, `TOP_N`,
> régimen, sizing, salidas ni esquema.

## 1. El hueco

El parte diario por valor (`/auto-monitor?mode=daily`) declaraba señal, decisión y validación,
pero **no demostraba la cadena**: para un valor concreto no se podía ver

- qué **estrategia ejecutada** selló el ciclo (y no la que el parte *declara*),
- con qué **indicadores** y **por qué** esa y no otra,
- qué **señal/vela** la originó,
- qué **entrada y salida** tenía según el `TradePlan`,
- qué pasó de verdad en las **nueve etapas** durables (`SIGNAL → … → CYCLE_CLOSED`),
- qué evidencia **DÍA-D** existe y si es suficiente.

Y no había forma de **pedir** la verificación DÍA-D de ese valor desde la ficha: el botón
existente lanzaba el replay del **día completo** (watch completo), no el del valor.

El hueco no era de motor: era de **superficie de producto**. La cadena ya se leía y el replay
ya existía; faltaba exponerlos **por valor**.

## 2. Qué cambió (y qué no)

| Pieza | Cambio |
| --- | --- |
| [`auto_chain_durable_reader.py`](../../../../packages/py/application/src/bolsa_application/auto_chain_durable_reader.py) | `_cycle_view` extrae `entryDay`/`exitDay` (aditivo) para poder anclar el DÍA-D del valor. |
| [`auto_estudio_chain.py`](../../../../apps/api-python/src/bolsa_api/api/v1/routes/auto_estudio_chain.py) | **NUEVO** `GET /api/auto/estudio-chain`: adaptador HTTP **read-only** del lector durable. `limit ≤ 200`, acotado por cuenta, error **declarado** (nunca lista vacía). |
| [`auto_ops_job.py`](../../../../packages/py/domain/src/bolsa_domain/entities/auto_ops_job.py) · [`auto_ops_jobs.py`](../../../../packages/py/application/src/bolsa_application/auto_ops_jobs.py) | `JOB_KIND_DIA_D_VALUE_REPLAY = "dia_d_value_replay"`; `payload.symbol` **obligatorio**, normalizado a mayúsculas; fecha futura rechazada. |
| [`dia_d_artifacts.py`](../../../../packages/py/application/src/bolsa_application/dia_d_artifacts.py) | `values/` + `symbol_segment(symbol)`: el artefacto del valor es **otro fichero** y no puede pisar el del día. |
| [`auto_ops_dia_d.py`](../../../../apps/api-python/src/bolsa_api/background/auto_ops_dia_d.py) | El handler acepta `symbol`, pasa `--watch <SYMBOL>` y `--out .../values/<SYMBOL>/dia-d-auto-<D>.json`, y exige **`meta.watch == [symbol]`**. |
| [`v2_89_dia_d_auto_replay.py`](../../../../apps/api-python/scripts/v2_89_dia_d_auto_replay.py) | `meta.watch` (lista explícita) — campo **aditivo** que no altera la decisión. |
| [`auto_dia_d.py`](../../../../apps/api-python/src/bolsa_api/api/v1/routes/auto_dia_d.py) | **NUEVO** `GET /api/auto/dia-d-replay/{day}/value/{symbol}`: `available=false` si no hay artefacto; misma política de cuenta. |
| [`estudio-daily-ops.ts`](../../../../packages/shared/src/estudio-daily-ops.ts) · [`api.ts`](../../../../apps/web/src/lib/api.ts) | Tipos del `kind`, del artefacto de cadena y del DÍA-D por valor + tres métodos de cliente. |
| [`use-estudio-chain.ts`](../../../../apps/web/src/features/auto-monitor/use-estudio-chain.ts) · [`use-dia-d-value-replay.ts`](../../../../apps/web/src/features/auto-monitor/use-dia-d-value-replay.ts) · [`estudio-chain-evidence.tsx`](../../../../apps/web/src/features/auto-monitor/estudio-chain-evidence.tsx) | **NUEVOS**: una query de cadena por informe (indexada por `instrumentId`), hook de verificación por `(cuenta, día, símbolo)` y sección **«5 · Cadena y resultado (evidencia durable)»**. |
| [`estudio-daily-ops-panel.tsx`](../../../../apps/web/src/features/auto-monitor/estudio-daily-ops-panel.tsx) | Integra la sección en cada ficha y eleva el error de la cadena al primer nivel (el de cada ficha queda `inline`). |

**No** se toca: `auto_v2_entry`, `classify_market_regime`,
`regime_allows_entry_for`, `replay_oos` (contenido), `TOP_N`, umbrales, pesos A/B, gobernador,
sizing, salidas ni esquema. El único cambio fuera de read-model/UI/cola es el `meta.bump` de
los 13 CLIs (etiqueta) y el `meta.watch` (campo aditivo del artefacto DÍA-D).

## 3. Reglas duras de la superficie nueva

1. **Una sola verdad.** La cadena se lee con `read_estudio_chain_evidence(...)` y se compone
   con `build_chain_evidence_artifact(...)`; **no** hay un segundo lector ni un segundo P&L.
2. **Hueco ≠ 0.** Una etapa sin traza durable viaja `None`; un valor sin ciclos declara
   `measured = false`; un fallo de lectura es **error declarado**.
3. **Fail-closed por cuenta.** Sin cuenta visible no se lee nada (`no_account_scope`); otra
   cuenta no ve el artefacto del valor.
4. **Aislamiento de artefactos.** La verificación del valor escribe
   `values/<SYMBOL>/dia-d-auto-<D>.json`; el artefacto del día **no se toca**.
5. **Procedencia verificada.** Un job sólo se da por bueno con `exit 0` + artefacto + `day` +
   `meta.account` + **`meta.watch == [symbol]`**.
6. **Sin promoción.** `CONFIRMED` **no se emite**; el veredicto global sigue
   `NO CONFIRMADO` y la ventana PAPER sigue `INCONCLUSIVE`.
7. **Atribución.** El histórico del valor **no** se atribuye a la señal de hoy salvo
   coincidencia exacta de `planId`/`signalId` (`AUDIT_NOT_ATTRIBUTED_LABEL`).

## 4. Verificación (medida)

| Comprobación | Resultado |
| --- | --- |
| `pytest apps/api-python/tests packages/py/application/tests -q` | **4094 passed / 1 failed** (`test_c3b_crash_after_resolve_put_no_double_on_relaunch`, caos **conocido**: un servidor dev vivo compite por el outbox) — **en aislamiento 1 passed** |
| `pytest` focalizado nuevo (`test_auto_estudio_chain_route`, `test_auto_dia_d_route`, `test_auto_ops_dia_d`, `test_auto_ops_job_worker`, `test_auto_ops_jobs`, `test_auto_chain_durable_reader`, `test_dia_d_bump_guard`) | **78 passed** (ruta de cadena: **8 passed**) |
| `vitest run src/features/auto-monitor` | **21 ficheros · 166 tests passed** |
| `vitest run` (suite web completa) | **312/313 ficheros · 2310 passed / 1 failed** (`auto-monitor.test.tsx` «compone header, notas y timeline», `Test timed out in 5000ms` con la suite en paralelo; **en aislamiento 11 passed**) |
| `use-dia-d-value-replay` + `estudio-daily-ops-panel` | **5 + 18 = 23 passed** |
| `playwright (mock E2E)` local | **`gp-e2e-v290` 5 passed · `gp-e2e-s5-auto-dia-d-bridge` 3 passed** |
| `typecheck` (monorepo) | **OK** (`4 successful / 4`) |
| `lint` (monorepo) | **0 errores**, 23 avisos preexistentes |
| `pnpm lint:py` | **`All checks passed!`** (15 `I001` corregidos con `lint:py:fix`) |
| `pnpm imports:py` | **`Contracts: 4 kept, 0 broken.`** |
| `pnpm types:py` | **`Success: no issues found in 567 source files`** |
| `contract:check` | **OK** (contrato regenerado; solo aditivo) |
| `pnpm window:test` | **50 passed** |
| `test_dia_d_bump_guard` | **2 passed** (`2.11.152-beta`) |

**Corrección tras el primer `Release tag CI`.** `playwright (mock E2E)` falló porque la suite
mock no servía `GET /api/auto/estudio-chain` y el fallback `{ data: [] }` llegaba al panel como
si fuera la respuesta: `chain.notes.join(...)` tumbaba la ficha entera. Se corrige en dos
capas, sin tocar el contrato: (1) el panel **normaliza** la respuesta
(`normalizeEstudioChain`: un payload sin forma es hueco declarado, no una cadena vacía) y (2)
el mock E2E sirve la cadena durable y el artefacto `values/<SÍMBOLO>` con la misma forma que la
API. Guardián nuevo: «un payload sin forma no tumba la ficha: se declara el hueco».

**E2E integrado.** `gp-v288-s5` gana **S5-08** (evidencia por valor + verificación DÍA-D del
valor + no herencia del artefacto del día) y **S5-06** verifica la sección 5 en la UI diaria.
**No ejecutado en local**: el spec integrado requiere API Python + PostgreSQL + worker +
barras sembradas y en esta máquina no había stack escuchando (`:8000`/`:3001`/`:5432`
cerrados). Un `skipped` **no** cuenta como prueba: se declara como hueco de verificación local
y lo cubre el job opt-in del CI.

## 5. Límites declarados (sin fabricar)

- **AUTO sigue OFF**; no se enciende la cadencia diaria ni el orquestador.
- La prueba demuestra **instrumentación y trazabilidad**, **no** rentabilidad: sin ciclos
  PAPER reales la evidencia por valor sigue en hueco y la ventana sigue `INCONCLUSIVE`.
- El DÍA-D del valor es un **sandbox con watch de 1 símbolo**, no una ejecución real ni una
  orden.
- La comparación estrategia-ejecutada vs mejor-puntuada queda en **hueco** cuando el motor no
  sella la identidad de la mejor puntuada; **no se rellena**.
- Un job por valor activo por `(cuenta, día)` (índice único parcial): el resto se **serializa**
  y la UI lo declara («hay otra verificación en curso»), en vez de devolver un job ajeno.
- Los dos fallos de la suite completa son **flaky declarados** (caos por servidor dev vivo y
  `testTimeout` de 5 s con la suite en paralelo) y **pasan en aislamiento**; no se tocó
  `testTimeout`/`retries` en este sello.
- Operativa **100 % SIM** (PAPER / dinero virtual); no se envían órdenes reales a ningún bróker.
- Tag **unsigned**.

## 6. Freeze y ventana PAPER

Este sello mueve `apps` y `packages` ⇒ el pin PAPER queda `TREE_MOVED` por diseño y se
**re-ancla** al árbol del sello (`pnpm window:pin --write`) para que el run de las 18:00 no
aborte fail-closed. El re-anclaje **no** edita código: solo `commit`/`appsHash`/`packagesHash`
en `scripts/`. La **ventana PAPER** no se re-mide y sigue necesitando OPERACIÓN (no software).

## 7. Publicación (POST-TAG)

`Release tag CI` [run **`39303586042`**](https://github.com/jvelasca/Bolsa_V1/actions/runs/39303586042) ⇒
**`conclusion: success`**: 13 jobs `success` + `certify` `success`
(`playwright (integrated E2E, opt-in)` `skipped`, declarado). `playwright (mock E2E)` **verde** y
`replay-repro` **`REPRODUCIDO`** («mismo CONTENIDO; el sello está en CRLF y este fichero en LF»)
⇒ **`Δ decisión = 0`**. `pnpm window:freeze` **OK** sobre el árbol del sello (`4198a3a8`).

El **primer** intento del tag ([`39300632203`](https://github.com/jvelasca/Bolsa_V1/actions/runs/39300632203))
salió **rojo sólo** en `playwright (mock E2E)`: la suite mock no servía
`GET /api/auto/estudio-chain` y el fallback `{ data: [] }` llegaba al panel como si fuera la
respuesta, rompiendo `chain.notes.join(...)`. Corrección en dos capas, sin tocar el contrato:
el panel **normaliza** la respuesta (`normalizeEstudioChain`) y el mock E2E sirve la cadena y
el artefacto `values/<SÍMBOLO>` con la forma de la API. El tag se **movió** al commit de
corrección y el reenvío salió verde: la ventana PAPER sigue **`INCONCLUSIVE`** (es OPERACIÓN,
no software).
