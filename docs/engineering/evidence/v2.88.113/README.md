# Evidencia — `v2.88.113-beta` / **`P2` (sello 2) — auditoría por valor de ESTUDIO**: estrategia + porqué + señal + resultado

> **Base funcional:** `v2.88.112-beta` (commit `d955da59`). Cierra el hueco **`P2`** (DÍA-D enlazado al ciclo + auditoría por valor) de la [auditoría profundizada](../../auditoria-profundizada-auto-h1-sim-dia-d-2026-10-11.md).
> **Naturaleza:** sello **aditivo**. `Δ motor ≠ 0` (módulo puro nuevo `estudio_audit.py` + clave `presetKey` en las dos mitades + ruta read-only + componentes UI) pero **`Δ decisión = 0`**: sin motor de decisión, sin umbrales, sin reparto ni `TOP_N`/régimen/selección/protección. **SIN migración** (head `053_dia_d_cycle_verifications`). **Contrato ampliado** (`contract:gen`).
> **Alcance:** **sello 2 de `P2`** — la **composición por valor de ESTUDIO**. El **enlace durable** verificación↔ciclo fue el sello 1 ([`v2.88.112`](../v2.88.112/README.md)).
> **Plan:** [`plan-v2-88-113-estudio-auditoria-por-valor-2026-10-11.md`](../../plan-v2-88-113-estudio-auditoria-por-valor-2026-10-11.md).

---

## 1. Qué cierra (el hueco de `P2`)

El veredicto DÍA-D quedaba **fragmentado** en cuatro capas que no se podían leer **por valor**: la **estrategia elegida** (identidad exacta `presetKey`), el **porqué** (`definition.indicatorSpecs` + `coachFacts.recommendations[]`), la **señal** (los ciclos de `auto_operational_monitor`) y el **resultado** — en **R** (feedback por valor) y en **dinero** (`oos_finance.py`). Además, el dinero se agrupaba por `strategy_version` **opaco**, sin la clave exacta que el ciclo ya sella desde H1 (`strategyPresetKey`). Este sello **compone** las cuatro capas por símbolo y **une** el dinero a la estrategia por la **clave EXACTA `presetKey`**.

## 2. Clave de unión exacta (H1) en las dos mitades

- [`oos_finance.py`](../../../../packages/py/application/src/bolsa_application/oos_finance.py): `OosFill` y `GroupMetrics` ganan `strategy_preset_key`; `GroupMetrics.to_dict()` emite `strategyPresetKey`; `fills_from_replay` propaga la identidad (`strategyPresetKey`/`strategy_preset_key`) y declara hueco (`None`) si el fill no la trae; por grupo se toma el **primer `presetKey` NO vacío** de sus filles (sin identidad ⇒ `None`, jamás fabricada).
- [`dia_d_auto_feedback.py`](../../../../packages/py/application/src/bolsa_application/dia_d_auto_feedback.py): `_normalize_cycle_row` copia `strategyPresetKey`/`presetKey` del hecho; ausente ⇒ `None`.

## 3. Módulo PURO de auditoría por valor

[`estudio_audit.py`](../../../../packages/py/application/src/bolsa_application/estudio_audit.py) (sin DB/red/reloj): `build_estudio_audit_report` compone **por símbolo**:

- **estrategia** — identidad exacta (`presetKey` + `version`) con **ambigüedad declarada** (`_first_distinct`: dos identidades distintas ⇒ `None` + «ambigua», **nunca** una «ganadora»).
- **porqué** — `indicatorSpecs` + `recommendations` si el llamante los aporta; ausente ⇒ hueco declarado (no se inventa la explicación).
- **señal** — nº de ciclos / ciclos medidos / días cubiertos (`_signal_for_symbol`).
- **resultado R** — `verdict`/`expectancyR`/`hitRate`/`realizedRTotal` con **suelo** `DEFAULT_MIN_CYCLES = 5`.
- **dinero** — `netReturnPct`/`netReturnPctAtStress`/`maxDrawdownPct`/`hitRate`/`committedCapital`/`trades` con **suelo** `DEFAULT_MIN_TRADES = 10`; unión del grupo por la clave **EXACTA `presetKey`** (`_pick_finance_group`; si hay varios candidatos sin clave ⇒ **ambiguo** ⇒ `None`).

