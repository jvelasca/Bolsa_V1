# Evidencia `v2.88.54-beta` — `UI`: **Auditoría UI / accesibilidad (15 rutas)** (críticos a 0)

**Objeto:** el **siguiente chat, un auditor externo, o un Cursor distinto**. No es el historial.

**Producto:** `V2.88.54-beta` · **Package:** `2.11.54-beta` · **AsOf:** 2026-10-05 · **Nature:** `UI` · **Fase:** `UI AUDIT` · **Δ AUTO decision/execution motor = 0**.

**Schemas:** sin cambios (`dia-d-multi-band-v1`, `dia-d-thesis-exit-v5`, `dia-d-multi-cycle-ledger-v7`, `dia-d-thesis-stop-sequences-v2`). **Alembic:** head `048_journal_entry_dedupe_key` — **SIN migración**. **Contrato HTTP:** **sin cambio** (`contract:check` OK).

**Padre:** [`v2.88.53`](../v2.88.53/README.md) (tag → `c5e6354c`, `Release tag CI` [`37323748100`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37323748100) VERDE) → [`v2.88.52`](../v2.88.52/README.md) → [`v2.88.51`](../v2.88.51/README.md).

**Decisión de alcance (declarada).** Se abre sello por mandato explícito: **«eleva la versión y auditar toda la parte UI»**. `v2.88.53` se selló antes (gates + tag + CI + Release) y **después** se abrió `2.11.54-beta` para esta auditoría. El sello **no** añade funcionalidad: **corrige accesibilidad/estructura** en frontend y deja **un** hallazgo abierto declarado (`heading-order`, best-practice). **NO** toca motor, contrato HTTP, migraciones ni el pipeline `DÍA-D`.

---

## 0. Qué añade este sello (y qué NO)

Auditoría de UI ejecutada con **navegador real** (`axe-core 4.10.2` inyectado sobre `vite dev`) en las **15 rutas de nivel 1**, más sondas de texto (`undefined`/`NaN`/`null`) y verificación de *landmarks*/jerarquía. Resultado: **3 críticos y 7 reglas serias corregidas** (detalle completo y falsable en [`docs/engineering/auditoria-ui-v2.88.54-2026-10-05.md`](../auditoria-ui-v2.88.54-2026-10-05.md)).

1. **Críticos a 0:** `button-name` ×2 (botones *icon-only* sin nombre en `/screeners`) y `select-name` ×1 (`/screeners`, `/alerts`) → `title`/`aria-label` explícitos.
2. **`nested-interactive` a 0** (`serious`, **506 nodos**: 303 en `/instruments`, 203 en `/trading`): filas `div[role="button"]` con controles focusables dentro y pestaña de gráfico `div[role="button"]` con botón de cerrar dentro → interactividad redundante eliminada conservando la vía de teclado.
3. **`landmark-one-main` + `region` a 0** en `/trading` (`region` afectaba a **200 nodos**): la rama de Trading montaba `<div>`, ahora `<main>`. El efecto colateral (`landmark-complementary-is-top-level` por el `<aside>` del rail de dibujo) se cierra en el mismo sello (`<aside>` → `<div>`); `/trading` queda **0 violaciones**.
4. **`page-has-heading-one` a 0** (10 rutas): el título de página pasa a `<h1>` en las 9 vistas que lo marcaban como `<h2>`; en `/trading` se añade `<h1 class="sr-only">Trading</h1>`.
5. **`link-in-text-block` a 0** (`serious`, 7 nodos): enlaces de prosa con subrayado permanente (contraste enlace/contexto 1.17:1 < 3:1 exigido).
6. **`color-contrast` a 0** (`serious`, 25 nodos): se retira la **opacidad apilada** sobre `--bolsa-muted-foreground` (`/55`…`/90`, `opacity-60/70`) que bajaba el texto meta de 8–12 px a 2.72–4.36:1. El token de tema **no** se toca (ya cumple ≈6:1).

**NO** toca el motor, los umbrales, `TOP_N`, la allocation ni las costuras de decisión. **NO** cambia el contrato HTTP. **NO** re-mide `DÍA-D`. **NO** implementa `PortfolioDecision` (`UI52-02`) ni la navegación global (`UI52-04`).

---

## 1. Afirmaciones falsables (cada una con su forma de romperse)

