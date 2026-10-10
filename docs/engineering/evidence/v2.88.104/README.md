# Evidencia `v2.88.104-beta` — **UI 8.x: puente AUTO → DÍA-D (`S5`) + refactor DRY del lanzamiento DÍA-D** (UI-only · `Δ motor = 0` · `Δ contrato = 0` · sin migración)

**Producto:** `V2.88.104-beta` · **Package:** `2.11.104-beta` · **AsOf:** 2026-10-10. **Sin migración nueva** (Alembic head sigue `052_top3_opportunities`). Los 9 CLIs DÍA-D `v2_89`…`v2_97` sellan `2.11.104-beta` junto al `package.json` (guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py)).

> **Nota de árbol (honesta).** Este sello **no** mueve `packages/py/**` (`git diff --name-only -- packages/py` **vacío**): es UI + tests + higiene E2E + tooling dev más el `meta.bump`. El único cambio fuera de `apps/web/**`/`docs/**` es el sello declarado (`meta.bump`) de los 9 CLIs DÍA-D. `replay-repro` debe seguir **`REPRODUCIDO`** con la huella `1E3ADAC2…` para confirmarlo por CI.
> **Origen.** Cierra el hueco confirmado en la [auditoría operativa diaria §5](../../auditoria-operativa-diaria-entrada-salida-dia-d-2026-10-08.md): desde la operación de AUTO **no** había camino a la **estrategia/indicadores ganadores** que sustentan esa señal ni al **verificador DÍA-D bajo demanda** del Laboratorio. Ese es el slice **`S5`**.

**Base:** [`evidence/v2.88.103/README.md`](../v2.88.103/README.md) (trazabilidad financiera de la oportunidad + materialización durable + protocolo longitudinal PAPER + UI AUTO).
**Cita POST-TAG.** **Tag anotado `v2.88.104-beta`:** **PENDIENTE de completar** (objeto → commit + `Release tag CI` `VERDE`/`ROJO` + `replay-repro`) tras el run de CI del tag.

## 1. Cambios (por bloque)

| # | Bloque | Qué demuestra | Implementación |
| --- | --- | --- | --- |
| 1 | **Helper puro + hook (`S5`)** | Desde la operación de AUTO se resuelve el **UUID del instrumento por ticker** (`getInstruments`), el **TOP #1 de Finalistas** (`getInstrumentStrategyTop`), los **indicadores** y la **razón** (`getStrategy` + `strategySlotToIndicatorLabels`/`readRecommendationReasons`). Fail-closed: hueco → «Sin dato todavía» (**nunca** `0`); fallo de lectura → «No disponible». | [`auto-operation-strategy.ts`](../../../../apps/web/src/features/auto/auto-operation-strategy.ts), [`use-auto-operation-strategy.ts`](../../../../apps/web/src/features/auto/use-auto-operation-strategy.ts) |
| 2 | **Regresión del helper** | Pruebas de la resolución por ticker y la **heurística de coincidencia** (igualdad por token completo). | [`auto-operation-strategy.test.ts`](../../../../apps/web/src/features/auto/auto-operation-strategy.test.ts) |
| 3 | **Tarjeta + CTA `Verificar D→hoy`** | `AutoOperationStrategyCard` muestra la estrategia/indicadores/razón que sustentan la señal y ofrece el CTA que entra la sesión DÍA-D LAB (`mode: 'auto'`) y navega a `diaDVerifyHref`. Conserva los `data-testid`; el story panel la consume. | [`auto-operation-strategy-card.tsx`](../../../../apps/web/src/features/auto-monitor/auto-operation-strategy-card.tsx), [`auto-operation-strategy-card.test.tsx`](../../../../apps/web/src/features/auto-monitor/auto-operation-strategy-card.test.tsx) |
| 4 | **Refactor DRY del lanzamiento DÍA-D** | `useDiaDVerifyLaunch` unifica el lanzamiento que estaba **DUPLICADO** en `auto-operation-story-panel.tsx` y `instrument-strategy-top-panel.tsx` (`enterSession` `mode:'auto'` + `setAdoption(candidata)` + `navigate(diaDVerifyHref)` + toast). Sin cambio de comportamiento. | [`use-dia-d-verify-launch.ts`](../../../../apps/web/src/features/trading/use-dia-d-verify-launch.ts), [`auto-operation-story-panel.tsx`](../../../../apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx), [`instrument-strategy-top-panel.tsx`](../../../../apps/web/src/features/backtests/instrument-strategy-top-panel.tsx) |
| 5 | **Heurística de coincidencia ENDURECIDA** | `resolveAutoOperationStrategyMatch` pasa de **CONTENCIÓN** sobre tokens normalizados (falso positivo: sello `ma` contenido en `smacrossover` se declaraba `same`) a **IGUALDAD POR TOKEN COMPLETO** (`same`/`differs`/`unknown`); `same` solo con emparejamiento real. | [`auto-operation-strategy.ts`](../../../../apps/web/src/features/auto/auto-operation-strategy.ts) |
| 6 | **Honestidad UI** | `rank != 1` se declara **explícitamente**; las razones se listan completas (hasta 5); y **'carga ≠ hueco'**: durante la carga **NO** se declara un falso «Sin dato todavía» (se muestra «Cargando...»); error de lectura ⇒ «No disponible». | [`auto-operation-strategy-card.tsx`](../../../../apps/web/src/features/auto-monitor/auto-operation-strategy-card.tsx), [`auto-operation-story-panel.test.tsx`](../../../../apps/web/src/features/auto-monitor/auto-operation-story-panel.test.tsx) |
| 7 | **Higiene E2E + mock de rutas** | Specs mock/integrado del puente; el integrado limpia en `afterAll` el `strategy-top` **global** sembrado (`DELETE`) sin cambiar aserciones. | [`gp-e2e-s5-auto-dia-d-bridge-mock.spec.ts`](../../../../apps/web/e2e/gp-e2e-s5-auto-dia-d-bridge-mock.spec.ts), [`gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts`](../../../../apps/web/e2e/gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts), [`e2e-mock-routes.ts`](../../../../apps/web/e2e/helpers/e2e-mock-routes.ts) |
| 8 | **CI `S5`** | Filtros del puente `S5` en los jobs `playwright (mock E2E)` e integrado. | [`.github/workflows/release-tag-ci.yml`](../../../../.github/workflows/release-tag-ci.yml) |
| 9 | **Tooling dev** | `seed_auto_cycle_for_ui.py` siembra/limpia un ciclo AUTO durable + TOP en la BD **dev** (idempotente, `--cleanup`), **FUERA** de `apps/api-python` y `packages/py`. | [`scripts/dev/seed_auto_cycle_for_ui.py`](../../../../scripts/dev/seed_auto_cycle_for_ui.py) |
| Bump | — | `package.json` (`2.11.104-beta`) + `meta.bump` de `v2_89`…`v2_97`. | [`test_dia_d_bump_guard.py`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) |

