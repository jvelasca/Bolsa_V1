# Roadmap — V1.16 Mesa desk (Operational UX II)

> **Padre:** [`engineering-index-2026-08-03.md`](./engineering-index-2026-08-03.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **AsOf:** 2026-08-26.  
> **Partida:** **`v1.15-beta` → `fc2ed753`**.  
> **Plan:** [`plan-mesa-desk-v116-v119-2026-08-26.md`](./plan-mesa-desk-v116-v119-2026-08-26.md).  
> **Tag objetivo:** **`v1.16-beta` → `953cfcb`** (publicado).

---

## Contexto

V1.15 entregó `/mesa` como home (ADR-037): composición de 6 APIs, nav daily-first, Journal tabla simplificada. Las auditorías V1.14/V1.15 pidieron **desk de 20 segundos** — semántica única, proyecciones UI — más hardening backend (pickle, ENV, PAPER_D, EdgeReport, sanity→DS-05).

V1.16–V1.19 **no** son tags separados en este roadmap: se agrupan en **un tag `v1.16-beta`** con relevos por epic.

---

## Slices

| Slice    | Nombre                    | Estado                                                 | Relevo                                                                                                             |
| -------- | ------------------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------ |
| **MD-0** | Apertura + baseline       | **CERRADO** — spine **485**                            | [`traspaso-relevo-mesa-desk-v116-apertura-2026-08-26.md`](./traspaso-relevo-mesa-desk-v116-apertura-2026-08-26.md) |
| **MD-1** | V1.16 Mesa desk           | F1-F + F1-G GREEN · **F1-H chip DS-05 pendiente (P1)** | [`traspaso-relevo-mesa-desk-v116-2026-08-26.md`](./traspaso-relevo-mesa-desk-v116-2026-08-26.md)                   |
| **MD-2** | V1.17 Posición + ticket   | **CERRADO** (Libro fuera scope)                        | [`traspaso-relevo-mesa-desk-v117-2026-08-26.md`](./traspaso-relevo-mesa-desk-v117-2026-08-26.md)                   |
| **MD-3** | V1.18 Evolución + alertas | **CERRADO**                                            | [`traspaso-relevo-mesa-desk-v118-2026-08-26.md`](./traspaso-relevo-mesa-desk-v118-2026-08-26.md)                   |
| **MD-4** | V1.19 What-if + operable  | **CERRADO** (gates reales fuera tag)                   | [`traspaso-relevo-mesa-desk-v119-2026-08-26.md`](./traspaso-relevo-mesa-desk-v119-2026-08-26.md)                   |
| **MD-5** | Backend paralelo          | **CERRADO** (sanity E2E = P1 post-tag)                 | [`traspaso-relevo-mesa-desk-backend-2026-08-26.md`](./traspaso-relevo-mesa-desk-backend-2026-08-26.md)             |
| **MD-6** | Verificación + pack v116  | **DOCS LISTOS** — spine 485                            | [`audit-pack-estado-global-2026-08-26-v116.md`](./audit-pack-estado-global-2026-08-26-v116.md)                     |
| **MD-7** | Tag `v1.16-beta`          | **PUBLICADO** → `953cfcb`                              | [`traspaso-relevo-tag-v1-16-beta-2026-08-26.md`](./traspaso-relevo-tag-v1-16-beta-2026-08-26.md)                   |

---

## Freeze (heredado)

Confirm = firma · TradePlan/Position SoT · DEX intacto · Ranking ≠ BUY · AUTO off · `PAPER_D_EXECUTE` off · LIVE experimental · sin HTTP nuevo Mesa en este tag.

---

## Post-v1.16-beta (candidatas, no mezclar)

| Candidata                | Notas                                |
| ------------------------ | ------------------------------------ |
| `GET /api/mesa/today`    | Tras composable estable              |
| Backtest = TradingPolicy | Cambio estructural; pack propio      |
| Gates reales en what-if  | Mejora UX, no blocker si documentado |
| F3 troceo profundo       | Mantenibilidad                       |
