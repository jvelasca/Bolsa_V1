# Evidencia `v2.88.129-beta` — cierre de `heading-order` en las superficies L1 (deuda `axe` de la UI 6.x): `CardTitle` con nivel explícito + primer encabezado a `h2`, gate unitario durable nuevo y barrido axe ampliado

> **Bump:** `2.11.128-beta` → **`2.11.129-beta`** (`package.json` + `meta.bump` del CLI OOS `v2_87`, de los 9 CLIs `v2_89`…`v2_97` y del certificador `v2_98`; guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) verde).
>
> **Naturaleza:** incremento **solo de `apps/web/**` + tests** (marcado/semántica HTML + a11y + tests) — **`Δ motor = 0`**, **`Δ decisión = 0`**, **`Δ contrato HTTP = 0`** · **SIN migración** (head `053_dia_d_cycle_verifications`). **Representación visual idéntica** (los mismos `className`; solo cambia el *tag* semántico del encabezado). Tag **unsigned**.
>
> **Base:** `v2.88.128-beta`.

---

## 1. `heading-order` CERRADO — `CardTitle` con `level` opcional + promoción a `h2`

**Antes:** la regla `heading-order` de axe (best-practice) aparecía en **11 rutas L1** (deuda declarada desde `v2.88.54`): el `<h1>` de la página colgaba directamente de un `CardTitle` renderizado como `h3` ⇒ **salto `h1 → h3`**.

**Ahora** ([`card.tsx`](../../../../apps/web/src/components/ui/card.tsx)):

- `CardTitle` gana la prop **opcional** `level` (`CardTitleLevel = "h2"|"h3"|"h4"|"h5"|"h6"`, **default `h3`** ⇒ **retrocompatible** con las superficies existentes; `h1` se excluye a propósito porque es único por página y se escribe inline en ella).
- Las **8 rutas heredadas** que saltaban `h1 → h3` promocionan su primer encabezado a `h2`:
  - [`dashboard-page.tsx`](../../../../apps/web/src/features/dashboard/dashboard-page.tsx) (`:96`, `:321`, `:552`),
  - [`account-detail-panel.tsx:276`](../../../../apps/web/src/features/accounts/account-detail-panel.tsx),
  - [`alerts-page.tsx:154`](../../../../apps/web/src/features/alerts/alerts-page.tsx),
  - [`tax-report-page.tsx:233`](../../../../apps/web/src/features/fiscal/tax-report-page.tsx),
  - [`screeners-hub.tsx:488`](../../../../apps/web/src/features/screeners/screeners-hub.tsx),
  - [`operational-console-sections.tsx:526`](../../../../apps/web/src/features/operational-console/operational-console-sections.tsx),
  - [`auto-operation-story-panel.tsx:363`](../../../../apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx),
  - [`auto-monitor-header.tsx:48`](../../../../apps/web/src/features/auto-monitor/auto-monitor-header.tsx),
  - [`backtests-page-run-tab.tsx:615`](../../../../apps/web/src/features/backtests/backtests-page-run-tab.tsx) (usa `CardTitle level="h2"`),
  - [`instrument-detail-page.tsx:293`](../../../../apps/web/src/features/instruments/instrument-detail-page.tsx).

**Representación visual idéntica:** no se cambia ningún `className`; solo el *tag* semántico del encabezado.

---

## 2. Gate unitario durable NUEVO (Frontend CI, NO opt-in)

[`heading-order.test.tsx`](../../../../apps/web/src/test/heading-order.test.tsx) monta **9 variantes** de página (dashboard, accounts, alerts, fiscal, operational-console, `auto-monitor?mode=operation`, `auto-monitor?mode=current`, screeners y `/instruments/:id`) y asierta, sobre el **orden documental**:

1. exactamente **un `<h1>`** por página;
2. **ningún salto** de nivel (`level[i] - level[i-1] <= 1`);
3. el **primer encabezado es `h1`**.

La **guarda de lista** `HEADING_GUARD` obliga a declarar de forma explícita toda página nueva; `HEADING_GUARD_EXCLUDED` documenta las exclusiones —aquí `/backtests`— y una guarda adicional verifica que ninguna ruta esté a la vez cubierta y excluida. El test corre en **vitest** (Frontend CI), **no** es opt-in.

---

## 3. Barrido axe ampliado a las 8 rutas heredadas

[`gp-e2e-ui5-0-axe-touched-routes-mock.spec.ts`](../../../../apps/web/e2e/gp-e2e-ui5-0-axe-touched-routes-mock.spec.ts) suma a `ROUTES` las **8 rutas heredadas** (`/overview`, `/backtests`, `/accounts`, `/screeners`, `/alerts`, `/fiscal`, `/operational-console`, `/auto-monitor`) reutilizando los `install*Mocks` existentes, con un nuevo `expectMain` por caso (shell keep-alive de `/backtests`) y `expectNoHeadingOrderViolations` (**0** violaciones `heading-order`).

