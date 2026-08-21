# PLAN PROFUNDO — Refactorización, corrección y mejora post-v1.3.0 (2026-08-21)

> **SUPERSEDIDO (2026-08-21) por [`plan-r12-auditoria-ux-2026-08-21.md`](./plan-r12-auditoria-ux-2026-08-21.md).** Relevo UNO (`f7a4ab0`) y DOS (`f7a86cc`) están ejecutados; la Fase 6 higiene se absorbe en R-12 A5/A6. No abrir fases de este plan; usar R-12.

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (`Product / Ops`).
> **Ancla obligatoria:** leer PRIMERO `docs/engineering/estado-verificado-auditoria-vs-main-2026-08-21.md` (§0 firma de estado + §3 gaps reales) y `docs/engineering/backlog-trabajo-2026-08-20.md` §0/§1 · `docs/engineering/PROJECT_STATE.md` · premisas E1–E9 (`docs/PROJECT_PREMISES.md`).
> **Estado de partida (verificado):** `main` GitHub = local = **`49ecbcd`** (release **`v1.3.0`**), árbol limpio, sin commits sin empujar.
> **AsOf:** 2026-08-21 · **Estado del plan:** ✅ **APROBADO por el propietario (2026-08-21)**. **RELEVO UNO (Fases 1–3) EJECUTADO:** F1 ✅ (invariante A en verify + limpieza 15 cuentas sim huérfanas → EXIT 0) · F2 ✅ (5 tests de concurrencia custodia PG real, 5 passed) · F3 ⏳ APLAZADA (contrato 409 queda en Opción A, decisión + ejecución pendientes). **RELEVO DOS (Fases 4–5 + R000) EJECUTADO (2026-08-21):** F4 ✅ (crash-consistency chaos, 3 tests) · F5 ✅ (concurrencia masiva chaos, 5 tests) · **R000** ✅ (tests `m7*`/`m2*` limpian cuentas + instrumentos → EXIT 0 estable). Se descubre y documenta un **hallazgo de diseño** en `ExecuteTrade` (invariante B estricta no garantizable bajo concurrencia) → deuda propuesta para fase propia (no auto-abierta).

---

## 0. Resumen ejecutivo y advertencia de contexto

La **auditoría externa del 2026-08-21** que motivó este encargo evaluó el estado **`75e8c23`** (14 commits por detrás de `main`). Esos 14 commits (R-11 C1–C6 + D1 + D2 + release `v1.3.0`) **ya cierran la práctica totalidad de los P1/P2 que esa auditoría pide**. Por tanto, **este plan NO repite trabajo ya hecho**: está construido exclusivamente sobre los **gaps reales que quedan abiertos en `main` (49ecbcd)**, verificados con subagentes y evidencia file:line (ver [estado-verificado](./estado-verificado-auditoria-vs-main-2026-08-21.md) §2/§3).

Los gaps reales son de dos naturalezas:

- **A) Cierre/retoque de verificación y contrato** (bajo riesgo, alto valor): invariante A + invariante B en el verificador global; tests de concurrencia de custodia que faltan; contrato `409` fuera de OpenAPI.
- **B) Chaos / verificación bajo estrés** (la "siguiente frontera" que la auditoría recomienda explícitamente): atomicidad bajo kill de procesos, cientos de operaciones concurrentes, Redis/Postgres reiniciándose, doble verificación matemática (Σ ledger = cash + chain `balance_after`).
- **C) Deuda arquitectónica de alcance amplio** (V2, por decisión, NO auto-abrir): auth global, legacy portfolio model, scheduler-vs-worker, `pending-delete` purga, unificación Research→Radar.

> **Principio de minimización del riesgo:** las premisas E1–E6 del proyecto SE MANTIENEN ÍNTEGRAS. Esto significa: nada se abre sin aprobación, una fase = un subagente acotado, coordinador re-verifica, aprobación por commit, push a `main` con rama protegida, control de saturación (~3 subagentes máx. en paralelo con alcances disjuntos), y relevos de chat documentados con firma de estado.

