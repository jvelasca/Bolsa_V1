# RELEVO — MD-2 V1.17 Posición + ticket Confirm · 2026-08-26

> **Padre:** [`plan-mesa-desk-v116-v119-2026-08-26.md`](./plan-mesa-desk-v116-v119-2026-08-26.md) §F2 · [`roadmap-v116-mesa-desk-2026-08-26.md`](./roadmap-v116-mesa-desk-2026-08-26.md) MD-2.
> **AsOf:** 2026-08-26.
> **Estado:** **MD-2 CERRADO** (gaps F2-B/F2-D; F2-E ya existía).
> **Arranque chat nuevo:** este fichero + plan §F3 (MD-3) o §F5 backend.

---

## 0. Resumen

| ID   | Entrega                                        | Estado                                     |
| ---- | ---------------------------------------------- | ------------------------------------------ |
| F2-A | `PositionRoutePanel` (ENTRY/STOP/TP)           | **Hecho** (previo)                         |
| F2-B | Cablear `showRoute` en Mesa posiciones         | **Hecho**                                  |
| F2-C | Ticket riesgo → entrada → objetivo             | **Hecho** (previo)                         |
| F2-D | Invalidación riesgo al cambiar qty/precio      | **Hecho**                                  |
| F2-E | Troceo auditables F3 (ticket / risk / protect) | **Hecho** (previo — 4 bloques importables) |

---

## 1. Qué quedó hecho

### F2-B — `showRoute` en Mesa

- Helper exportado `mesaPositionShowsRoute(position, study)` en `mesa-position-row.tsx`.
- `mesa-positions-summary.tsx` pasa `showRoute={mesaPositionShowsRoute(...)}` por fila.
- Criterio: `study.hasOperationalPlan === true` **o** `operational.currentStop/target1/target2` presentes.
- Tests: `mesa-position-row.test.tsx` (**5**).

### F2-D — Invalidación qty/precio F3

- Nuevo módulo puro `f3-risk-input-baseline.ts`: baseline TRIGGERED, detección stale, precio firmado.
- `supervised-f3-panel.tsx`:
  - Limpia `riskOverrideReason` al cambiar `quantity` / `price` / `activeId` (sin override silencioso).
  - Recalcula `evaluateRiskSignature` con `resolveF3SignedPrice`.
  - Pasa `inputsStale` a `F3TradePlanRiskFirstBlock`.
  - **Ejecutar** sigue bloqueado por `executeBlockedByRisk`; **Confirmar Intent** (`execute=false`) sin gate (P2 D4).
- `f3-trade-plan-risk-first-block.tsx`: aviso `f3-trade-plan-inputs-stale` cuando qty/precio ≠ plan.
- Tests: `f3-risk-input-baseline.test.ts` (**6**), `f3-trade-plan-risk-first-block.test.tsx` (**2**).

### F2-E — Subcomponentes F3

Ya existían (no re-trocear):

- `f3-ticket-preview-block.tsx`
- `f3-trade-plan-risk-first-block.tsx`
- `f3-risk-signature-block.tsx`
- `f3-protect-stop-block.tsx`

---

## 2. Fuera de alcance / parcial

| Tema                                                              | Estado      | Notas                                                                                                                                 |
| ----------------------------------------------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| **Libro** (`/operaciones`) con `showRoute`                        | **Fuera**   | `MesaPositionRow` solo se usa en `/mesa` vía `MesaPositionsSummary`. Libro no comparte fila — wiring futuro si se unifica componente. |
| Troceo adicional de `supervised-f3-panel.tsx` (assessments, cola) | **Fuera**   | Plan: solo ticket/risk/protect; assessments quedan inline.                                                                            |
| Smoke browser ruta visual                                         | **Parcial** | Ver MD-6 / F6 checklist.                                                                                                              |
| Commit / tag                                                      | **Fuera**   | Owner explícito.                                                                                                                      |

---

## 3. Verificación reproducible

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/web test -- mesa-position f3-trade-plan f3-risk-input-baseline f3-risk-signature
# 2026-08-26: 16 passed (5 + 2 + 6 + 3)
```

**Archivos tocados:**

- `apps/web/src/features/mesa/mesa-position-row.tsx`
- `apps/web/src/features/mesa/mesa-positions-summary.tsx`
- `apps/web/src/features/mesa/mesa-position-row.test.tsx`
- `apps/web/src/features/settings/supervised-f3-panel.tsx`
- `apps/web/src/features/trading/f3-risk-input-baseline.ts`
- `apps/web/src/features/trading/f3-risk-input-baseline.test.ts`
- `apps/web/src/features/trading/f3-trade-plan-risk-first-block.tsx`
- `apps/web/src/features/trading/f3-trade-plan-risk-first-block.test.tsx`

---

## 4. Freeze recordatorio

Confirm = firma · AUTO off · `PAPER_D_EXECUTE` off · LIVE experimental · proyección UI ≠ dominio · sin HTTP nuevo Mesa.

---

## 5. Siguiente chat (E1)

1. **MD-3** — tests alertas + deltas edge cases (`decision-journal-relevant-delta.test.ts`).
2. **MD-4** — `mesa-operable-ranking.test.ts` + decisión what-if gates.
3. **MD-5** — backend sanity DS-05 runtime + pytest nuevos.

No mezclar MD-2 con tag release (MD-7).