---

## 4. 2 arreglos a11y EXTRA (violaciones `serious` preexistentes)

El error boundary / keep-alive **ocultaba** dos violaciones `serious` preexistentes que el barrido ampliado aflora:

- **`color-contrast`** — [`backtest-wizard-advanced-options.tsx:66`](../../../../apps/web/src/features/backtests/backtest-wizard-advanced-options.tsx): se **quita** `opacity-80`, que bajaba el contraste a `#737f8d`/`#131923` = **4.32 < 4.5**.
- **`scrollable-region-focusable`** — [`tax-report-page.tsx:70-74`](../../../../apps/web/src/features/fiscal/tax-report-page.tsx) y `:141-145`: los `div.overflow-x-auto` de las **dos** tablas ganan `role="region"` + `aria-label` + `tabIndex={0}`.

**Mocks E2E para `/fiscal`.** Nuevo `taxReportMock()` ([`e2e-mock-routes.ts:415-479`](../../../../apps/web/e2e/helpers/e2e-mock-routes.ts)) + rama `if (path.endsWith("/tax-report"))` (`:917-919`): sin ellos `/fiscal` caía al default `{data:[]}` y **reventaba**.

---

## 5. Verificación (local)

| Comprobación | Resultado |
|--------------|-----------|
| Spec axe COMPLETO, todas las rutas + command palette (`E2E_RUN=1 pnpm e2e -- gp-e2e-ui5-0-axe`) | **29 passed** (incl. `expectNoHeadingOrderViolations` ⇒ **0** `heading-order`) |
| Gate unitario ([`heading-order.test.tsx`](../../../../apps/web/src/test/heading-order.test.tsx)) | **10 passed** |
| `pnpm --filter @bolsa/web typecheck` | **OK** |
| `pnpm --filter @bolsa/web lint` | **0 errors / 23 warnings** (preexistentes) |
| `pnpm --filter @bolsa/web test` | **299 ficheros / 2194 passed** |
| Guardián de bump (`uv run --no-sync python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q`) | **1 passed** (`2.11.129-beta`) |
| `Δ motor` / `Δ decisión` / `Δ contrato HTTP` | **0 / 0 / 0** |
| `alembic heads` | `053_dia_d_cycle_verifications` (**sin migración**) |

---

## 6. Límites declarados (sin fabricar) + falsabilidad

- **`/backtests` fuera del gate unitario:** su modelo de página compone el hub entero (asistente + jobs + DÍA-D + keep-alive) y no se monta en jsdom; queda **cubierto** por el barrido **axe E2E**, donde sí se añade a `ROUTES`.
- **El barrido axe sigue siendo `mock-only`:** el E2E **integrado** (contra stack real) **no** se ejercita en esta pasada. La deuda `axe` de la UI 6.x se **reduce** al cerrarse `heading-order`, pero la certificación `axe` sigue **con mocks**.
- **Cambio solo de `apps/web/**`:** marcado/semántica HTML + a11y + tests; sin tocar motor, decisión, contrato HTTP ni migración.

**Falsabilidad.**

- Si una página L1 volviera a saltar de nivel (o tuviera 0 / 2 `h1`), el gate unitario [`heading-order.test.tsx`](../../../../apps/web/src/test/heading-order.test.tsx) **rompe**.
- Si el sondeo axe se corriera con las 8 rutas heredadas y apareciera una violación `heading-order`, `expectNoHeadingOrderViolations` **rompe**.
- Si se **añadiera** una página al censo sin declararla en `HEADING_GUARD` (o `HEADING_GUARD_EXCLUDED`), la guarda de lista **rompe**.

---

## 7. `Release tag CI` del sello — **FALLIDO** (SUPERADO por `v2.88.130`)

**Tag** `v2.88.129-beta` (anotado, unsigned) ⇒ objeto `b30e6bb0` ⇒ commit `51b368bf`. **Base:** `v2.88.128-beta`.

**`Release tag CI`:** [run **`38574943655`**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38574943655) — **`FAILED`** en el job **`playwright (mock E2E)`**, con el test literal:

```
[/backtests @móvil 390×844] · scrollable-region-focusable [serious] ×1 — Scrollable region must have keyboard access
```

sobre el nodo `.p-3.overflow-auto.pt-0`. El resto de jobs del run quedaron **verde** (incl. `playwright (integrated AUTO S5)`) y `certify` falló **por agregar el job rojo**.

**SUPERADO por `v2.88.130`:** [`../v2.88.130/README.md`](../v2.88.130/README.md) corrige la causa (a11y del contenedor de resultados scrolleable de backtests) y subsume este cierre con CI verde.