---

## 1. Principios rectores (cómo se ejecutará el plan) — REFORZADOS

1. **Read-first obligatorio por fase:** todo subagente lee `estado-verificado-*` §0 + backlog §0/§1 + premisas E1–E9 + `PROJECT_STATE` antes de tocar nada. Si el repo no coincide → PARAR.
2. **Una fase = un subagente acotado** con brief que inyecte: contexto, archivos EXACTOS a tocar, qué **NO** tocar, mapa de consumidores ya verificado, batería esperada, **prohibido commit/push**. Máx. ~3 en paralelo con alcances disjuntos.
3. **El coordinador nunca confía en el reporte del subagente:** contrasta cada diff/file:line y corre la batería él mismo (E3/E4).
4. **Aprobación del propietario por commit** (E4). Rama `main` protegida, push con aprobación nativa.
5. **Batería mínima obligatoria por fase** (§5 del [estado-verificado](./estado-verificado-auditoria-vs-main-2026-08-21.md)).
6. **Anti-alucinación / anti-pérdida / control de saturación:** si un chat se satura → cerrar hilo y abrir otro pegando el texto de relevo (este doc + bloque de estado verificado + firma HEAD/rama/árbol/tags).

---

## 2. Matriz de priorización / riesgo (por dinero y verdad de resultados)

| Prioridad | Fase                                                                 | Qué resuelve                                                                                                                                                                         | Riesgo si NO se hace                                                                                           | Alcance    | Puesta en el plan                                                                                                               |
| --------- | -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------- |
| P-A1      | **Fase 1 — Invariante matemática completa en el verificador global** | Añadir invariante **A** (Σ ledger.amount == cash) a `verify_ledger_balance_chain.py` (ya valida la B). Un verificador con **dos** invariantes independientes que la auditoría exige. | No poder demostrar formalmente "Σ ledger = cash" como invariante de verificación global; solo vivía en pytest. | Bajo       | ✅ **CERRADA (2026-08-21)** ver §3.1                                                                                            |
| P-A2      | **Fase 2 — Tests de concurrencia de custodia faltantes**             | `2 custody jobs simultáneos` + `Redis caído + 2 workers` + `transición PG real 2026→2027`.                                                                                           | El nuevo punto de entrada real (scheduler) sin prueba de doble-cobro bajo estrés.                              | Bajo-medio | ✅ **CERRADA (2026-08-21)** ver §3.2                                                                                            |
| P-A3      | **Fase 3 — Contrato: decisión del `409` en OpenAPI**                 | Decidir si exponer el `409 IDEMPOTENCY_KEY_REUSED` en openapi.json/schema.d.ts (hoy solo runtime).                                                                                   | Frontend no tiene esa respuesta tipada; contrato incompleto. Requiere DECISIÓN (no auto-cerrar).               | Bajo       | ⏳ **APLAZADA (2026-08-21)** — se mantiene Opción A; B1 recomendada pero requiere `contract:gen`/fase pactada. Ver §3.3         |
| P-B1      | **Fase 4 — Crash-consistency (chaos): kill entre cash y ledger**     | Verificar atomicidad REAL: `BEGIN → UPDATE cash → KILL` → ROLLBACK, cash intacto, sin ledger.                                                                                        | No hay ninguna prueba de atomicidad real bajo kill. Es la "prueba fundamental" de la auditoría.                | Medio      | ✅ **CERRADA (2026-08-21)** ver §3.4 · `tests/chaos/test_crash_consistency.py` (3 tests, PG real aislado)                       |
| P-B2      | **Fase 5 — Concurrencia masiva / carga (chaos)**                     | cientos de depósitos/retiros/BUY/SELL simultáneos + verificación Σ=chain=cash tras cada escenario.                                                                                   | Comportamiento bajo estrés no validado (auditoría recomienda como siguiente fase).                             | Medio      | ✅ **CERRADA (2026-08-21)** ver §3.5 · `tests/chaos/test_load_concurrency_flow.py` (5 tests). Destapa **deuda ExecuteTrade/B**. |
| P-R0      | **R000 (deuda) — tests `m7*`/`m2*` limpian su DB**                   | Los tests crean cuentas `simulated` e instrumentos sin limpiar → residuos que rompen el EXIT 0 del verify en DB compartida.                                                          | ExEC 0 inestable del verify; contaminación de la DB de desarrollo.                                             | Bajo       | ✅ **CERRADA (2026-08-21)** ver §3.6 · `m7*`+`m2*` añaden `_cleanup_account`/`_cleanup_instrument` → delta 0.                   |
| P-C1      | **Fase 6 — Limpieza/hygiene transversal segura**                     | Purga de doc obsoleto + mypy restante de otras capas + docstrings + barrido pending-delete real (inventario → writers → readers → test de ausencia).                                 | Deuda de higiene crece; `pending-delete` riesgo alto sin plan de purga.                                        | Medio      | ⚠️ (bajo E8, ver §3.6)                                                                                                          |
| P-C2      | **Deuda V2 (no ahora, por decisión)**                                | auth global · legacy portfolio model · scheduler-vs-worker (R-8C.2) · unificación Research→Radar · semver packages                                                                   | —                                                                                                              | Amplio     | ⏳ (decisión, ver §4)                                                                                                           |

