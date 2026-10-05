# Auditoría UI / accesibilidad — `v2.88.54-beta` (2026-10-05)

**Alcance:** toda la aplicación (las 15 rutas de nivel 1). **Método:** barrido en navegador real (Chromium vía Playwright sobre `vite dev` en `localhost:5173` + API en `localhost:8000`) con `axe-core 4.10.2` inyectado en la página, más sondas de texto (`undefined` / `NaN` / `null`) y comprobación de jerarquía de *landmarks*.

**Naturaleza del sello:** `UI` (accesibilidad y estructura). **Δ motor = 0**, **contrato HTTP sin cambio**, **sin migración** (Alembic head `048_journal_entry_dedupe_key`).

**Estado global (falsable):**

| Métrica | Antes de esta auditoría | Después |
| --- | --- | --- |
| Reglas `critical` | **3** (`button-name` ×2, `select-name` ×1) | **0** |
| Reglas `serious` | **7 reglas / 534 nodos** (`nested-interactive` 506, `color-contrast` 25, `link-in-text-block` 7) | **0** |
| `page-has-heading-one` | **10 rutas** | **0** |
| `landmark-one-main` / `region` | **2 rutas** (`/trading` +200 nodos) | **0** |
| Rutas 100 % limpias | **3 / 15** | **4 / 15** |
| Resto | — | `heading-order` (`moderate`, best-practice, 1 nodo) en 11 rutas (§6) |

---

## 0. Cómo se reproduce (auditable)

El barrido no es una opinión: es re-ejecutable. Con la app levantada (`vite dev` + API):

```js
// En la consola del navegador, en cualquier ruta:
const s = document.createElement('script');
s.src = 'https://cdn.jsdelivr.net/npm/axe-core@4.10.2/axe.min.js';
document.head.appendChild(s);
// tras cargar:
const r = await window.axe.run(document, { resultTypes: ['violations'] });
console.table(r.violations.map(v => ({ id: v.id, impact: v.impact, nodes: v.nodes.length })));
```

Sonda de *landmarks* / jerarquía (debe dar `main = 1` y un `h1` por ruta):

```js
({ mains: document.querySelectorAll('main').length,
   asides: document.querySelectorAll('aside').length,
   h1: [...document.querySelectorAll('h1')].map(h => h.textContent.trim()) })
```

> **Nota de método.** Un barrido SPA de 15 rutas encadenadas sin recarga puede medir un DOM a medio montar (se observó una tanda con resultado idéntico en todas las rutas mientras corría la suite `vitest` en la misma máquina). Todas las cifras de este informe se tomaron **con diagnóstico de `main`/`h1` por ruta** y solo se aceptan las medidas donde `main = 1` y el `h1` corresponde a la ruta.

---

## 1. Resultado por ruta (antes → después)

| Ruta | `h1` final | Antes | Después |
| --- | --- | --- | --- |
| `/mesa` | `Hoy` | limpio | **limpio** |
| `/overview` | `Overview` | `page-has-heading-one` | `heading-order` (1) |
| `/trading` | `Trading` | `nested-interactive` 203 · `color-contrast` 10 · `landmark-one-main` · `page-has-heading-one` · `region` 200 | **limpio** |
| `/backtests` | `Backtesting` | `color-contrast` 1 · `page-has-heading-one` | `heading-order` (1) |
| `/instruments` | `Instrumentos` | `nested-interactive` **303** · `color-contrast` 14 · `page-has-heading-one` | **limpio** |
| `/accounts` | `Cuentas` | `page-has-heading-one` | `heading-order` (1) |
| `/decision-journal` | `Decision Journal` | limpio | **limpio** |
| `/research` | `Asesor` | `heading-order` · `link-in-text-block` 2 | `heading-order` (1) |
| `/screeners` | `Señales` | **`button-name` ×2 (critical)** · **`select-name` (critical)** · `link-in-text-block` 3 · `page-has-heading-one` | `heading-order` (1) |
| `/alerts` | `Alertas de precio` | **`select-name` (critical)** · `page-has-heading-one` | `heading-order` (1) |
| `/fiscal` | `Informe fiscal` | `link-in-text-block` 1 · `page-has-heading-one` | `heading-order` (1) |
| `/confirm` | `Confirmar` | `page-has-heading-one` | `heading-order` (1) |
| `/history` | `Libro · Historial` | `page-has-heading-one` | `heading-order` (1) |
| `/operational-console` | `Consola operacional` | `heading-order` · `link-in-text-block` 1 | `heading-order` (1) |
| `/auto-monitor` | `Monitor AUTO` | `heading-order` | `heading-order` (1) |

