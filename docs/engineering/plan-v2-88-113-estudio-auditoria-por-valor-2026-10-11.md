# Plan — `v2.88.113-beta` / **`P2` — auditoría por valor de ESTUDIO**: estrategia + porqué + señal + resultado

> **Estado:** **EJECUTADO** (2026-10-11) — sello 2 de `P2` implementado y verificado en local; tag `v2.88.113-beta` **por publicar**.
> **Base funcional:** `v2.88.112-beta` (tag anotado `v2.88.112-beta` → commit `d955da59`).
> **Naturaleza:** `Δ motor ≠ 0` **aditivo** (módulo puro `estudio_audit.py` + ruta read-only + componentes UI) · **`Δ decisión = 0`** (sin umbrales/reparto/`TOP_N`/régimen/protección) · **SIN migración** (head `053_dia_d_cycle_verifications`) · contrato HTTP **ampliado** (`contract:gen`).
> **Origen:** hueco **`P2`** de la [auditoría profundizada](./auditoria-profundizada-auto-h1-sim-dia-d-2026-10-11.md). El sello 1 (`v2.88.112-beta`) cerró el **enlace durable** verificación↔ciclo; este sello compone la **auditoría por valor de ESTUDIO**.

---

## 0. Objetivo y criterio de aceptación (falsable)

**Hueco:** el veredicto DÍA-D queda **fragmentado** entre cuatro capas que hoy viven dispersas y no se pueden leer por valor: **estrategia elegida** (identidad exacta `presetKey`), **porqué** (`definition.indicatorSpecs` + `coachFacts.recommendations[]`), **señal** (ciclos del `auto_operational_monitor`), **resultado** en **R** (feedback por valor) y en **dinero** (`oos_finance.py`). El dinero se agrupaba por `strategy_version` **opaco**, sin la clave exacta que el ciclo ya sella (`strategyPresetKey`, H1).

**Criterio de aceptación falsable.**
1. Existe un **read-model por valor de ESTUDIO** que reúne las cuatro capas por símbolo, con la **clave de unión EXACTA `presetKey`** (H1).
2. Un valor solo se declara **`measured`** si **ambas** mitades (R y dinero) alcanzan su **suelo de muestra**; en otro caso los ratios son **`None`** — **jamás** `0` que finja medición.
3. **`presetKey` ambigua** (dos ciclos del mismo valor declaran identidades distintas) ⇒ la unión del dinero es un **hueco declarado** (`None`), **nunca** se elige una «ganadora».
4. La ruta es **fail-closed por cuenta** (sin cuenta ⇒ `no_account_scope`) y **read-only** (`PRECOMPUTED_ARTIFACT`): compone piezas **ya calculadas**, no recalcula el motor.
5. La UI lo pinta en **`/auto/analisis`** («¿Qué ha pasado?») sin fabricar números: `pointCitable = false` (banda `K`), huecos en «Sin dato todavía».
6. El artefacto congelado de `replay-repro` **no** se toca ⇒ `Δ decisión = 0`.

---

## 1. Precedente y reutilización (no duplicar)

- **Identidad exacta H1:** el ciclo sella `cycle.strategyPresetKey` (misma clave que el TOP) — [`auto-operation-strategy.ts`](../../apps/web/src/features/auto/auto-operation-strategy.ts) y evidencia [`v2.88.107`](./evidence/v2.88.107/README.md)/[`v2.88.108`](./evidence/v2.88.108/README.md)/[`v2.88.112`](./evidence/v2.88.112/README.md).
- **Fichas por valor (R):** [`build_value_scorecard`](../../packages/py/application/src/bolsa_application/dia_d_auto_feedback.py) del artefacto de feedback.
- **Índice por ciclo:** `cycles[]` del mismo artefacto, expuesto read-only en [`auto_dia_d_feedback.py`](../../apps/api-python/src/bolsa_api/api/v1/routes/auto_dia_d_feedback.py).
- **Dinero:** reporte financiero OOS por `(estrategia × instrumento)` de [`oos_finance.py`](../../packages/py/application/src/bolsa_application/oos_finance.py) — evidencia [`v2.88.111`](./evidence/v2.88.111/README.md).
- **Restricciones del acta `v2.88.111-beta`:** `pointCitable = false` (banda `K` sin medir), costes **modelados**, `UNKNOWN ≠ 0` (hueco declarado, nunca `0`).

---

## 2. Diseño por fases

### Fase A — Clave de unión exacta (H1) en las dos mitades

- [`oos_finance.py`](../../packages/py/application/src/bolsa_application/oos_finance.py): `OosFill`/`GroupMetrics` ganan `strategy_preset_key`; `to_dict()` emite `strategyPresetKey`; `fills_from_replay` propaga la clave (`strategyPresetKey`/`strategy_preset_key`) y declara hueco (`None`) si el fill no la trae; por grupo se toma el **primer `presetKey` no vacío** de sus filles (sin identidad ⇒ `None`).
- [`dia_d_auto_feedback.py`](../../packages/py/application/src/bolsa_application/dia_d_auto_feedback.py): `_normalize_cycle_row` copia `strategyPresetKey`/`presetKey` del hecho; ausente ⇒ `None`.

### Fase B — Módulo PURO de auditoría por valor

