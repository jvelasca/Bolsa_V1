# ADR-045: UI Contract 5.0 — Global User-First (jerarquía y gramática de operación)

**Estado:** Accepted (**implementado** en `v2.88.88-beta`, [UI REFACTOR 5.0](./../engineering/evidence/v2.88.88/README.md))
**Fecha:** 2026-10-08
**Contexto:** `v2.88.87-beta` cerró la primera etapa de simplificación de AUTO (estado humano, centro de actividad, «¿Por qué?», ficha universal, TOP3) y quedó certificada de punta a punta (`Δ motor = 0`, contrato HTTP sin cambio, head Alembic `052_top3_opportunities`). La [auditoría UI global](./../engineering/auditoria-ui-global-v2.88.87-2026-10-08.md) confirma que el problema ya no está dentro de AUTO: está en la **coherencia entre superficies** y en la **densidad** de la primera capa. AUTO expone siete puertas al mismo nivel, la HOME repite hechos, la `AdminRail` mezcla producto/administración/diagnóstico, no existe una insignia de modo ni una escalera universal de operación.

**Depende de:** [ADR-040](./040-user-information-architecture.md) · [ADR-044](./044-auto-workspace-information-architecture.md) · [ADR-019](./019-dual-universes-lab-vs-trading.md) · [ADR-041](./041-operational-coherence.md).
**Congela:** [UI Contract 5.0](./../engineering/spec-ui-contract-5-0-2026-10-08.md).

---

## 1. Decisión

La aplicación debe leerse como **una sola aplicación**, con un **único lenguaje operativo**. Se eleva a contrato (reglas `UI5-01`…`UI5-20`):

1. **Jerarquía de navegación**
   - Cinco puertas L1 **intactas** (Hoy · Mercado · Cartera · Asesor · Laboratorio); AUTO **no** es L1 (ADR-040).
   - **Nav visible de AUTO = `Resumen · Operar · Cartera · Actividad`**; `Riesgo · Análisis · Sistema` pasan bajo **«Más información»**. Las rutas `/auto/riesgo`, `/auto/analisis`, `/auto/sistema` **no cambian** (siguen siendo compartibles); sólo cambia la jerarquía visual, no la topología.
   - **HOME de AUTO = cockpit**: cada hecho se pinta una sola vez; «¿Qué puedo hacer?» se reserva a acciones del usuario.
   - `AdminRail` se agrupa en **Producto / Administración / Diagnóstico**; «Consola avanzada» se conserva bajo diagnóstico/avanzado.
2. **Gramática de la operación**
   - **Escalera universal**: `Orden preparada → Orden enviada → Esperando ejecución → Ejecución parcial/completada → Posición creada → Posición cerrada`. Nunca se salta de orden a posición.
   - **Insignia de modo obligatoria** por operación: `AUTO` / `SEMI` / `MANUAL` (+ `LIVE` cuando exista), con el canal `SIMULADO`/`LIVE`; nunca se deduce.
   - Heredados y elevados a global: `Precio aplicado ≠ posición materializada`, `Ranking ≠ decisión`, **Cartera única** (`AUTO / Cartera` es vista de la misma cuenta).
3. **Estados y lenguaje**
   - **«Sin dato todavía»** es el estado oficial del dato ausente; prohibido `0`/`—`/`N/A`/`UNKNOWN` para ese significado.
   - Cuatro tonos: `CONFIRMADO` · `PARCIAL/PENDIENTE` · `SIN DATO TODAVÍA` · `BLOQUEADO` (solo con evidencia).
   - **`UNKNOWN ≠ 0`** elevado a contrato global.
   - **Acción ≠ Navegación ≠ Información**; **un término = un significado** ([domain-language](../domain-language.md) es la autoridad).

---

## 2. Relación con ADR-040 y ADR-044 (invariantes)

- **ADR-040 no se reabre:** las cinco puertas L1 y `/mesa` como aterrizaje siguen vigentes; AUTO sigue sin ser una sexta puerta L1.
- **ADR-044 no se reabre en su topología:** las siete secciones de `/auto/*` siguen existiendo con las mismas rutas, roles y jerarquía `h1/h2/h3`; este ADR **sólo** cambia la **jerarquía visible** de la sub-navegación (cuatro puertas + «Más información»).
- Los principios de ADR-044 (AUTO **compone** superficies por enlace, no las reimplementa; `<main>` único; `Δ motor = 0`) permanecen.

---

## 3. Alcance y naturaleza

- **Sólo presentación, jerarquía, vocabulario y estados.** No toca motor, worker, umbrales, `TOP_N`, contrato HTTP ni Alembic.
- **`Δ motor = 0`** por construcción.
- La **implementación** de `UI5-01`…`UI5-20` es un slice posterior (**UI REFACTOR 5.0**); este ADR y la spec asociada **congelan**, no implementan.

---

## 4. Consecuencias

- **Docs:** [UI Contract 5.0](./../engineering/spec-ui-contract-5-0-2026-10-08.md), [auditoría UI global](./../engineering/auditoria-ui-global-v2.88.87-2026-10-08.md), este ADR, [domain-language](../domain-language.md) §4.2 (actualizado), `CURRENT_SYSTEM.md` y `CHANGELOG.md`.
- **Implementación (slice posterior):** `auto-nav.ts`/`auto-workspace-layout.tsx` (nav visible), `auto-home-page.tsx` (cockpit sin duplicidades), `admin-rail.tsx` (tres grupos), insignia de modo en `operations-panel.tsx`/ficha, copy del TOP3 en `auto-top3-panel.tsx`, y primer nivel de `auto-riesgo-page.tsx`.
- **Deuda declarada que NO cierra este ADR:** `PortfolioDecision` durable; traza de materialización SIM; certificación `axe` de la fase de implementación.
- **Ninguna pantalla se borra** antes de que su sustituto esté verde; el refactor es aditivo.

---

## 5. Freeze (heredado, intacto)

Confirm = firma · `PAPER_D_EXECUTE` off · AUTO off · `Ranking ≠ BUY` · `TOP_N ≠ DECISIÓN` · `SALIDA ≠ LIQUIDACIÓN` (plegada) · LLM no ejecuta · LAB ≠ TRADING · `CONFIRMED` NO se emite · `UNKNOWN ≠ 0`.