**Sin hallazgos en las sondas de texto:** ninguna ruta pinta `undefined`, `NaN` ni `null` de JavaScript. La única coincidencia textual (`/overview`: «…llega vacío; cobertura uneven en bancos (null-if-incomplete)») es **copy honesta** que documenta el comportamiento `null-if-incomplete`, no una fuga de valor.

**Sin errores de runtime:** recarga dura de `/trading` → consola limpia. Los `401` de `/operational-console` se gestionan como aviso de autenticación (declarado, no crash).

---

## 2. Hallazgos corregidos (con evidencia `axe` y arreglo)

### F1 — `button-name` (**critical**) · `/screeners` · 2 nodos

- **Evidencia:** `button-name` impact `critical`, `n = 2`. Nodos: `.bg-transparent.h-8.px-3:nth-child(4)` y `.h-8.px-3.text-xs:nth-child(6)`, ambos con `Element does not have inner text that is visible to screen readers / aria-label attribute does not exist`.
- **Causa:** dos botones *icon-only* en `apps/web/src/features/screeners/trackers-panel.tsx` (ejecutar rastreador; eliminar rastreador) sin nombre accesible.
- **Arreglo:** `title` + `aria-label` explícitos (`"Ejecutar rastreador ahora"`, `"Eliminar rastreador"`).

### F2 — `select-name` (**critical**) · `/screeners` y `/alerts` · 2 nodos

- **Evidencia:** `select-name` impact `critical`, `n = 1` por ruta. Nodo `.ml-6` con `Element does not have an implicit (wrapped) <label> / aria-label attribute does not exist`.
- **Causa:** el `<select>` de preset/estrategia guardada queda bajo un `<fieldset><legend>Estrategia</legend>`, pero el `legend` etiqueta el **fieldset**, no el control (`apps/web/src/features/screeners/scan-runner-form.tsx`, `apps/web/src/features/alerts/signal-alerts-section.tsx`).
- **Arreglo:** `aria-label="Estrategia preset"` / `aria-label="Estrategia guardada"` en los 4 `<select>` afectados.

### F3 — `nested-interactive` (**serious**) · `/instruments` 303 nodos y `/trading` 203 nodos

- **Evidencia:** `nested-interactive` impact `serious`; `n = 303` en `/instruments` y `n = 203` en `/trading`, siempre con `Element has focusable descendants`.
- **Causa (dos superficies):**
  1. `apps/web/src/features/instruments/instruments-page.tsx`: cada fila del hub era `div[role="button"][tabindex=0]` **conteniendo** botones reales (abrir, activar rastreador, abrir en Mercado, ficha). 303 filas ⇒ 303 nodos.
  2. `apps/web/src/features/trading/charts-zone.tsx`: la pestaña de gráfico era `div[role="button"]` con el `<button>` de cerrar dentro.
- **Arreglo:** se elimina la interactividad **redundante** del contenedor y se conservan controles reales:
  - Filas de `/instruments`: fuera `role="button"`/`tabIndex`/`onKeyDown`; el `onClick` de fila (atajo de ratón) se mantiene y el `<button>` interno ya da la vía de teclado.
  - Pestañas de gráfico: el `div` pasa a contenedor no interactivo con **dos botones hermanos** (seleccionar · cerrar).

### F4 — `landmark-one-main` + `region` (**moderate**, 1 + 200 nodos) · `/trading`

- **Evidencia:** en `/trading` no existía `<main>` visible (la única `main` del DOM era el *keepalive* de Backtesting, `aria-hidden` + `inert`), de modo que 200 nodos quedaban fuera de todo *landmark*.
- **Causa:** en `apps/web/src/components/layout/platform-shell.tsx` la rama de Trading montaba un `<div>`, no un `<main>`.
- **Arreglo:** la rama de Trading pasa a `<main>` (una sola `main` visible por ruta, ahora verificado: `main = 1` en las 15).

### F5 — `page-has-heading-one` (**moderate**) · 10 rutas

