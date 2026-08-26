# RELEVO — UI Mesa incidente DEX-3 (2026-08-26)

> **Padre:** [plan](./plan-mesa-incident-ui-2026-08-26.md) · [DEX-3 relevo](./traspaso-relevo-dex3-operational-incident-2026-08-26.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).
> **AsOf:** 2026-08-26.
> **Estado:** **M0–M4 CERRADOS**. DEX-1…DEX-5 **no reabiertos**.

---

## 0. Qué quedó hecho

| Pieza                                                     | Estado                       |
| --------------------------------------------------------- | ---------------------------- |
| `GET /operational-incidents/active`                       | Hecho                        |
| `POST …/resolve` + `POST …/clear` (+ optional `…/review`) | Hecho — delega a store DEX-3 |
| `MesaIncidentBanner` en barra operativa                   | Hecho                        |
| Resolve nota obligatoria · Clear gated recon clean        | Hecho                        |
| Auto-heal / mutar libros                                  | **No**                       |

## 1. Freeze intacto

Confirm = firma · `PAPER_D_EXECUTE` default off · resolve/clear **no** mutan cash/holdings/PositionState.

## 2. Verificación

- `test_operational_incident_api.py`
- `test_dex3_operational_incident.py` (regresión)
- web `mesa-incident-banner.test.tsx`
- `pnpm test:decision-spine` **483**
- `pnpm --filter @bolsa/web contract:gen`

## 3. M4 — no hacer

1. No reimplementar kernel DEX-3 en routes (delegar a `operational_incident_store`).
2. No confundir `incident:unresolved` con `reconciliation:*` en copy.
3. No competir con CTAs Confirm en el banner.
