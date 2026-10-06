# ADR-044 — Espacio AUTO con sub-navegación propia (V2.88.55)

**Estado:** Accepted
**Fecha:** 2026-10-05
**Contexto:** `v2.88.52` → `v2.88.54` cerraron el modelo semántico de AUTO (spec [AUTO UI SEMANTIC MODEL 1.0](../engineering/spec-auto-ui-semantic-model-1-2026-10-05.md)), la operación única y una auditoría global de UI (accesibilidad/estructura a `0` críticos). El auditor externo (MIA) certificó la versión y pidió dejar de parchear componentes: diseñar la UI de AUTO como producto. Hoy AUTO no tiene navegación de producto: vive como un único botón `Monitor AUTO` en la `AdminRail` (`/auto-monitor`) con pestañas internas.

**Depende de:** [ADR-040](./040-user-information-architecture.md) · [ADR-041](./041-operational-coherence.md) · [ADR-042](./042-operating-excellence.md) · spec [AUTO UI REFACTOR 2.0](../engineering/spec-auto-ui-refactor-2-0-2026-10-05.md) · spec [AUTO UI SEMANTIC MODEL 1.0](../engineering/spec-auto-ui-semantic-model-1-2026-10-05.md).

---

## 1. Decisión

AUTO pasa a ser un **espacio de trabajo con sub-navegación propia** (`/auto/*`), con cinco secciones de producto:

```
AUTO
├── OPERAR    Oportunidades · Operaciones · Operación seleccionada
├── CARTERA   Posiciones · Órdenes · Historial · Cuentas
├── RIESGO    Riesgo abierto · límites · integridad financiera
├── ANÁLISIS  DÍA-D · Evidencia · Estrategias · Investigación
└── SISTEMA   Salud AUTO · Broker/ejecución · Reconciliación · Auditoría
```

Y dentro de una **operación** la lectura es narrativa y causal:

```
QUÉ PASÓ → POR QUÉ → QUÉ RIESGO TENÍA → QUÉ HIZO EL BROKER → QUÉ RESULTADO → ¿QUÉ ENSEÑA DÍA-D?
```

El principio rector es **resumen operativo arriba, causalidad técnica bajo demanda**.

## 2. Relación con ADR-040 (invariante)

- La arquitectura de usuario **global** de ADR-040 **no cambia**: `Hoy · Mercado · Cartera · Asesor · Laboratorio` siguen siendo las cinco puertas L1.
- AUTO **no** es una sexta puerta L1 y **no** aparece como L1 en la barra superior. Es un **espacio con alcance propio**, accesible desde la `AdminRail` (barra admin, no nav diaria) y desde la command palette.
- El espacio AUTO **compone** superficies ya existentes (Mesa, Mercado, Consola operativa, Laboratorio, Asesor) mediante deep-links; **no** las sustituye ni las duplica. Es una capa de lectura/agrupación de producto, no un motor nuevo.
- Cuando AUTO necesite una superficie que hoy vive en una puerta L1, la **enlaza** (`/mesa?view=…`, `/backtests?tab=…`, `/research`, `/history`), no la reimplementa.

## 3. Contrato de la sub-navegación

- Fuente única de labels/rutas en `apps/web/src/features/auto/auto-nav.ts` (unit-testable, sin React), espejo de [`daily-nav.ts`](../../apps/web/src/features/confirm/daily-nav.ts).
- La sub-navegación es **persistente** dentro del espacio: cambiar de sección no desmonta el shell.
- Cada ruta de sección expone **exactamente un `<h1>`** (título de página) y **un solo `<main>` visible** (el `<main>` lo aporta el `PlatformShell`; el layout de AUTO **no** anida otro `<main>`).
- La jerarquía de encabezados del espacio es `h1` página · `h2` sección · `h3` tarjeta (cierra el `heading-order` heredado de `v2.88.54`).
- La selección relevante (ciclo, día, ventana, símbolo) viaja en la **URL** (empezado en `v2.88.52`), de modo que una vista AUTO es compartible y sobrevive al cambio de sección.

## 4. Compatibilidad y refactor aditivo

- Rutas históricas (`/auto-monitor`) se conservan y siguen funcionando; el espacio nuevo es **aditivo**.
- `/auto` redirige a `/auto/operar` (sección por defecto).
- Ninguna pantalla existente se borra antes de que su sustituto esté verde.
- `Δ AUTO decision/execution motor = 0`: sin cambio de motor, umbrales, `TOP_N`, contrato HTTP ni migración Alembic.

## 5. Freeze (heredado, intacto)

Confirm = firma · `PAPER_D_EXECUTE` off · AUTO off · Ranking ≠ BUY · `TOP_N ≠ DECISIÓN` · `SALIDA ≠ LIQUIDACIÓN` (plegada) · LLM no ejecuta · LAB ≠ TRADING · `CONFIRMED` NO se emite.

---

## 6. Consecuencias

- Nuevos: `apps/web/src/features/auto/auto-nav.ts`, `apps/web/src/components/layout/auto-workspace-layout.tsx` y las páginas de sección; rutas `/auto/*` en `app.tsx`.
- Modificados: `admin-rail.tsx` (entrada `AUTO`), `command-registry.ts` (comandos de sección), `platform-shell.tsx`/`routes.ts` (tratamiento de `/auto` como workspace).
- Deuda declarada que **no** cierra este ADR: `PortfolioDecision` durable (`UI52-02`), contrato de explicación por `cycleId`, PIT institucional, Execution Analysis.
- Docs: este ADR + [spec AUTO UI REFACTOR 2.0](../engineering/spec-auto-ui-refactor-2-0-2026-10-05.md), `CURRENT_SYSTEM.md`, `CHANGELOG.md`.

---

## 7. Addendum `v2.88.62` — HOME como landing de `/auto`

**Estado:** Accepted (`2026-10-06`). **Complementa (no reabre)** las cinco secciones de §1.

- §4 decía «`/auto` redirige a `/auto/operar` (sección por defecto)». **Se sustituye** por: `/auto` monta una **HOME / cockpit** que responde en 5 s las cuatro preguntas del usuario básico (qué está haciendo AUTO · qué puede hacer · cuánto riesgo tiene · qué ha pasado) y **enlaza** a las cinco secciones.
- **LA HOME es aditiva**: `/auto/operar`, `/auto/cartera`, `/auto/riesgo`, `/auto/analisis` y `/auto/sistema` se conservan sin cambios de rol; `operar` deja de ser la sección «por defecto» pero sigue siendo la superficie de oportunidades/operaciones.
- La HOME **no** reimplementa ninguna superficie: compone por enlace (invariante de §2). El `<main>` sigue siendo único (lo aporta `PlatformShell`) y la HOME expone exactamente un `<h1>`.
- **No** cambia ADR-040: AUTO sigue sin ser una sexta puerta L1.
- **`Δ motor = 0`**, sin cambio de contrato HTTP, sin migración Alembic.
- Congelado en [spec AUTO UI REFACTOR 3.0](../engineering/spec-auto-ui-refactor-3-0-2026-10-06.md).