---

## 3. Desglose por fase

> Cada fase se abre SOLO con aprobación explícita. Se ejecuta en un subagente acotado + verificación del coordinador + batería + aprobación por commit + push a `main`.

### 3.1 Fase 1 — Invariante A + B en el verificador global de ledger (bajo riesgo)

**Objetivo:** que `scripts/verify/verify_ledger_balance_chain.py` valide, por cuenta, **ambas** invariantes:

- **A:** `Σ ledger.amount == cash actual` (comparación con el `cash` de la cartera).
- **B:** `balance_after[i] == balance_after[i-1] + amount[i]` (ya implementada, `verify_ledger_balance_chain.py:72-79`).

**Evidencia verificada:** hoy `verify_ledger_balance_chain.py` solo valida la **B** (`:6-8`, `_validate_sequential` `:60-79`). La **A** (`Σ==cash`) solo vive en pytest (`ledger_repository.sum_cash_amounts` `:263-282` + `test_m2_ledger_cash_reconciliation.py:133-147`, offline) y en `test_concurrency_scenarios.py`. Unificarla en el script de verificación global convierte a ese script en el verificador "canónico" de ambas invariantes y alinea con la auditoría (que pide "dos pruebas independientes").

**Archivos a tocar (acotado):** `scripts/verify/verify_ledger_balance_chain.py` (+ opcional helper para leer el `cash` actual por cartera). **No tocar** producción ni repos.

**Batería esperada (subagente → coordinador):** ruff 0 · mypy del script 0 · ejecutar el script contra la DB real → **EXIT 0** · y correr una mutación negativa para confirmar que detecta una A rota (test de la capacidad de detección, no solo del happy path).

**Riesgo:** bajo (solo script de verificación, sin producción). Deja un entregable de demostración del patrón "fase acotada + aprobación".

### 3.2 Fase 2 — Tests de concurrencia de custodia que faltan (bajo-medio)

**Objetivo:** cerrar los 3 huecos de verificación detectados por el subagente (ver [estado-verificado](./estado-verificado-auditoria-vs-main-2026-08-21.md) §3.2):

