# RELEVO — MD-4 V1.19 What-if + ranking operable · 2026-08-26

> **Padre:** [`plan-mesa-desk-v116-v119-2026-08-26.md`](./plan-mesa-desk-v116-v119-2026-08-26.md) §F4 · [`roadmap-v116-mesa-desk-2026-08-26.md`](./roadmap-v116-mesa-desk-2026-08-26.md) MD-4.
> **AsOf:** 2026-08-26.
> **Estado:** **MD-4 CERRADO** (tests ranking + decisión what-if gates).
> **Arranque chat nuevo:** este fichero + plan §F5 backend o §F6 verificación.

---

## 0. Resumen

| ID   | Entrega                                              | Estado                            |
| ---- | ---------------------------------------------------- | --------------------------------- |
| F4-A | Ranking operable (`sortMesaCandidatesOperable`)      | **Hecho** (previo)                |
| F4-B | What-if read-only panel                              | **Hecho** (previo — simplificado) |
| F4-C | Preview con gates reales **vs** limitación explícita | **Fuera v1.16-beta** — ver §2     |
| F4-D | Tests `mesa-operable-ranking.test.ts`                | **Hecho**                         |
| F4-E | `GET /api/mesa/today`                                | **Fuera v1.16-beta**              |

---

## 1. Qué quedó hecho

### F4-D — Tests ranking + what-if

Nuevo `packages/shared/src/cognitive/mesa-operable-ranking.test.ts`:

- **`scoreMesaCandidateOperable`:** operable solo TRIGGERED + plan; `blockReasons` (entradas bloqueadas, gate, caducado, sin plan, veto); penalización score.
- **`sortMesaCandidatesOperable`:** operables primero; desempate por `operationalScore` desc.
- **`projectMesaWhatIf`:** suma R, exposición equity/cash/notional, warnings >100% / >5R, nulls honestos.

UI ya existente:

- `mesa-candidates-panel.tsx` — copy `No operable: {blockReasons.join(" · ")}`.
- `mesa-what-if-panel.tsx` — panel read-only; **nunca ejecuta**.

---

## 2. Decisión F4-C — gates reales en what-if

| Opción                                                                          | Decisión v1.16-beta      |
| ------------------------------------------------------------------------------- | ------------------------ |
| Preview what-if con gates reales (risk engine / `check_opening` / sanity DS-05) | **Fuera**                |
| Proyección aritmética read-only (`projectMesaWhatIf`)                           | **Hecho** — entra en tag |

**Motivo:** el plan §F4 permite documentar la limitación; no hay HTTP nuevo Mesa ni wiring E2E de sanity→Confirm en esta fase. El panel what-if muestra riesgo R agregado y exposición % desde datos ya en cliente (study + portfolio); **no** re-evalúa TradePlan, régimen, veto de apertura ni firma de riesgo.

**Implicación para auditor:** what-if es **informativo**, no autoritativo. Confirm sigue siendo la única firma operativa.

**Post-tag (P2):** cablear preview opcional vía API existente de riesgo si el owner prioriza gates reales antes de v1.17+.

---

## 3. Fuera de alcance / parcial

| Tema                    | Estado               | Notas               |
| ----------------------- | -------------------- | ------------------- |
| Gates reales en what-if | **Fuera v1.16-beta** | §2                  |
| `GET /api/mesa/today`   | **Fuera v1.16-beta** | Plan §6             |
| Smoke browser what-if   | **Parcial**          | Checklist F6 / MD-6 |
| Commit / tag            | **Fuera**            | Owner explícito     |

---

## 4. Verificación reproducible

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run mesa-operable-ranking
# 2026-08-26: 13 passed
```

**Archivos tocados:**

- `packages/shared/src/cognitive/mesa-operable-ranking.test.ts` (nuevo)
- `docs/engineering/traspaso-relevo-mesa-desk-v119-2026-08-26.md` (este)

---

## 5. Freeze recordatorio

What-if **solo lectura** · ranking sin COMPRAR · Confirm = firma · proyección UI ≠ dominio · sin HTTP nuevo Mesa.

---

## 6. Siguiente chat (E1)

1. **MD-5** — backend sanity DS-05 runtime + pytest nuevos (plan §F5).
2. **MD-6** — verificación integrada + smoke browser (plan §F6).

No mezclar MD-4 con tag release (MD-7).