## 2. Reglas que NO cambian

- **Motor intacto.** `Δ motor = 0`: sin motor, sin worker, sin umbrales, sin Alembic, sin `contract:gen`, sin tocar `packages/py/**` (`git diff --name-only -- packages/py apps/api-python` **vacío** antes del bump).
- **Contrato HTTP sin cambio.** `contract:check` **OK**; no se regenera el contrato (`contract:gen`).
- **`UNKNOWN ≠ 0` y carga ≠ hueco.** Un dato ausente se rotula «Sin dato todavía»; **jamás** se colapsa a `0` ni a un veredicto afirmado. Mientras **carga**, se rotula «Cargando...» (no se finge hueco).
- **`ranking ≠ decisión`.** La tarjeta **no** recalcula ranking ni score: lee el TOP #1 tal cual y, si `rank != 1`, lo **declara**.
- **Sin `CONFIRMED`.** La verificación DÍA-D sigue siendo el verificador ya existente del Laboratorio; este sello **no** emite confirmación reservada.

## 3. Verificación (local)

- `pnpm --filter @bolsa/web exec tsc --noEmit` → **OK** (exit 0).
- `pnpm --filter @bolsa/web exec eslint src` → **0 errores** (23 avisos `react-hooks/exhaustive-deps` preexistentes).
- `pnpm --filter @bolsa/web exec vitest run` → **293 ficheros / 2060 tests verdes**.
- `pnpm --filter @bolsa/web run build` → **OK**.
- E2E **mock** `S5` (`gp-e2e-s5-auto-dia-d-bridge-mock.spec.ts`) → **2/2 verdes**.
- `pnpm --filter @bolsa/web run contract:check` → **OK**.
- `python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q` → **1 passed** (`2.11.104-beta`).
- **`Δ motor = 0`**: `git diff --name-only -- packages/py apps/api-python` → **vacío** (antes del `meta.bump`).

## 4. Verificación real en navegador

Ciclo dev sembrado **`cyc-ui-970fde76031a`** (ruta `/auto/operar/operacion/cyc-ui-970fde76031a`), instrumento **ACS** (UUID `cmtzslah50007xn9c7ftx7y4l`):

- **Tarjeta** «Estrategia que sustenta la señal»: TOP `#1 SMA exit sim` · indicador `SMA` · **2 razones** · sello del ciclo `sma_crossover` ⇒ **«Coincide»**.
  ![Tarjeta de estrategia S5](./s5-auto-strategy-card.png)
- **CTA «Verificar D→hoy»** ⇒ navega a `/backtests?tab=run&instrumentId=cmtzslah50007xn9c7ftx7y4l&focus=detail&verify=1` con la sesión LAB precargada.
  ![Verificador DÍA-D desde AUTO](./s5-dia-d-verify.png)
- **Sin TOP**: declara «Sin dato todavía: no hay Finalistas (TOP) para este valor» y **deshabilita** el CTA.

**Artefactos.** `s5-auto-strategy-card.png`, `s5-dia-d-verify.png` (este directorio).

## 5. Qué no cambia / deuda declarada

- **Motor de decisión/ejecución**, worker, umbrales, Alembic (head `052_top3_opportunities`), `contract:gen`, contrato HTTP y esquema.
- **`P4-3`** (medición por artefacto CLI, no en vivo) sigue **abierto**.
- **Deuda PARKED FASE 2 (`F2-3`/`F2-4`)** sigue **abierta**.
- **E2E integrado `opt-in`** (un `skipped` **no** certifica).
- **`23` warnings `react-hooks/exhaustive-deps`** (`eslint`, **0 errores**): preexistentes, ajenos a este sello.
- **Tag `unsigned`.**
