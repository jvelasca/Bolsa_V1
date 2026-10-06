# Evidencia `v2.88.59-beta` — `AUTO · UI`: **AUTO COCKPIT 1.0.1** (telemetría honesta: semáforo `unknown` y `PAPER_D_EXECUTE` NO MEDIDO)

**Objeto:** el **siguiente chat, un auditor externo, o un Cursor distinto**. No es el historial.

**Producto:** `V2.88.59-beta` · **Package:** `2.11.59-beta` · **AsOf:** 2026-10-06 · **Nature:** `UI / read-model` · **Fase:** `AUTO UI 1.0.1 (honestidad de telemetría)`. **Δ AUTO decision/execution motor = 0**.

**Schemas:** sin cambios (`dia-d-multi-band-v1`, `dia-d-thesis-exit-v5`, `dia-d-multi-cycle-ledger-v7`, `dia-d-thesis-stop-sequences-v2`). **Alembic:** head `048_journal_entry_dedupe_key` — **SIN migración**. **Contrato HTTP:** **sin cambio** (endpoints intactos).

**Padre:** [`v2.88.58`](../v2.88.58/README.md) (tag → `e99c99c5`, `Release tag CI` [`37367672717`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37367672717) VERDE) → [`v2.88.57`](../v2.88.57/README.md).

**Decisión de alcance (declarada).** Entrada: la auditoría externa de [`v2.88.58`](../../entrega-auditoria-externa-mia-v2.88.58-2026-10-05.md) que **aprueba el sello** pero registra **dos deudas P2** de honestidad de telemetría/UI. Este slice **solo** las corrige; es UI/read-model puro: **NO** toca motor, contrato HTTP, migraciones ni el pipeline `DÍA-D`.

---

## 0. Qué añade este sello (y qué NO)

**Añade** dos correcciones de honestidad de telemetría en el semáforo de realidad monetaria (sin motor):

1. **P2-a — Un tipo de cuenta no medido ya no se pinta como `virtual`.** `buildAutoReality` (`features/auto/auto-reality.ts`) trataba `accountType == null` como `tone = "virtual"` (verde), invirtiendo el patrón *fail-closed* que el propio fichero declara. Ahora existe un **tercer tono `"unknown"` (ámbar)**: `moneyLabel = "TIPO DE CUENTA NO CONFIRMADO"`, `brokerLabel = "Broker NO MEDIDO"` e `isVirtual = null`. El hueco se declara en el **mismo lugar prominente** donde antes iba la afirmación tranquilizadora.
2. **P2-b — `PAPER_D_EXECUTE` pendiente ya no se colapsa a `false`.** `auto-reality-strip.tsx` calculaba `killQuery.data?.paperDExecuteEnv === true`; mientras la query no respondía, `undefined` devenía `false` y el helper nunca recibía `null`, de modo que la nota `Ejecución paper NO MEDIDA` jamás aparecía. Ahora usa `?? null`: «no medido» se declara `NO MEDIDO`.

**NO** toca el motor, los umbrales, `TOP_N`, la allocation ni las costuras de decisión. **NO** cambia el contrato HTTP. **NO** re-mide `DÍA-D`. **NO** cierra `PortfolioDecision` (`UI52-02`), la explicación DÍA-D `cycleId`-resolutiva (`F-S1`), el barrido `axe` en vivo (`F-A2`), PIT institucional ni Execution Analysis.

---

## 1. Afirmaciones falsables (cada una con su forma de romperse)

| # | Afirmación | Cómo se rompe (falsación) | Evidencia |
| --- | --- | --- | --- |
| **1** | Un tipo de cuenta **ausente** toma el tono `unknown` (ámbar), **nunca** `virtual`. | Que `accountType == null` vuelva a producir `tone === "virtual"`. | §3; `auto-reality.test.ts`; `auto-reality-strip.test.tsx`. |
| **2** | El **texto** del caso no medido es `TIPO DE CUENTA NO CONFIRMADO` en el primer nivel, no una nota secundaria. | Que el `auto-reality-money` renderice `DINERO VIRTUAL` con `type` sin confirmar. | §3; `auto-reality-strip.test.tsx`. |
| **3** | `isVirtual` es `null` cuando el tipo no se conoce (`UNKNOWN ≠ 0`). | Que un hueco se rellene con `true`/`false`. | §3; `auto-reality.test.ts`. |
| **4** | Un `PAPER_D_EXECUTE` **pendiente** se declara `NO MEDIDO`. | Que `undefined` se colapse a `false` y desaparezca la nota. | §3; `auto-reality.test.ts`; `auto-reality-strip.test.tsx`. |
| **5** | Con cuenta `live`, el semáforo sigue reclamando dinero real; con `simulated`, virtual. | Que `live`/`simulated` cambien de tono. | §3; `auto-reality.test.ts`. |
| **6** | `Δ motor = 0`. | Que el diff toque motor/umbrales. | §6 (`apps`/`packages` sin ficheros de motor). |

---

## 2. Verificación (gates)