- [`estudio_audit.py`](../../packages/py/application/src/bolsa_application/estudio_audit.py): `build_estudio_audit_report` compone por símbolo **estrategia** (identidad exacta + ambigüedad declarada) + **porqué** (`indicatorSpecs`/`recommendations`, si el llamante los aporta) + **señal** (ciclos/días) + **resultado R** + **dinero**.
- Unión del dinero a la estrategia por la clave **EXACTA `presetKey`**; ambigua ⇒ `None` (hueco); **suelos de muestra** (`DEFAULT_MIN_CYCLES = 5` R y `DEFAULT_MIN_TRADES = 10` dinero) para declarar `measured`; ratios `None` bajo el suelo; salida **ordenada por símbolo** (mismo estado ⇒ mismo payload); `pointCitable = false`.

### Fase C — API read-only y contrato

- [`auto_estudio_audit.py`](../../apps/api-python/src/bolsa_api/api/v1/routes/auto_estudio_audit.py): `GET /api/auto/estudio-audit` (ventana más reciente con artefacto) y `GET /api/auto/estudio-audit/{window}`; `serving = PRECOMPUTED_ARTIFACT`; **fail-closed por cuenta**; DTOs con **política de huecos** (`None`, nunca `""`/`0`). Registrado en [`router.py`](../../apps/api-python/src/bolsa_api/api/v1/router.py).
- `contract:gen` regenera [`openapi.json`](../../apps/web/api/openapi.json)/[`schema.d.ts`](../../apps/web/src/api/schema.d.ts); `contract:check` verde.

### Fase D — UI

- [`api.ts`](../../apps/web/src/lib/api.ts): `getAutoEstudioAudit` / `getAutoEstudioAuditWindow`.
- [`use-auto-dia-d-feedback.ts`](../../apps/web/src/features/auto-monitor/use-auto-dia-d-feedback.ts): `useAutoEstudioAudit` (read-only, fail-closed por cuenta).
- [`estudio-audit-view.ts`](../../apps/web/src/features/auto-monitor/estudio-audit-view.ts): helpers PUROS (`formatR`/`formatPct`/`formatRate`/`describeStrategy`/`describeVerdict`) — un dato ausente ⇒ «Sin dato todavía», nunca `0`.
- [`estudio-audit-panel.tsx`](../../apps/web/src/features/auto-monitor/estudio-audit-panel.tsx): tarjeta «Auditoría por valor de ESTUDIO», integrada en [`auto-analisis-page.tsx`](../../apps/web/src/features/auto/auto-analisis-page.tsx) (pestaña «¿Qué ha pasado?»), con detalle técnico en vista secundaria.

### Fase E — Pruebas

- **Aplicación** [`test_estudio_audit.py`](../../packages/py/application/tests/test_estudio_audit.py): unión exacta por `presetKey`, suelos, huecos R/dinero, ambigüedad declarada, orden por símbolo.
- **Aplicación** [`test_oos_finance.py`](../../packages/py/application/tests/test_oos_finance.py): la clave exacta viaja al grupo; `fills_from_replay` la propaga y declara hueco (cadena vacía ⇒ `None`).
- **Ruta (hermética)** [`test_auto_estudio_audit_route.py`](../../apps/api-python/tests/test_auto_estudio_audit_route.py): ventana concreta, ventana inválida, sin cuenta (`no_account_scope`), sin artefacto.
- **Vitest** [`estudio-audit-view.test.ts`](../../apps/web/src/features/auto-monitor/estudio-audit-view.test.ts) + [`estudio-audit-panel.test.tsx`](../../apps/web/src/features/auto-monitor/estudio-audit-panel.test.tsx).

---

## 3. Restricción DURA — el sello `replay-repro` NO se puede mover

`replay-repro` regenera `replay-oos-durable-v2.88.7.json` desde el fixture y **asserta su `SHA-256` byte a byte**. La clave `presetKey` es **aditiva y opcional** (`None` por defecto) y la composición de ESTUDIO es un reporte **opt-in → no** entra en el payload del replay ⇒ el artefacto congelado **no** puede moverse (`Δ decisión = 0`).

---

## 4. Riesgos y mitigaciones

| Riesgo | Mitigación |
| --- | --- |
| «Elegir una ganadora» cuando hay identidad ambigua | `presetKey` distinta por valor ⇒ unión **`None`** (hueco declarado), nunca un ganador arbitrario |
| Fingir medición con `0` | `UNKNOWN ≠ 0`: ratios `None` bajo el suelo de muestra; `measured` exige **ambas** mitades |
| Atribuir el dinero a la estrategia equivocada | Unión por la clave **EXACTA** `presetKey` (H1), no por `strategy_version` opaco |
| Regresión del sello congelado | La clave nueva es **opcional** y el reporte de ESTUDIO es **opt-in**; no entra en el payload del replay |
| Prometer rentabilidad | Banda, no punto (`pointCitable = false`); el informe **compone**, no afirma |

---

## 5. Entrega, gates y sello

- `docs/engineering/evidence/v2.88.113/README.md` (formato del de `v2.88.112`).
- **Bump** `package.json` → `2.11.113-beta` y `meta.bump` de los 9 CLIs DÍA-D `v2_89`…`v2_97` (guardián [`test_dia_d_bump_guard.py`](../../apps/api-python/tests/test_dia_d_bump_guard.py)).
- CI verde en [`release-tag-ci.yml`](../../.github/workflows/release-tag-ci.yml): `python`, `lifecycle-pg` (Alembic + golden), `frontend` (`contract:check`), `playwright-integrated-auto-s5`, `replay-repro` = `REPRODUCIDO`, `certify`.
- Tag anotado **`v2.88.113-beta`** (unsigned, limitación de certificación) + cita POST-TAG.