| # | Afirmación | Cómo se rompe (falsación) | Evidencia |
| --- | --- | --- | --- |
| **1** | **Cero `critical`.** Ninguna de las 15 rutas emite reglas `critical` de `axe`. | Que `axe.run` devuelva cualquier regla con `impact === 'critical'`. | §2; informe §1–§2 (F1, F2). |
| **2** | **`nested-interactive` a 0.** Ninguna fila/pestaña anida controles focusables. | Que `axe` vuelva a reportar `nested-interactive` con `Element has focusable descendants`. | §2; informe §2 (F3). |
| **3** | **Un solo `<main>` visible por ruta y `region` a 0** en `/trading`. | Que `document.querySelectorAll('main').length > 1` o que reaparezca `region`. | §2 (diagnóstico `main = 1` en las 15 rutas); informe §2 (F4). |
| **4** | **`h1` en las 15 rutas.** Cada ruta expone exactamente un `h1` de página. | Que una ruta no tenga `h1` (⇒ `page-has-heading-one`). | §2 (diagnóstico `h1` por ruta); informe §2 (F5). |
| **5** | **`color-contrast` a 0 sin tocar el tema.** El texto meta vuelve a ≥4.5:1 retirando opacidad apilada, no cambiando tokens. | Que `axe` reporte `color-contrast`, o que el diff toque `apps/web/src/index.css` en los tokens de color. | §2; informe §2 (F7). |
| **6** | **`link-in-text-block` a 0.** Los enlaces de prosa llevan subrayado permanente. | Que `axe` reporte un enlace con `insufficient color contrast … with the surrounding text`. | §2; informe §2 (F6). |
| **7** | **`heading-order` es el único hallazgo abierto, y es best-practice `moderate`.** | Que aparezca cualquier regla `critical`/`serious`, o un hallazgo `moderate` distinto de `heading-order`. | §2; informe §3 (D1). |
| **8** | **`Δ motor = 0`.** Ningún fichero de motor, umbral o contrato. | Que el diff toque motor/umbrales, o que `contract:check` no coincida. | §2 (`contract:check OK`); informe §6. |
| **9** | **Sin fugas de valor en la UI.** Ninguna ruta pinta `undefined`/`NaN`/`null` de JavaScript. | Que la sonda de texto encuentre `undefined`/`NaN`/`null` no-copy. | informe §1 (única coincidencia = copy `null-if-incomplete`). |

---

## 2. Verificación (gates)

| Gate | Resultado |
| --- | --- |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **passed** (`meta.bump` de `v2_89`…`v2_97` == `package.json` `2.11.54-beta`) |
| `node --test scripts/lib/window-forward.test.mjs` | **25 passed / 0 fail** |
| `@bolsa/shared` build (`tsc`) | limpio |
| `@bolsa/shared` `vitest` | **810 passed · 1 todo** (`97` ficheros) |
| `@bolsa/web` `vitest` | **1386 passed** (`241` ficheros) |
| `@bolsa/web` `typecheck` (`tsc -b --noEmit`) | limpio |
| `@bolsa/web` `lint` | **0 errores** (`23` warnings pre-existentes) |
| `@bolsa/web` `contract:check` | **OK** — `openapi.json`/`schema.d.ts` coinciden |
| Barrido `axe-core 4.10.2` (15 rutas, navegador real) | **0 `critical` · 0 `serious`**; `heading-order` (`moderate`, 1 nodo) en 11 rutas |

> **Nota de método (auditable).** Durante el sellado se detectó una tanda de barrido **no válida** (resultado idéntico en las 15 rutas mientras la suite `vitest` corría en la misma máquina: el DOM se medía a medio montar). Se descartó y se repitió el barrido **con diagnóstico de `main`/`h1` por ruta**, aceptando solo medidas con `main = 1` y `h1` correcto. Es exactamente el modo de fallo que un auditor debe poder reproducir.

---

## 3. Los arreglos, en detalle

Ver el informe completo [`auditoria-ui-v2.88.54-2026-10-05.md`](../auditoria-ui-v2.88.54-2026-10-05.md) §2, con el HTML literal de cada nodo infractor, la regla `axe`, el `impact` y el ratio de contraste medido. Resumen por fichero:

- **Estructura/landmarks:** `platform-shell.tsx` (rama Trading → `<main>` + `<h1 class="sr-only">`), `chart-drawing-sidebar.tsx` (`<aside>` → `<div>`).
- **Interactividad anidada:** `instruments-page.tsx` (filas sin `role="button"`/`tabIndex`), `charts-zone.tsx` (pestaña = dos botones hermanos).
- **Nombre accesible:** `trackers-panel.tsx` (`aria-label` en ejecutar/eliminar), `scan-runner-form.tsx` y `signal-alerts-section.tsx` (`aria-label` en los `<select>` de preset/guardada).
- **`h1` de página:** `dashboard-page.tsx`, `backtests-page.tsx`, `instruments-page.tsx`, `accounts-page.tsx`, `screeners-page.tsx`, `alerts-page.tsx`, `tax-report-page.tsx`, `confirm-content.tsx`, `history-page.tsx`.
- **Contraste (quitar opacidad apilada):** `cabin-visual.ts`, `operator-cabin-ui.tsx`, `trading-status-bar.tsx`, `trading-app-threads.tsx`, `lists-tab/list-carousel.tsx`, `instruments-page.tsx`, `instruments-hub-filter-bar.tsx`, `backtests/strategy-filter-carousel.tsx`.
- **Distinción de enlaces de prosa (subrayado):** `screeners-page.tsx`, `research-page.tsx`, `tax-report-page.tsx`, `operational-console-page.tsx`.