**Honestidad:** un valor solo se declara `measured = true` si **ambas** mitades alcanzan su suelo; en otro caso los ratios viajan en `None` y el motivo en `unmeasured` — **jamás** `0` que finja medición. `pointCitable = false` (banda `K`, no punto). Salida **ordenada por símbolo** ⇒ mismo estado, mismo payload.

## 4. API read-only y contrato

[`auto_estudio_audit.py`](../../../../apps/api-python/src/bolsa_api/api/v1/routes/auto_estudio_audit.py) (registrado en [`router.py`](../../../../apps/api-python/src/bolsa_api/api/v1/router.py)):

- **`GET /api/auto/estudio-audit`** — auditoría por valor de la ventana más reciente con artefacto.
- **`GET /api/auto/estudio-audit/{window}`** — ventana concreta (`D0_D1`); ventana inválida ⇒ `available = false` + `invalid_window`.
- `serving = PRECOMPUTED_ARTIFACT`: compone piezas **ya calculadas** (feedback DÍA-D + reporte financiero OOS opt-in `finance-<window>.json`); **no** recalcula el motor.
- **Fail-closed por cuenta:** sin cuenta visible ⇒ `available = false` + `no_account_scope` (nunca datos globales); sin artefacto ⇒ `available = false`.
- DTOs con **política de huecos** (`None`, nunca `""`/`0`). `contract:gen` regenera [`openapi.json`](../../../../apps/web/api/openapi.json)/[`schema.d.ts`](../../../../apps/web/src/api/schema.d.ts); `contract:check` **OK**.

## 5. UI (superficie en `/auto/analisis`)

- [`api.ts`](../../../../apps/web/src/lib/api.ts): `getAutoEstudioAudit` / `getAutoEstudioAuditWindow`.
- [`use-auto-dia-d-feedback.ts`](../../../../apps/web/src/features/auto-monitor/use-auto-dia-d-feedback.ts): `useAutoEstudioAudit` (read-only, fail-closed por cuenta).
- [`estudio-audit-view.ts`](../../../../apps/web/src/features/auto-monitor/estudio-audit-view.ts): helpers PUROS (`formatR`/`formatPct`/`formatRate`/`describeStrategy`/`describeVerdict`); un dato ausente ⇒ **«Sin dato todavía»**, nunca `0`.
- [`estudio-audit-panel.tsx`](../../../../apps/web/src/features/auto-monitor/estudio-audit-panel.tsx): tarjeta «Auditoría por valor de ESTUDIO», integrada en [`auto-analisis-page.tsx`](../../../../apps/web/src/features/auto/auto-analisis-page.tsx) (pestaña **«¿Qué ha pasado?»**), con **detalle técnico en vista secundaria**.

## 6. Pruebas

- **Aplicación** [`test_estudio_audit.py`](../../../../packages/py/application/tests/test_estudio_audit.py): unión exacta por `presetKey`, suelos de muestra, huecos R/dinero, **ambigüedad** declarada, orden por símbolo.
- **Aplicación** [`test_oos_finance.py`](../../../../packages/py/application/tests/test_oos_finance.py): la clave exacta viaja al grupo; `fills_from_replay` la propaga y declara hueco (cadena vacía ⇒ `None`).
- **Ruta (hermética)** [`test_auto_estudio_audit_route.py`](../../../../apps/api-python/tests/test_auto_estudio_audit_route.py): ventana concreta, ventana inválida, sin cuenta (`no_account_scope`), sin artefacto.
- **Vitest** [`estudio-audit-view.test.ts`](../../../../apps/web/src/features/auto-monitor/estudio-audit-view.test.ts) (formato honesto) + [`estudio-audit-panel.test.tsx`](../../../../apps/web/src/features/auto-monitor/estudio-audit-panel.test.tsx) (panel + hueco declarado).

## 7. Bump, migración y contrato

`2.11.112-beta` → **`2.11.113-beta`**: `package.json` + `meta.bump` de los 9 CLIs DÍA-D `v2_89`…`v2_97`, guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) → **verde**. **SIN migración** (head `053_dia_d_cycle_verifications`). **Contrato ampliado** (`contract:gen` = 225 paths / 487 schemas; `contract:check` verde).

## 8. Verificación (local)