1. **2 `RunCustodyJob`/`ApplyCustodyFees` concurrentes** (asyncio.gather, PG real) → exactamente 1 cargo ledger, 1 obligation APPLIED, cash − fee; nunca cash − 2·fee. El test de concurrencia actual (`test_concurrency_scenarios.py:555`) acopla custodia a un trade y no fuerza el timing; los de custodia (`test_m7_*`, `test_custody_idempotency.py`) son secuenciales o con fakes.
2. **Redis caído + 2 workers** → exactly one charge. El fallback a memoria existe (`risk_runtime.py:211-217`), pero no hay test de regresión.
3. **Transición de periodo PG real** "PENDING 2026 → 2027 con cash insuficiente" → ni la antigua ni la nueva obligación desaparecen; ninguna fila se pierde. Hoy `test_custody_obligation_multi_period.py` lo cubre con **fakes** (`_FakeObligationRepo`), no con PG real + workers.

**Archivos a tocar (acotado):** nuevos tests en `packages/py/infrastructure/tests/` y/o `packages/py/application/tests/` (PG real). **No tocar** producción ni repos.

**Batería esperada:** pytest de la zona con PG real · ruff 0 · mypy 0 · `verify_ledger_balance_chain.py` EXIT 0 tras cada escenario (Σ==cash == chain). Riesgo bajo (tests-only).

### 3.3 Fase 3 — Contrato: DECISIÓN del `409` en OpenAPI (requiere decisión, no auto-cerrar)

**Estado verificado:** el `409 IDEMPOTENCY_KEY_REUSED` existe solo en runtime (`apps/api-python/src/bolsa_api/main.py:174-181` → `JSONResponse(409, ...)`; excepción `errors.py:28-44`). `openapi.json`/`schema.d.ts` NO lo declaran (0 hits de `409`/`IDEMPOTENCY`); deposit/withdraw solo declaran `201`/`422`. `contract:check` (`sync-contract.mjs`) pasa verde porque solo compara re-regen vs commit, no valida códigos de estado.

**Decisión que debe tomar el propietario (no cerrable por el agente):** Opción A (mantener 409 solo runtime, como R-11 C4) vs Opción B (exponer `409` como response en OpenAPI/schema.d.ts — requiere `contract:gen`/regen, que el protocolo prohíbe sin fase pactada). Si se aprueba B, se ejecuta como fase de contrato propia con su regen acotada y reverificación de call-sites FE (el FE usa `fetch` en crudo, así que tipar el 409 no debería romper call-sites, pero se verifica).

**Riesgo:** bajo. Es una **decisión**, no una corrección automática. Si se elige B, el beneficio es que el frontend pueda manejar el `409` de forma tipada.

### 3.4 Fase 4 — Chaos: crash-consistency (kill entre cash y ledger) [REAL, prioritario]

**Objetivo (la prueba "fundamental" de la auditoría):** demostrar atomicidad REAL bajo kill de proceso:

- `cash = 10 000` → `BUY` → actualiza cash a `9 000` → **KILL del proceso** antes de insertar ledger → debe quedar **ROLLBACK** (cash = 10 000, ledger sin fila).
- Análogo para: kill tras `UPDATE cash` antes de `INSERT ledger`, y kill tras `INSERT ledger` pero antes de commit (ningún estado parcial persistido).

**Implementación propuesta:** un **script de chaos test** (`scripts/chaos/` o `packages/py/infrastructure/tests/chaos/`) que:

1. Abre una transacción, realiza la mutación de cash, y lanza `SIGKILL`/cierre brusco de la conexión (simulando kill de proceso) **antes** del commit.
2. Reabre conexión y verifica que cash volvió al valor inicial y no hay fila ledger parcial.
3. Reporta PASS/FAIL con invariantes A y B verificadas.

**Riesgo:** medio (requiere manipular conexiones reales y matar/quebrar sesiones; debe ejecutarse contra una **DB de prueba aislada / docker**, NUNCA contra dev real). **Batería: ejecutar contra contenedor PostgreSQL de tests, no contra la DB de desarrollo.**

