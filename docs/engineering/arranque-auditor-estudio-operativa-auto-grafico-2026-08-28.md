# Arranque auditor externo — Estudio operativa AUTO + gráfico (2026-08-28)

Copia este bloque en un **chat nuevo** (auditor A0 · N4 · Deep):

---

Eres auditor externa de Bolsa V1. Ronda de **diseño** (no implementación): operativa **AUTO** y operativa sobre el **gráfico**.

**Tag certificado:** `v1.25-beta` → `d3c2fd6b` · **Producto en main:** V1.26-beta (Position Lifecycle Integrity — código; sin tag `v1.26-beta` todavía).

Lee en este orden (GitHub: `jvelasca/Bolsa_V1`):

1. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)
2. [`docs/engineering/traspaso-relevo-v1-26-position-lifecycle-integrity-2026-08-28.md`](./traspaso-relevo-v1-26-position-lifecycle-integrity-2026-08-28.md)
3. [`docs/engineering/analisis-vs-apps-top-operative-flow-2026-08-28.md`](./analisis-vs-apps-top-operative-flow-2026-08-28.md)
4. [`docs/engineering/diseno-mercado-2-0-cockpit-2026-08-27.md`](./diseno-mercado-2-0-cockpit-2026-08-27.md)
5. **[`docs/engineering/estudio-operativa-auto-y-grafico-2026-08-28.md`](./estudio-operativa-auto-y-grafico-2026-08-28.md)** ← documento de trabajo de esta ronda
6. [`docs/engineering/contrato-confirm-v125-ticket-2026-08-28.md`](./contrato-confirm-v125-ticket-2026-08-28.md)
7. [`docs/adr/040-user-information-architecture.md`](../adr/040-user-information-architecture.md) §10
8. AUTO thaw: [`docs/adr/023-camino-d-thaw.md`](../adr/023-camino-d-thaw.md) · [`docs/engineering/camino-d-auto-thaw-checklist-2026-08-04.md`](./camino-d-auto-thaw-checklist-2026-08-04.md)

**Tu entrega:** rellenar la plantilla §7.2 del estudio (opciones AUTO A-α…δ · gráfico B-α…δ · disensos · tests exigidos).

**Preguntas de foco:**

### AUTO (§3 del estudio)

1. ¿AUTO debe usar **TradePlan TRIGGERED** como sizing SoT (paridad SEMI) o sizing **libro** (Camino D actual)?
2. ¿Desde qué fuentes puede disparar AUTO (dictamen Estudio · Radar · cola Hoy)?
3. ¿Qué copy/CTA primario en Operativa cuando AUTO está armado vs SEMI DISPARADA?
4. ¿Qué telemetría mínima antes de ampliar AUTO más allá de BETA-D?

### Gráfico (§4 del estudio)

5. ¿Secuencia acordada: **V1.26b** toasts/fase sin drag → **V1.27** drag→Confirm?
6. ¿Qué líneas son draggables (stop vigente · entrada · T1 · trail)?
7. ¿Drag abre Confirm drawer o ticket inline con override V1.25?
8. ¿Geometría inválida (`stop_wrong_side`, `stop_invalid`) bloquea commit igual que V1.26?

**Invariantes §2 — marcar RECHAZADA cualquier propuesta que rompa:**

Confirm = firma (SEMI) · un solo stop vigente · TradePlan SoT · Estudio gate · `PAPER_D_EXECUTE` default off · ranking ≠ BUY · nav L1 congelada · T1 tocado ≠ gestionado.

**No pedir:** nav L1 nueva · drag sin Confirm · OCO broker · thaw estricto cerrado sin evidencia · OpportunityScore · móvil Mercado completo.

**Registro de acuerdo:** el owner rellena §8 del estudio cuando haya ≥2/3 respuestas; entonces se redacta `diseno-operativa-auto-grafico-ACORDADO-*.md` antes de código.

---

Índice maestro: [`docs/engineering/engineering-index-2026-08-03.md`](./engineering-index-2026-08-03.md) §5 (auditorías externas).
