# RELEVO — Operational Console (2026-08-26)

> **Padre:** [plan](./plan-operational-console-2026-08-26.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).
> **AsOf:** 2026-08-26.
> **Estado:** **OC0–OC4 CERRADOS** (OC3 skipped). DEX/Confirm **no reabiertos**.

---

## 0. Qué quedó hecho

| Pieza                                     | Estado                                 |
| ----------------------------------------- | -------------------------------------- |
| Ruta `/operational-console`               | Hecho                                  |
| Nav «Consola ops» + Libro dropdown        | Hecho                                  |
| Secciones readiness, OE-1, recon, runtime | Hecho — consume `ops-self-eval`        |
| Card incidentes + resolve panel (DEX-3)   | Hecho — reutiliza `MesaIncidentBanner` |
| Quick links Board/Journal/Confirm/Ops     | Hecho                                  |
| Hook compartido `useOpsSelfEval`          | Hecho — mesa bar + consola             |
| OC3 recon-detail endpoint                 | **Skipped** (YAGNI)                    |

## 1. Distinción producto

| Ruta                   | Rol                                     |
| ---------------------- | --------------------------------------- |
| `/operations` P4       | Posiciones + CTAs desriesgo vía Confirm |
| `/operational-console` | Salud ops read-only + accesos rápidos   |

## 2. Verificación

- web `operational-console-page.test.tsx`
- `pnpm test:decision-spine` **483**

## 3. OC4 — no hacer

1. No duplicar toggles venue/kill en consola (read-only + links).
2. No firmar ni ejecutar desde consola.
3. No convertir en god-page con CTAs de trading.