> ✅ **EJECUTADA (2026-08-21, Relevo DOS):** `packages/py/infrastructure/tests/chaos/test_crash_consistency.py`. Implementa los 3 kill points (kill tras deducir cash sin ledger; kill tras insertar ledger sin commit; control con commit) usando `rollback()`/abandono de transacción como equivalente al kill O/S (documentado en docstring). Ejecuta contra la DB aislada `bolsa_v1_chaos` (docker, migrada a `006`). Battery real: ruff 0 · mypy 0 · **3 passed** en 0.8s · sin residuos.

### 3.5 Fase 5 — Chaos: concurrencia masiva / carga (estrés) [REAL]

**Objetivo:** validar comportamiento bajo estrés, tal como recomienda la auditoría:

- 500 depósitos simultáneos / 500 retiradas simultáneas / 500 BUY y 500 SELL sobre la misma posición / BUY+SELL simultáneos / custodia+BUY simultáneos, con reintentos HTTP.
- Tras cada escenario verificar: `cash >= 0`, **Σ ledger.amount == cash**, y **chain `balance_after` válida**.

**Implementación propuesta:** nuevo `scripts/chaos/` (o ampliar `test_concurrency_scenarios.py`) con PG real, sesiones independientes y `asyncio.gather`. Apoyarse en las invariantes A y B ya unificadas en Fase 1.

**Riesgo:** medio (alta concurrencia). Ejecutar contra **DB de pruebas aislada/docker**. Battería: pytest PG real + verify EXIT 0.

> ✅ **EJECUTADA (2026-08-21, Relevo DOS):** `packages/py/infrastructure/tests/chaos/test_load_concurrency_flow.py`. Scenarios: 500 depósitos, 500 retiros (guard no-negatividad), 500 BUY + 500 SELL sobre una posición, BUY+SELL y custodia+BUY simultáneos. Tras cada uno se verifica `cash ≥ 0`, `Σ ledger == Σ cash` (inv. A) y chain (inv. B **en la variante robusta-vs-concurrencia**, NO la estricta — ver hallazgo abajo). Executado contra `bolsa_v1_chaos`. Battery real: ruff 0 · mypy 0 · **5 passed** en ~38s · sin residuos (cleanup garantizado verificado).

> **🔴 HALLAZGO DE DISEÑO (deuda No-auto-abierta):** bajo `ExecuteTrade` CONCURRENTE, **la invariante B estricta (`balance_after[n] == balance_after[n-1] + amount[n]`) NO es una postcondición** del código de producción: `ExecuteTrade.execute` (`accounts.py:884-888`) lee `cash_before` con `get_summary` **PRE-lock** antes de `execute_trade` (que sí usa `with_for_update`). Bajo varias trades concurrentes en la misma cuenta, cada escritura de `balance_after` usa un `cash_before` desfasado → la cadena estricta descuadra en O(N) **sin** violar la invariante financiera M-2 `Σ ledger == Σ cash`. Por eso F5 verifica la variante robusta (Σ exacta + ningún `balance_after` negativo) para trades, y la cadena estricta solo para flujos que escriben desde cash bajo lock (`add_cash`/`deduct_cash`). **No se arregló producción** (requiere fase propia + aprobación): propuesta de mejora = fijar `balance_after` al cash **post-lock** dentro de `execute_trade`. Añadir a la deuda V2.

### 3.6 Fase 6 — Higiene / limpieza transversal segura (bajo E8) [OPCIONAL, media]

**Objetivo:** reducir deuda de calidad SIN tocar ítems de riesgo alto (los V2 en §4):