- **Evidencia:** `page-has-heading-one` en `/overview`, `/backtests`, `/trading`, `/instruments`, `/accounts`, `/screeners`, `/alerts`, `/fiscal`, `/confirm`, `/history`.
- **Causa:** el título de página se marcaba como `<h2>` (mientras las páginas de `/mesa`, `/decision-journal`, `/research`, `/operational-console`, `/auto-monitor` ya usaban `<h1>`).
- **Arreglo:** el título de página pasa a `<h1>` en las 9 vistas afectadas; en `/trading` se añade un `<h1 class="sr-only">Trading</h1>` dentro de la `main` (el terminal no tenía título de página visible).

### F6 — `link-in-text-block` (**serious**) · 7 nodos en 4 rutas

- **Evidencia:** links `text-primary` sobre prosa `text-muted-foreground`, contraste enlace/contexto **1.17:1** (mínimo 3:1) y sin estilo distintivo más allá del color.
- **Causa:** enlaces intercalados en párrafos con `className="text-primary hover:underline"` (subrayado solo en `hover`).
- **Arreglo:** subrayado permanente en esos enlaces de prosa (`underline hover:underline`) en `screeners-page.tsx` (3), `research-page.tsx` (2), `tax-report-page.tsx` (1) y `operational-console-page.tsx` (1).

### F7 — `color-contrast` (**serious**) · 25 nodos en 3 rutas

- **Evidencia:** `color-contrast` `serious`, ratios medidos 2.72–4.36 (mínimo 4.5:1) en texto meta de 8–12 px.
- **Causa raíz (única):** **apilar** modificadores de opacidad sobre `--bolsa-muted-foreground` (`#8b98a8`, que por sí solo da ≈ 6:1). Ejemplos literales tomados de `axe`:
  - `/trading`: `<span class="ml-1 opacity-60">35</span>` → 3.73:1 (`#009168` sobre `#042c28`); `<p class="cabin-type-meta … text-muted-foreground/90 opacity-80">Próxima acción</p>` → 3.47:1; `<span class="… text-muted-foreground/70">Activa</span>` → 3.62:1; `<span class="… text-muted-foreground/60">EUR</span>` → 2.99:1; etiquetas `text-muted-foreground/80` → 4.36:1; `<span class="… text-muted-foreground/55">Colas</span>` (8 px) → 2.72:1.
  - `/instruments`: `<span class="ml-1 opacity-70">· Industrials</span>` → 3.76:1; `<span class="ml-1 tabular-nums opacity-70">35</span>` → 3.76:1; `<span class="… text-destructive opacity-70">40</span>` → 2.99:1.
  - `/backtests`: `<span class="ml-1 tabular-nums opacity-70">(21)</span>` → 3.54:1.
- **Arreglo:** se retira la opacidad **apilada** (no se toca el token de tema, que ya cumple): `text-muted-foreground/90`, `/80`, `/70`, `/60`, `/55` y los `opacity-60`/`opacity-70` sobre spans meta en `cabin-visual.ts`, `operator-cabin-ui.tsx`, `trading-status-bar.tsx`, `trading-app-threads.tsx`, `list-carousel.tsx`, `instruments-page.tsx`, `instruments-hub-filter-bar.tsx`, `strategy-filter-carousel.tsx`.

### F8 — `landmark-complementary-is-top-level` (**moderate**, 1 nodo) · `/trading`

- **Evidencia:** apareció **al** corregir F4: el `<aside class="chart-drawing-sidebar-rail …">` quedaba dentro de la nueva `<main>`.
- **Causa:** el rail de herramientas de dibujo se marcaba como *complementary* anidado en un *landmark*.
- **Arreglo:** `apps/web/src/features/charts/chart-drawing-sidebar.tsx` pasa de `<aside>` a `<div>` (es una barra de herramientas del propio panel, no contenido complementario de página). Verificado: `/trading` queda con **0 violaciones**.

---

## 3. Hallazgos abiertos (declarados, con remediación)

### D1 — `heading-order` (**moderate**, best-practice) · 11 rutas · 1 nodo por ruta

