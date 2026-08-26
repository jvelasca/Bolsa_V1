# RELEVO — MD-3 V1.18 Evolución + alertas · 2026-08-26

> **Padre:** [`plan-mesa-desk-v116-v119-2026-08-26.md`](./plan-mesa-desk-v116-v119-2026-08-26.md) §F3 · [`roadmap-v116-mesa-desk-2026-08-26.md`](./roadmap-v116-mesa-desk-2026-08-26.md) MD-3.
> **AsOf:** 2026-08-26.
> **Estado:** **MD-3 CERRADO**.
> **Arranque chat nuevo:** este fichero + plan §F4 (MD-4) o §F6 verificación.

---

## 0. Resumen DoD F3

| ID   | Entrega                              | Estado                                       |
| ---- | ------------------------------------ | -------------------------------------------- |
| F3-A | `decision-journal-relevant-delta.ts` | **Hecho** (previo)                           |
| F3-B | `mesa-decision-alerts-panel.tsx`     | **Hecho** (previo)                           |
| F3-C | Copy «¿Por qué cambió?» sin LLM      | **Hecho** — `journal-study-compare-card.tsx` |
| F3-D | Tests alertas + deltas edge cases    | **Hecho**                                    |
| F3-E | Integración alertas orden ADR-037    | **Hecho**                                    |

**DoD checklist:**

- [x] Alertas solo con datos persistidos (portfolio, studies, header freshness, discrepancias ya calculadas)
- [x] Tests ≥4 casos delta relevantes
- [x] Tests `buildMesaDecisionAlerts`
- [x] Sin segundo bus de alertas (compositor único en `mesa-hoy-page.tsx`)
- [x] Orden visual ADR-037 respetado (alertas tras resumen cuenta, antes de atención)

---

## 1. Qué quedó hecho

### F3-E — Orden ADR-037 en `/mesa`

Orden invariante ADR-037 §2 + extensiones V1.16/V1.18:

1. Incidente activo (+ fail-closed query error)
2. Cabecera operativa V1.16 (`MesaOperationalHeaderStrip`)
3. Estado de sesión
4. Resumen cuenta
5. **Alertas operativas V1.18** (`MesaDecisionAlertsPanel`)
6. Requiere atención
7. Posiciones
8. Candidatos
9. Link salud del sistema

**Corrección:** el panel de alertas estaba antes de sesión/resumen; movido a posición 5.

### F3-D — Tests

`decision-journal-relevant-delta.test.ts`:

- `buildRelevantJournalDelta`: opinión, idéntico, primera tesis, fuerza, stop vs entrada filtrada, invalidación (**6** casos)
- `filterRelevantDeltaFields`: filtro RELEVANT_LABELS (**1**)
- `buildMesaDecisionAlerts`: incidente/stale, señales posición+study, vacío (**3**)

---

## 2. Fuera de alcance

| Tema                             | Estado      | Notas                                       |
| -------------------------------- | ----------- | ------------------------------------------- |
| Smoke browser alertas            | **Parcial** | Ver MD-6 / F6 checklist                     |
| Commit / tag                     | **Fuera**   | Owner explícito                             |
| Segundo panel alertas en Journal | **Fuera**   | Compare card es evolución, no bus operativo |

---

## 3. Verificación reproducible

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run decision-journal-relevant mesa-hoy
pnpm --filter @bolsa/web test -- mesa-hoy
# 2026-08-26: shared 16 passed (10 delta/alerts + 6 mesa-hoy-model) · web 11 passed
```

**Archivos tocados:**

- `apps/web/src/features/mesa/mesa-hoy-page.tsx` — orden alertas
- `packages/shared/src/cognitive/decision-journal-relevant-delta.test.ts` — tests delta + alertas
- `docs/engineering/traspaso-relevo-mesa-desk-v118-2026-08-26.md` — este relevo

---

## 4. Freeze recordatorio

Confirm = firma · AUTO off · `PAPER_D_EXECUTE` off · proyección UI ≠ dominio · sin HTTP nuevo Mesa · alertas sin LLM.

---

## 5. Siguiente chat (E1)

1. **MD-4** — `mesa-operable-ranking.test.ts` + decisión what-if gates.
2. **MD-6** — spine full + smoke browser.

No mezclar MD-3 con tag release (MD-7).