| Gate | Resultado |
| --- | --- |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **passed** (`meta.bump` de `v2_89`…`v2_97` == `package.json` `2.11.59-beta`) — **verificado por inspección local** |
| `@bolsa/web` `vitest` | **1438 passed** (`249` ficheros; **+3** sobre `v2.88.58`) |
| `@bolsa/web` `typecheck` (`tsc -b --noEmit`) | limpio |
| `@bolsa/web` `lint` | **0 errores** (`23` warnings pre-existentes) |
| `pnpm window:test` | **25/25** |
| E2E mock AUTO (`gp-e2e-v28856`/`gp-e2e-v28857`) | **6 passed** |
| `contract:check` | **no ejecutable en local** (política *App Control* bloquea el spawn de `python`); contrato HTTP **no tocado**; lo verifica CI |

> **Nota de método (declarada).** En esta máquina, la política *App Control* de Windows bloquea la ejecución de `python.exe` (`os error 4551`), por lo que el `bump guard` y `contract:check` **no** pudieron ejecutarse por CLI; el `bump guard` se verificó **por inspección** (los 9 `meta.bump` y `package.json` coinciden en `2.11.59-beta`, sin residuo `2.11.58-beta` en `apps/`) y el contrato se declara intacto. **Hueco declarado**, no silenciado; CI re-ejecuta ambos.

---

## 3. Las correcciones, en detalle

- **`features/auto/auto-reality.ts`:** `AutoRealityTone = "virtual" | "real" | "unknown"`; `isVirtual: boolean | null`; constantes `AUTO_REALITY_MONEY_UNKNOWN`/`AUTO_REALITY_BROKER_UNKNOWN`; el helper ramifica `!accountKnown → unknown`, `realMoney → real`, resto → `virtual`.
- **`features/auto/auto-reality-strip.tsx`:** `paperDExecuteEnv = killQuery.data?.paperDExecuteEnv ?? null`; el contenedor y el punto se pintan con mapas `TONE_CONTAINER_CLASS`/`TONE_DOT_CLASS` índice de `reality.tone` (ámbar para `unknown`).
- **Tests:** `auto-reality.test.ts` (1 actualizado + 1 nuevo) y `auto-reality-strip.test.tsx` (2 nuevos + mock reconfigurable).

---

## 4. Límites declarados (NO se cierran aquí)

- **`PortfolioDecision` durable (`UI52-02`)**: sigue abierta (backend/spine).
- **Contrato de explicación DÍA-D verdaderamente `cycleId`-resolutivo (`F-S1`)**: fase backend **F5**.
- **`F-A2` — barrido `axe` en vivo de `/auto/*`**: **no** re-ejecutado.
- **`F-S2`/`F-S3` (P3)**: densidad tipográfica (`text-[11px]`) e `h1` crudo de ausencia.
- **PIT histórico institucional** y **Execution Analysis** (`23 orden_creada_sin_fill`): P3 abiertas.
- **NO** se re-mide `DÍA-D`: las cifras OOS de `v2.88.50`/`v2.88.51` se **heredan y citan**.

---

## 5. Cómo se reproduce

```bash
# 1) Guard backend de versión (meta.bump == package.json).
uv run --no-sync python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q

# 2) UI.
pnpm --filter @bolsa/web test
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web lint
pnpm --filter @bolsa/web contract:check

# 3) Freeze del runner de la ventana.
pnpm window:test

# 4) E2E del cockpit AUTO (mock, sin API; workers=1 como CI).
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-e2e-v28856 gp-e2e-v28857
```

**No** se reproduce el pipeline `DÍA-D` en este sello (declarado): las cifras OOS se **citan** de `v2.88.50`/`v2.88.51`.

---

## 6. Sello

- **Añadidos:** `docs/engineering/evidence/v2.88.59/README.md`, `docs/engineering/entrega-auditoria-externa-mia-v2.88.59-2026-10-06.md`.
- **Modificados:** `apps/web/src/features/auto/auto-reality.ts` + `auto-reality.test.ts`, `apps/web/src/features/auto/auto-reality-strip.tsx` + `auto-reality-strip.test.tsx`, `package.json` (`2.11.59-beta`), `v2_89`…`v2_97` (`meta.bump`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `scripts/lib/window-forward.mjs` (re-anclaje del freeze).
- **`Δ AUTO decision/execution motor = 0`:** ningún fichero de motor tocado; el contrato HTTP no se mueve.

| Rol | Commit | Árboles |
| --- | --- | --- |
| **Sello funcional** (`feat`) | `c8c23cef` | `apps` `a909995b…` / `packages` `95cb0d69…` |
| Re-anclaje del freeze de la ventana (`chore`) | `982a50fd` | pin `commit: c8c23cef` (no mueve árbol) |
| **Commit del tag** (`docs(seal)`) | _(este commit)_ · tag anotado `v2.88.59-beta` | (mismos árboles que el funcional) |
| Cita **POST-TAG** (evidencia §7) | _(pendiente)_ | — |

---

## 7. Cita del CI (POST-TAG)

> **`Release tag CI`** del tag `v2.88.59-beta`: **PENDIENTE** de certificar. Se citará aquí (POST-TAG) con el run, el veredicto de `replay-repro` y la confirmación de `Δ motor = 0`. Ningún tag contiene su propio resultado de CI — límite estructural declarado, como en `v2.88.46`…`v2.88.58`.
