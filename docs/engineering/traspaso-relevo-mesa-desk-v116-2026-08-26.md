# RELEVO — Mesa desk V1.16 cierre tests (MD-1 / F1) · 2026-08-26

> **Padre:** [`plan-mesa-desk-v116-v119-2026-08-26.md`](./plan-mesa-desk-v116-v119-2026-08-26.md) · ADR-037.  
> **Partida:** tag **`v1.15-beta` → `fc2ed753`**.  
> **Estado:** **F1-G CERRADO** — matriz tests + smoke browser documentados; chip DS-05 (F1-H) sigue pendiente.  
> **Arranque siguiente agente:** este relevo + plan § F1-H / F2.

---

## 0. Qué se hizo

Completada la **matriz de tests semánticos V1.16** en shared + web, cubriendo los 10 estados obligatorios del plan §F1:

| Estado                     | Cobertura                                | Archivo(s)                                                                           |
| -------------------------- | ---------------------------------------- | ------------------------------------------------------------------------------------ |
| WATCH / sin plan           | `Vigilar` + capas SL/TP `—`              | `mesa-next-action.test.ts`, `mesa-protection-state.test.ts`, `mesa-hoy-page.test.ts` |
| ARMED sin CTA Confirm      | `view_thesis`, no `review_proposal`      | `mesa-next-action.test.ts`, `mesa-hoy-page.test.ts`                                  |
| TRIGGERED                  | `Revisar propuesta`                      | `mesa-next-action.test.ts`, `mesa-hoy-page.test.ts`                                  |
| BLOCKED / incidente / kill | entradas bloqueadas + tono sesión        | `mesa-next-action.test.ts`, `mesa-hoy-model.test.ts`, `mesa-hoy-page.test.ts`        |
| EXPIRED                    | `none`, no `review_proposal`             | `mesa-next-action.test.ts`, `mesa-hoy-page.test.ts`                                  |
| OPEN + hold                | `Mantener`                               | `mesa-next-action.test.ts`, `mesa-hoy-page.test.ts`                                  |
| protect_hint               | `Proteger`; no `Confirmada`              | `mesa-next-action.test.ts`, `mesa-protection-state.test.ts`, `mesa-hoy-page.test.ts` |
| persist skipped → Atención | discrepancia en cola                     | `mesa-protection-state.test.ts`, `mesa-hoy-model.test.ts`, `mesa-hoy-page.test.ts`   |
| NO TRADE / 0 listos        | headline sesión                          | `mesa-hoy-model.test.ts`, `mesa-hoy-page.test.ts`                                    |
| query incidentes error     | fail-closed (Atención + error freshness) | `mesa-next-action.test.ts`, `mesa-hoy-page.test.ts`                                  |

**Diff:** solo ficheros `*.test.ts` — sin campos de dominio nuevos, sin `COMPRAR` en assertions.

---

## 1. Comandos y resultados

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run mesa-next-action mesa-protection mesa-hoy
pnpm --filter @bolsa/web test -- mesa-hoy
```

| Batería                                                    | Antes     | Después       |
| ---------------------------------------------------------- | --------- | ------------- |
| shared `mesa-next-action` + `mesa-protection` + `mesa-hoy` | 24 passed | **34 passed** |
| web `mesa-hoy`                                             | 3 passed  | **11 passed** |

**Build shared:** OK (tsc).

---

## 2. Gaps restantes (F1 / MD-1)

| ID   | Gap                                     | Severidad       | Notas                                                                                    |
| ---- | --------------------------------------- | --------------- | ---------------------------------------------------------------------------------------- |
| F1-G | Smoke browser (5 escenarios Playwright) | P0              | **CERRADO** — checklist abajo (2026-08-26, Playwright MCP, `http://localhost:5173/mesa`) |
| F1-H | Chip datos DS-05 honesto                | P1              | Header + ops-self-eval — sin verde por omisión                                           |
| —    | Sin commit en working tree              | Blocker release | Owner decide                                                                             |
| —    | `pnpm test:decision-spine` post-cambios | P0              | **485 passed** (2026-08-26)                                                              |

### F1-G — Smoke browser checklist

Entorno: dev stack `:5173` / API `:8000` · cuenta activa `Para principal` · sin login (auth local off). Escenarios 2–5 usaron **route mock** Playwright (seed dev sin incidentes, posiciones ni TRIGGERED).

| #   | Escenario                                                                    | Resultado | Evidencia (1 línea)                                                                                                                                                               |
| --- | ---------------------------------------------------------------------------- | --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Carga default: cabecera operativa, candidatos sin COMPRAR, what-if read-only | **PASS**  | `region "Estado operativo de la mesa"` (Régimen/Capital/Normal/SEMI); candidato AAF → `Vigilar`; panel `What-if (solo lectura)` al abrir Simular impacto; sin `COMPRAR` en página |
| 2   | Incidente activo → entradas bloqueadas                                       | **PASS**  | Mock `operational-incidents/active` → `[data-testid=mesa-incident-section]` + copy `Nuevas entradas: BLOQUEADAS`                                                                  |
| 3   | Posición `protect_hint` → CTA Proteger, no Confirmada                        | **PASS**  | Mock portfolio+board → `[data-testid=mesa-next-action-PROT]` texto `Proteger`; sin `Confirmada` en fila                                                                           |
| 4   | Candidato TRIGGERED → Revisar propuesta                                      | **PASS**  | Mock decision-board TRIGGERED TRG1 → `[data-testid=mesa-candidate-cta-TRG1]` = `Revisar propuesta`                                                                                |
| 5   | Query incidentes error → fail-closed                                         | **PASS**  | Mock HTTP 500 incidentes → `[data-testid=mesa-incidents-query-error]` + copy bloqueo preventivo (≠ “0 incidentes”)                                                                |

---

## 3. Freeze recordatorio

- Sin COMPRAR en ranking · Confirm = firma · AUTO off · `PAPER_D_EXECUTE` off
- Proyección UI; dominio intacto
- Honestidad: sin plan → `—`; persist skipped → discrepancia; query error ≠ “0 incidentes”

---

## 4. Señal al owner

Matriz tests F1-F **GREEN** · smoke browser F1-G **5/5 PASS** (2–5 vía mock). Pendiente F1-H chip DS-05 antes de declarar F1 completo al 100 %.