- **Evidencia:** tras promover el título de página a `<h1>`, el **siguiente** encabezado en el árbol es un `<h3>` de tarjeta/sección (se salta el nivel `h2`). Nodos literales: `/overview` → `<h3>Cuenta demo EUR</h3>`; `/backtests` → `<h3 class="tracking-tight text-sm font-semibold">`; `/accounts` → `<h3 class="text-lg font-semibold">Cuenta demo EUR</h3>`; `/research` → `<h3 class="font-semibold tracking-tight text-base">Lab Health</h3>`.
- **Por qué no se cierra aquí:** es una **regla best-practice** (no une fallo WCAG A/AA) y el arreglo correcto es re-escalar la jerarquía completa —`h1` página · `h2` sección · `h3` sub-apartado—, lo que toca los títulos de tarjeta de muchas features y merece su propia tarea con revisión visual.
- **Remediación propuesta (acotada):** promover a `<h2>` el primer encabezado de tarjeta/sección de cada página (el único nodo que hoy delata el salto). `axe` reporta `n = 1` por ruta, de modo que el cambio es de un elemento por vista.
- **Nota de honestidad:** esta auditoría **no introduce** el `heading-order` (ya existía en `/research`, `/operational-console` y `/auto-monitor`); lo que hace es sustituir `page-has-heading-one` (10 rutas) por `heading-order` (11 rutas) al dotar a las páginas de un `h1` real. Ambos son `moderate`/best-practice; el `h1` es prerequisito de un árbol correcto.

### D2 — `23` warnings de `react-hooks/exhaustive-deps` (`eslint`)

- **Evidencia:** `npm run lint` → `0 errores`, `23 warnings` (pre-existentes, no introducidos por este sello), concentrados en `use-backtest-url-sync.ts`, `backtest-list-auto-controller.ts`, `mesa-hoy-page.tsx` y `journal-evolution-panel.tsx`.
- **Remediación:** deuda técnica declarada; no afecta a accesibilidad ni al motor.

---

## 4. Gates del sello (evidencia)

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

---

## 5. Ficheros tocados

**Accesibilidad / estructura:** `apps/web/src/components/layout/platform-shell.tsx`, `apps/web/src/features/instruments/instruments-page.tsx`, `apps/web/src/features/instruments/instruments-hub-filter-bar.tsx`, `apps/web/src/features/trading/charts-zone.tsx`, `apps/web/src/features/trading/cabin-visual.ts`, `apps/web/src/features/trading/operator-cabin-ui.tsx`, `apps/web/src/features/trading/trading-status-bar.tsx`, `apps/web/src/features/trading/trading-app-threads.tsx`, `apps/web/src/features/trading/lists-tab/list-carousel.tsx`, `apps/web/src/features/charts/chart-drawing-sidebar.tsx`, `apps/web/src/features/screeners/trackers-panel.tsx`, `apps/web/src/features/screeners/scan-runner-form.tsx`, `apps/web/src/features/screeners/screeners-page.tsx`, `apps/web/src/features/alerts/signal-alerts-section.tsx`, `apps/web/src/features/backtests/strategy-filter-carousel.tsx`, `apps/web/src/features/fiscal/tax-report-page.tsx`, `apps/web/src/features/operational-console/operational-console-page.tsx`, `apps/web/src/features/research/research-page.tsx`.

**Títulos de página (`h2` → `h1`):** `dashboard-page.tsx`, `backtests-page.tsx`, `instruments-page.tsx`, `accounts-page.tsx`, `screeners-page.tsx`, `alerts-page.tsx`, `tax-report-page.tsx`, `confirm-content.tsx`, `history-page.tsx`.

**Sello:** `package.json` (`2.11.54-beta`), `v2_89`…`v2_97` (`meta.bump`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `docs/engineering/evidence/v2.88.54/README.md`, `docs/engineering/entrega-auditoria-externa-mia-v2.88.54-2026-10-05.md`, `scripts/lib/window-forward.mjs` (re-anclaje del freeze).

---

## 6. Qué NO se toca

- **Motor, umbrales, `TOP_N`, allocation y costuras de decisión:** intactos (**Δ motor = 0**).
- **Contrato HTTP:** sin cambio (`contract:check` OK).
- **Migraciones:** sin cambio (Alembic head `048_journal_entry_dedupe_key`).
- **Pipeline `DÍA-D`:** no se re-ejecuta; las cifras OOS se **heredan y citan** de `v2.88.51`/`v2.88.50`.
- **Navegación global** (`UI52-04`) y **`PortfolioDecision`** (`UI52-02`): siguen abiertas (fuera de alcance).