- **R000 (descubierta en Relevo UNO) — tests que no limpian la DB compartida:** `test_m7_custody_single_charge_f3_guard.py` y `test_m2_ledger_cash_reconciliation.py` no llamaban a `close_account`/`delete_simulated_account` (y m2 no borraba sus instrumentos), por lo que cada ejecución sobre la DB compartida regeneraba cuentas `simulated` e instrumentos huérfanos que hacían que `verify_ledger_balance_chain.py` (con invariante A) no diera EXIT 0 estable. **✅ CORREGIDA (2026-08-21, Relevo DOS):** ambos ficheros añaden `_cleanup_account` (close+delete+commit) y `_cleanup_instrument` (los 2 tests de m2 que crean instrumento) → **delta 0** de residuos nuevos; el verify da **EXIT 0** estable contra dev. **Pendiente menor (higiene, requiere aprobación):** limpiar los residuos **históricos** ya existentes en la DB dev (8 cuentas `m7-win-*` y ~9 instrumentos `M2 *`) que no rompen el verify pero ensucian la BD compartida.
- **Docstrings:** aplicar forward-only/política (`code-documentation-standard`) + medir con `scripts/research/docstring_coverage_report.py`.
- **mypy restante** de otras capas (si el gate ya incluye `application`, verificar scope completo `analytics`/`market`/`infrastructure`).
- **`pending-delete` real, SOLO bajo el patrón seguro:** inventario de readers → localizar writers → comprobar referencias runtime → **no borrar todavía** salvo aprobación, y si se purga: eliminar writers, migrar readers necesarios, borrar storage, test de ausencia (E8: 0 imports, sin localStorage, battery verde). **NO se hace a ciegas; solo con aprobación por commit.**
- **Purga/archivado de doc antiguo obsoleto** que ya no refleja el estado real (migrar/marcar, nunca perder evidencia — E8).

**Riesgo:** medio; se ejecuta con el criterio E8 estricto y aprobación por commit. Dividido en subfases de alcance disjunto según necesidad.

---

## 4. Deuda arquitectónica diferida (V2) — NO auto-abrir, requiere decisión por fase

Estas son las que la auditoría y las premisas clasifican como "mejoras de arquitectura, no correcciones urgentes" y suelen requerir ADR + diseño + decisión del propietario:

| Ítem                                                                          | Por qué                                                                                                                                      | Condición para abrir                                                                           |
| ----------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| **`ExecuteTrade` + invariante B bajo concurrencia** (hallazgo F5, 2026-08-21) | `balance_after` se escribe desde `cash_before` pre-lock → la cadena estricta B descuadra en O(N) bajo trades concurrentes (M-2 se mantiene). | ADR/fase propia + decisión de fijar `balance_after` post-lock (tocar producción, riesgo medio) |
| **Auth global → multiusuario real** (usuarios, permisos, sesiones revocables) | hoy APP_PASSWORD global + JWT diferida                                                                                                       | Decisión de exponer la app + ADR + fase propia                                                 |
| **Legacy portfolio model** / `legacy_portfolio_id`                            | dos mundos (InvestmentAccount→Portfolio→legacy vs InvestmentAccount→Ledger)                                                                  | ADR + fase V2 específica                                                                       |
| **Scheduler-vs-worker (R-8C.2)**                                              | coexistencia scheduler no‑ARQ                                                                                                                | Decisión de autoridad única (ARQ o scheduler dedicado)                                         |
| **`pending-delete` riesgo alto (purga storage)**                              | migradores legacy con call-sites runtime pero sin writers                                                                                    | Fase planificada de purga (tras inventario completo)                                           |
| **Unificación Research→Radar**                                                | aparcado/DRAFT (F1–F3 docs cerradas)                                                                                                         | Decisión de abrir fases de código                                                              |
| **Semver real de `packages/*`**                                               | versionado ligado a tags                                                                                                                     | Decisión de política de versionado                                                             |

> **Regla:** cualquiera de estas se abre SIEMPRE como fase propia con plan/ADR + decisión explícita del propietario (E1/E7). Nunca como colateral de otra fase.

---

## 5. Orden de ejecución sugerido y agrupación en relevos (anti-saturación)

Dado el control de saturación (E2), el trabajo se agrupa en **relevos de chat** de tamaño manejable:

- **Relevo CERO:** documento de estado verificado + este plan + premisas. **Entregable:** plan aprobado. — ✅ HECHO (aprobado 2026-08-21).
- **Relevo UNO (Fases 1–3):** ✅ **EJECUTADO (2026-08-21, commit único)** — F1 invariante A en verify (EXIT 0 tras limpiar 15 cuentas sim huérfanas) · F2 tests de concurrencia custodia PG real (5 passed) · F3 análisis contrato `409` **APLAZADO** (se mantiene Opción A; B1 recomendada para una fase de contrato futura). Batería: ruff 0 · mypy 0 · pytest custodia 16 infra + 19 app passed · no-regresión OK · verify EXIT 0.
- **Relevo DOS (Fases 4–5 + R000, chaos):** ✅ **EJECUTADO (2026-08-21)** — F4 crash-consistency chaos (3 tests) · F5 concurrencia masiva chaos (5 tests) · **R000** tests m7*/m2* limpian cuentas + instrumentos (delta 0). Ejecutado contra **DB aislada `bolsa_v1_chaos`** (docker, migrada a `006`). Battery: ruff 0 · mypy 0 · chaos 8 passed · m2 7pass+1xfail / m7 pass · verify **EXIT 0** contra dev. **Hallazgo** `ExecuteTrade`/B → deuda V2.
- **Relevo TRES (Fase 6, higiene):** docstrings + mypy scope + limpieza E8 + `pending-delete` (solo bajo aprobación) + **cleanup puntual de residuos históricos en dev** (8 cuentas `m7-win-*`, instrumentos M2) + decisión de la deuda `ExecuteTrade`/B.

**Regla de relevo:** cada relevo cierra actualizando `backlog §0/§6`, `PROJECT_STATE.md`, `engineering-index`, el `plan-<fase>` y generando un **texto de paso con firma de estado** (HEAD/rama/árbol/tags) + batería + deuda-no-regresión.

---

## 6. Batería mínima obligatoria por fase (re-verificada por el coordinador)

- **Backend (py):** `ruff check packages/py apps/api-python --config pyproject.toml` → 0 · mypy de los ficheros en gate (incluye `packages/py/application/src`) · pytest de la zona.
- **Frontend/shared/contract:** `pnpm --filter @bolsa/web typecheck|lint|test` · `pnpm --filter @bolsa/shared typecheck|lint|test|build` · `contract:check` si cambia OpenAPI (precedido de `$env:PYTHONIOENCODING='utf-8'`). **NO `contract:gen`** salvo fase pactada.
- **Verificación invariante ledger:** `scripts/verify/verify_ledger_balance_chain.py` → EXIT 0 (y, tras Fase 1, con invariantes A y B) + `verify_account_isolation.py`.
- **Chaos:** ejecutar solo contra **DB de pruebas aislada (docker)**, nunca dev real.
- **Git:** `git status` acotado a los ficheros declarados por la fase.

---

## 7. Enlaces (fuentes de verdad)

- Estado verificado / ancla anti-alucinación: `docs/engineering/estado-verificado-auditoria-vs-main-2026-08-21.md`
- Backlog (LEER PRIMERO): `docs/engineering/backlog-trabajo-2026-08-20.md`
- Estado vivo: `docs/engineering/PROJECT_STATE.md`
- Premisas E1–E9: `docs/PROJECT_PREMISES.md`
- Traspaso R-11 (relevo previo): `docs/engineering/traspaso-relevo-cierre-r11-c1-c6-d1-d2-siguiente-2026-08-21.md`
- Inventario obsolescencia (riesgo alto): `docs/engineering/pending-delete/README.md`
- ADR 026: `docs/adr/026-custodia-obligacion-pendiente.md`
- Verificadores: `scripts/verify/verify_ledger_balance_chain.py` · `scripts/verify/verify_account_isolation.py`
- Estándar docstrings: `docs/engineering/code-documentation-standard-2026-08-03.md`
