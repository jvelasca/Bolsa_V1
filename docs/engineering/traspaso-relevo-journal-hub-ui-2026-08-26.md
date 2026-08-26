# RELEVO — Decision Journal hub UI (Tesis, patrón Instrumentos) (2026-08-26)

> **Padre:** [ADR-036](../adr/036-decision-journal-study-view.md) · [relevo Tesis](./traspaso-relevo-journal-20-tesis-2026-08-26.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO** (UI polish post-P1). DEX/Confirm **no reabiertos**.

---

## 0. Qué quedó hecho

| Pieza                                                            | Estado                                                 |
| ---------------------------------------------------------------- | ------------------------------------------------------ |
| Split lista \| ficha (`JournalStudiesSplitLayout`)               | Hecho — responsive wide/stack, divisor redimensionable |
| Tabla Tesis compacta (grid px fijo, cabecera sticky, alineación) | Hecho — patrón hub Instrumentos                        |
| Auto-fit columnas + persistencia layout v2                       | Hecho — `journal-study-column-layout.ts`               |
| Acciones fila compactas (menú `···`)                             | Hecho                                                  |
| Página full-height `100dvh - topbar`                             | Hecho                                                  |
| Límite API tesis `200` + contador `N / total`                    | Hecho                                                  |
| Rail ficha colapsada                                             | Hecho — `JournalStudyDetailCollapsedRail`              |

## 1. Archivos clave

- `apps/web/src/features/decision-journal/decision-journal-page.tsx`
- `apps/web/src/features/decision-journal/journal-studies-table.tsx`
- `apps/web/src/features/decision-journal/journal-studies-split-layout.tsx`
- `apps/web/src/lib/journal-study-column-layout.ts`

## 2. Verificación

- web `decision-journal-page.test.tsx`
- web `journal-study-column-layout.test.ts`
- `pnpm test:decision-spine` **483**

## 3. Notas

- Si la lista muestra pocas filas, suele ser **dato seed** (una tesis por instrumento), no límite UI.
- Storage columnas bump `bolsa.journal-study-columns.v2` resetea layouts viejos demasiado anchos.

## 4. No hacer

1. No reabrir mapper/API studies salvo bug real.
2. No duplicar hub Instrumentos entero (scores, trackers, etc.) en Journal.
3. No mutar TradePlan/journal desde Tesis.