- `ruff check packages/py apps/api-python --config pyproject.toml` → **All checks passed**.
- `lint-imports --config packages/py/.importlinter` → **4 kept, 0 broken**.
- `mypy` (las 5 raíces `src`, `--follow-imports=silent`) → **551 source files, no issues**.
- `pytest packages/py/application/tests -q` → **2679 passed**.
- web: `typecheck` **OK** · `lint` **0 errors** · `vitest` → **297 files / 2093 passed**.
- Guardianes + censo CI + rutas DÍA-D/ESTUDIO (`test_dia_d_bump_guard` + `test_ci_test_selection_census` + `test_auto_estudio_audit_route` + `test_auto_dia_d_feedback_route` + `test_auto_dia_d_verification_route`) → **28 passed**.
- `contract:gen` (225 paths / 487 schemas) + `contract:check` → **OK**.

## 9. Límites (declarados, no disfrazados)

- **Compone, no afirma.** El informe reúne piezas **ya calculadas**; **no** recalcula el motor ni proclama una estrategia «ganadora».
- **Huecos declarados.** `presetKey` ausente o **ambigua** ⇒ `None` («Sin dato todavía»), nunca un ganador arbitrario; bajo el suelo de muestra los ratios son `None`, **jamás `0`**.
- **Banda, no punto.** `pointCitable = false`: la banda de `K=12` sorteos cruza el cero ([`v2.88.16.3`](../v2.88.16.3/README.md)); un punto **no** es propiedad del motor.
- **Costes modelados.** El overlay de coste es **modelado** (la fricción medida del SIM iría aparte, sin doble contabilización).
- **`Δ decisión = 0`.** La clave nueva es **opcional** y el reporte de ESTUDIO es **opt-in**: no entra en el payload del replay; el artefacto de `replay-repro` **no** se toca.
- **Cita POST-TAG pendiente:** el objeto del tag, el commit y el run de `Release tag CI` se añaden en §10 tras publicar.

## 10. Cita POST-TAG

Tag anotado **`v2.88.113-beta`** (objeto `7713925b4fa73f2ed7705705624cac06c2a5a857` → commit `3dd15193881895a5bfa7a55937aca7e14963b500`) sellado y publicado en `origin`.

- `Release tag CI` [**38177610756**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38177610756) → **`success`**: **12 jobs `success` + `certify` `success`** (`playwright (integrated E2E, opt-in)` `skipped`, esperado).
- **`replay-repro`** → **`REPRODUCIDO`**: `sha256` `1E3ADAC2…929A37E7` **idéntico** a los sellos previos ⇒ **prueba directa** de que el sello **no** movió el artefacto congelado (`Δ decisión = 0` confirmado por CI).
- Tag **unsigned** (`verification.verified = false`, `reason: unsigned`): limitación de certificación, no defecto funcional.

### 10.1 Verificación externa (comunicado vs verificado)

- **Estado comunicado (antes de publicar):** el tag y la comparación devolvían `404` porque `v2.88.112-beta`/`v2.88.113-beta` **solo existían en el clon local**; no había `ref` remoto.
- **Verificación externa (confirmada 2026-10-11):** tras publicar el tag, `gh api repos/jvelasca/Bolsa_V1/git/ref/tags/v2.88.113-beta` **resuelve** al objeto `7713925b…` → commit `3dd15193`, y el run `38177610756` (`headBranch=v2.88.113-beta`, `headSha=3dd15193`) figura **`success`**. La verificación ya **no** es pendiente.
- **Residuo `R-2` (no cerrado por este sello):** al empujar **solo** el tag, los 2 commits (`d955da59`, `3dd15193`) son alcanzables por el tag pero **no** por `main` ⇒ no corrió el CI de rama sobre ellos; `origin/main` sigue en `3d8e74ad`. **→ RESUELTO en `v2.88.114-beta` (2026-10-12):** `main` empujado a `origin` (`3d8e74ad..1c33e7c1`); CI de rama `success`.
- **Alcance de la aprobación:** la aprobación del sello **no** demuestra la rentabilidad de las estrategias ni certifica por sí sola el bloqueo de **todas** las rutas de órdenes reales de `XTB`. Es un sello **aditivo** (`Δ decisión = 0`), no una afirmación de rendimiento.

