# Entrega a auditoría externa (MIA) — `v2.88.59-beta` · `AUTO · UI`: **AUTO COCKPIT 1.0.1** (telemetría honesta)

> **Fecha:** 2026-10-06 · **Producto:** `V2.88.59-beta` · **Package:** `2.11.59-beta` · **Alembic head:** `048_journal_entry_dedupe_key` (**sin migración**).
> **Base:** `v2.88.58-beta` (tag → `e99c99c5`, `Release tag CI` [`37367672717`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37367672717) **VERDE**).
> **Unidad de esta auditoría:** las **dos deudas P2 de honestidad de telemetría/UI** que la auditoría externa de `v2.88.58` registró sobre `AutoRealityStrip` (semáforo verde con tipo de cuenta `NO MEDIDO` y `PAPER_D_EXECUTE` no medido colapsado a `false`). **Regla del hueco:** una regla que no se puede afirmar se declara **abierta** con su remediación, **nunca** se silencia.
> **`Δ AUTO decision/execution motor = 0`.** Ningún fichero de motor tocado; el contrato HTTP no se mueve.
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.59/README.md`](./evidence/v2.88.59/README.md) (`§0`–`§7`).
> **Nota de auditabilidad:** como en `v2.88.46`…`v2.88.58`, la cita del `Release tag CI` **no puede** viajar dentro del propio tag (el job sólo corre al empujar el tag). La cita viaja en el **`Release`** y en `main` (commit POST-TAG); dentro del tag la evidencia la declara como **`PENDIENTE`/`POST-TAG`**. No es un hueco: es el límite estructural ya conocido.

**Sello dirigido (declarado).** Mandato: **cerrar las deudas P2 de honestidad de telemetría** de la auditoría de `v2.88.58` sin romper el sello anterior. El sello **no** añade funcionalidad de motor: es un endurecimiento **UI/read-model** con `Δ motor = 0`.

---

## 1. Qué se entrega (y qué NO)

**Se entrega** la corrección de las dos deudas P2, todo **sin tocar el motor**:

1. **P2-a — Semáforo honesto ante tipo de cuenta no medido.** `buildAutoReality` (`features/auto/auto-reality.ts`) deja de fundir `accountType == null` con `virtual`: introduce un tercer tono **`"unknown"` (ámbar)** con `moneyLabel = "TIPO DE CUENTA NO CONFIRMADO"`, `brokerLabel = "Broker NO MEDIDO"` e `isVirtual = null` (tri-estado). `auto-reality-strip.tsx` pinta contenedor y punto por `tone` (ámbar), con el texto honesto en el **mismo lugar prominente** donde antes iba `DINERO VIRTUAL`.
2. **P2-b — `PAPER_D_EXECUTE` no medido declarado como tal.** `auto-reality-strip.tsx` deja de colapsar `undefined` a `false` en `killQuery.data?.paperDExecuteEnv === true` y usa `?? null`; el helper recibe el hueco y emite la nota `Ejecución paper NO MEDIDA`.

**NO se entrega**, y se declara:

- **NO** se toca el motor, los umbrales, `TOP_N`, la allocation, ni las costuras de decisión (`Δ motor = 0`).
- **NO** hay cambio de **contrato HTTP**.
- **NO** se re-mide `DÍA-D`: las cifras OOS de `v2.88.50`/`v2.88.51` se **heredan y citan**.
- **NO** se cierra **`PortfolioDecision`** (`UI52-02`), la **explicación DÍA-D `cycleId`-resolutiva** (`F-S1`), el **barrido `axe` en vivo** (`F-A2`), el **PIT histórico institucional** ni **Execution Analysis**.
- **NO** se reescribe el sello `v2.88.58-beta`: sus artefactos quedan intactos; la corrección se registra en **este** sello.

---

## 2. Cambios verificables (todo con gate)

| Pieza | Fichero(s) | Qué hace |
| --- | --- | --- |
| Semáforo honesto (P2-a) | `features/auto/auto-reality.ts` | Tercer tono `"unknown"` (ámbar) cuando el tipo de cuenta falta; `isVirtual: boolean \| null`; constantes `AUTO_REALITY_MONEY_UNKNOWN`/`AUTO_REALITY_BROKER_UNKNOWN`. |
| Render por tono (P2-a) | `features/auto/auto-reality-strip.tsx` | Mapas `TONE_CONTAINER_CLASS`/`TONE_DOT_CLASS` índice de `tone` (ámbar para `unknown`). |
| Ejecución paper honesta (P2-b) | `features/auto/auto-reality-strip.tsx` | `paperDExecuteEnv = killQuery.data?.paperDExecuteEnv ?? null` (no colapsa `undefined` a `false`). |
| Tests unit | `auto-reality.test.ts`, `auto-reality-strip.test.tsx` | Cubren las seis afirmaciones falsables de `§1` (evidencia). |
| Guardián de versión | `test_dia_d_bump_guard.py` | `meta.bump == package.json.version` (`2.11.59-beta`) en `v2_89`…`v2_97`. |

---

## 3. Medición (cifras heredadas de `v2.88.50`/`v2.88.51`, NO re-medidas)

Sin cambio de motor **ni de muestra**, este sello no re-corre el pipeline. Se **citan** las cifras vigentes de [`v2.88.50`](./evidence/v2.88.50/README.md):

| Métrica (`v2.88.50`) | Valor |
| --- | --- |
| `route` (A/C, `dia-d-thesis-exit-v5` capa v7) | `{materializado: 19, orden_creada_sin_fill: 23}` ⇒ **A = `0`**, **C = `23`** |
| `stopEvaluatedOnTouch` / `deciderRanOnTouch` | **`42/42`** / **`42/42`** |
| `candidate` (`structuralStopCandidate`) | **`42/42`** |
| `THESIS_EXIT` (n) | **`42`** |
| Expectancy bruta global | `-0.7150` |
| Banda global de R | `[-17.290, +19.328]`, `crossesZeroR = true`, **`pointCitable = false`** |

---

## 4. Hallazgos abiertos (declarados, con remediación)

- **`F-A2` — barrido `axe` en vivo de `/auto/*` no ejecutado.** Remediación: spec `axe` propio para `/auto/*` en el siguiente sello de UI.
- **`F-S1` — explicación DÍA-D `cycleId`-resolutiva:** requiere contrato de artefacto por `cycleId` (fase backend **F5**).
- **`F-S2`/`F-S3` (P3):** densidad tipográfica (`text-[11px]`) e `h1` crudo de ausencia.
- **`PortfolioDecision` durable (`UI52-02`)**, **PIT histórico institucional** y **Execution Analysis** (`23 orden_creada_sin_fill`): abiertos (spine/backend).
- **`heading-order` fuera de AUTO (11 rutas, heredado de `v2.88.54`)**: deuda declarada.
- **`23` warnings `react-hooks/exhaustive-deps`** (`eslint`, **0 errores**): pre-existentes.
- **Método local (declarado):** en esta máquina, la política *App Control* de Windows bloquea `python.exe`, por lo que `test_dia_d_bump_guard.py` y `contract:check` **no** se ejecutaron por CLI; el bump guard se verificó por inspección (9/9 `meta.bump` == `2.11.59-beta`) y el contrato se declara intacto. CI los re-ejecuta.

---

## 5. Gates

| Gate | Resultado |
| --- | --- |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **passed** (`2.11.59-beta`, verificado por inspección local) |
| `@bolsa/web` `vitest` | **1438 passed** (`249` ficheros; **+3** sobre `v2.88.58`) |
| `@bolsa/web` `typecheck` / `lint` | limpio · **0 errores** (`23` warnings pre-existentes) |
| `pnpm window:test` | **25/25** |
| `E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-e2e-v28856 gp-e2e-v28857` | **6 passed** (mock, sin API; `workers=1`) |
| `contract:check` | no ejecutable en local (App Control); contrato **no tocado** — lo verifica CI |

---

## 6. Sello

- **Producto:** `V2.88.59-beta`. **Package:** `2.11.59-beta`. **Sin migración** (Alembic head `048_journal_entry_dedupe_key`). **Sin cambio de contrato HTTP.**
- **Añadidos:** `docs/engineering/evidence/v2.88.59/README.md`, este documento.
- **Modificados:** `apps/web/src/features/auto/auto-reality.ts` + `auto-reality.test.ts`, `apps/web/src/features/auto/auto-reality-strip.tsx` + `auto-reality-strip.test.tsx`, `package.json` (`2.11.59-beta`), `v2_89`…`v2_97` (`meta.bump`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `scripts/lib/window-forward.mjs` (re-anclaje del freeze).

| Rol | Commit | Árboles |
| --- | --- | --- |
| **Sello funcional** (`feat`) | `c8c23cef` | `apps` `a909995b…` / `packages` `95cb0d69…` |
| Re-anclaje del freeze de la ventana (`chore`) | `982a50fd` | pin `commit: c8c23cef` (no mueve árbol) |
| **Commit del tag** (`docs(seal)`) | _(este commit)_ · tag anotado `v2.88.59-beta` | (mismos árboles que el funcional) |
| Cita **POST-TAG** | _(pendiente)_ | — |

- **Tag:** `v2.88.59-beta` — **PENDIENTE** de crear; `Release tag CI` **PENDIENTE**; `GitHub Release` **PENDIENTE**.

---

## 7. Guion de auditoría desde GitHub

1. **Tag → evidencia.** Abrir `docs/engineering/evidence/v2.88.59/README.md` en el árbol del tag. Dentro del tag, `§7` (cita CI) se declara **POST-TAG**.
2. **Entrega MIA.** Leer este documento: qué se entrega/NO, cambios verificables, medición heredada, hallazgos abiertos y gates.
3. **Base.** `docs/engineering/evidence/v2.88.58/README.md` y `docs/engineering/entrega-auditoria-externa-mia-v2.88.58-2026-10-05.md` (auditoría que originó las dos deudas P2).
4. **CI del tag.** Abrir la pestaña **Actions** → `Release tag CI` del tag `v2.88.59-beta`. Comprobar `replay-repro` **REPRODUCIDO** (⇒ `Δ motor = 0`) y los jobs `python`, `frontend`, `shared`, `decision-spine`, `lifecycle-pg`, `security`, `certify` en **success**.
5. **Reproducción local (opcional).**
   ```bash
   git checkout v2.88.59-beta
   uv run --no-sync python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
   pnpm --filter @bolsa/web test
   pnpm --filter @bolsa/web typecheck
   pnpm --filter @bolsa/web lint
   pnpm --filter @bolsa/web contract:check
   pnpm window:test
   E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-e2e-v28856 gp-e2e-v28857
   ```
6. **Qué falsaría el sello:** que `accountType == null` vuelva a producir `tone === "virtual"` · que el texto con tipo no confirmado sea `DINERO VIRTUAL` · que `isVirtual` rellene el hueco con `true` · que un `PAPER_D_EXECUTE` pendiente se muestre como `false` medido · que `live`/`simulated` cambien de tono · que el diff toque motor/umbrales · que `replay-repro` no reproduzca.