---

## 4. Límites declarados (NO se cierran aquí)

- **`heading-order` (`moderate`, best-practice)** en 11 rutas: la página ya tiene `h1`, pero el primer encabezado de tarjeta es `h3` (salto de `h2`). Remediación acotada: promover ese primer encabezado a `h2` (un nodo por ruta). Ver informe §3 (D1).
- **`23` warnings `react-hooks/exhaustive-deps`**: pre-existentes; deuda técnica declarada (informe §3, D2).
- **`UI52-02` (`PortfolioDecision`)**: sigue abierta (backend/contrato).
- **`UI52-04` (navegación global)**: sigue abierta (objetivo post-1.0).
- **`aria-*` de sesiones anteriores** (`aria-hidden-focus`, `aria-prohibited-attr`, `aria-allowed-attr`, `aria-required-children`): corregidos en el barrido previo a este sello y **re-verificados** aquí (no reaparecen).
- **NO** se re-mide `DÍA-D`: las cifras OOS de `v2.88.51`/`v2.88.50` se **heredan y citan**.

---

## 5. Cómo se reproduce

```bash
# 1) Guard backend de versión (meta.bump == package.json).
uv run --no-sync python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q

# 2) Freeze de la ventana.
node --test scripts/lib/window-forward.test.mjs

# 3) Shared + Web.
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared test
pnpm --filter @bolsa/web test
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web lint
pnpm --filter @bolsa/web contract:check
```

```js
// 4) Auditoría de accesibilidad (navegador real, con la app levantada).
const s = document.createElement('script');
s.src = 'https://cdn.jsdelivr.net/npm/axe-core@4.10.2/axe.min.js';
document.head.appendChild(s);
const r = await window.axe.run(document, { resultTypes: ['violations'] });
console.table(r.violations.map(v => ({ id: v.id, impact: v.impact, nodes: v.nodes.length })));
// Diagnóstico de landmarks por ruta (debe dar main = 1 y un solo h1):
({ mains: document.querySelectorAll('main').length,
   h1: [...document.querySelectorAll('h1')].map(h => h.textContent.trim()) })
```

**No** se reproduce el pipeline `DÍA-D` en este sello (declarado): las cifras OOS se **citan** de `v2.88.50`/`v2.88.51`.

---

## 6. Sello

- **Añadidos:** `docs/engineering/evidence/v2.88.54/README.md`, `docs/engineering/auditoria-ui-v2.88.54-2026-10-05.md`, `docs/engineering/entrega-auditoria-externa-mia-v2.88.54-2026-10-05.md`.
- **Modificados (46 ficheros en el commit funcional `425292fd`):** 28 ficheros de UI (`apps/web/src/**`, detalle en el informe §5), `packages/shared/src/cognitive/auto-operation-story.ts` (+ su test) — aserción de `Δ motor = 0`; 9 scripts `v2_89`…`v2_97` (`meta.bump`), `package.json` (`2.11.54-beta`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md` y los 3 documentos de auditoría.
- **`Δ AUTO decision/execution motor = 0`:** ningún fichero de motor tocado; el cambio vive en UI (JSX/atributos accesibles/clases), en el docstring del view-model AUTO y en documentación.
- **Freeze re-anclado** en `scripts/lib/window-forward.mjs` (commit `chore` `5a680084`, posterior al funcional porque `scripts/` no participa del pin): `commit` `425292fd`, `apps` `b5babdb2510c584ec11498e9f54852306c1359c7`, `packages` `95cb0d698a708635e0594a5c85bacfb0a7538c20`. Pin anterior (`v2.88.53-beta`, commit `2b7f1940`): `apps` `9fcd4452…` / `packages` `371105fc…`.
- **Tag:** `v2.88.54-beta` (anotado) — **cita POST-TAG** del `Release tag CI` (escrita en `main` **después** del tag) y del `GitHub Release`.

---

## 7. Cita del CI (POST-TAG)

> **Pendiente de escribir tras el tag** (ningún tag contiene su propio resultado de CI: límite estructural declarado, como en `v2.88.46`…`v2.88.53`). Se anotará aquí el `Release tag CI` del tag `v2.88.54-beta` y la URL del `GitHub Release`, junto con el resultado de `replay-repro` (`Δ motor = 0` confirmado por CI).
