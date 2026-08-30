# Diseño ACORDADO — Operativa gráfico B-γ (stop → Confirm)

> **AsOf:** 2026-08-30 · **Estado:** **ACUERDO** (R4) — listo para R5 implementación.  
> **Padre:** [`estudio-operativa-auto-y-grafico-2026-08-28.md`](./estudio-operativa-auto-y-grafico-2026-08-28.md) §8 · N4 [`respuesta-auditor-N4-operativa-auto-grafico-2026-08-30.md`](./respuesta-auditor-N4-operativa-auto-grafico-2026-08-30.md).  
> **Epic código:** V1.34 · plan [`plan-v134-frente-b-drag-b-gamma-2026-08-30.md`](./plan-v134-frente-b-drag-b-gamma-2026-08-30.md).  
> **Contrato ticket:** [`contrato-confirm-v125-ticket-2026-08-28.md`](./contrato-confirm-v125-ticket-2026-08-28.md).

---

## 1. Decisión

| Campo         | Valor                                                                    |
| ------------- | ------------------------------------------------------------------------ |
| Opción        | **B-γ** = G3 (ghost/sandbox) + G4 (commit → Confirm)                     |
| Línea         | Solo **stop vigente**                                                    |
| Fases         | `armada` / `preparada` / `posicion` — **nunca** `disparada`              |
| Commit        | Pre-fill Confirm `signedStop` · drawer real · **no** mutar Position      |
| Geometría     | Una sola: `packages/shared/.../operational-levels.ts` (+ mirror PY gate) |
| Fuera Estudio | G0                                                                       |

**Rechazado:** B-δ · trail drag · T1/T2 drag · entrada drag (deuda) · OCO · ticket inline · flip `PAPER_D_EXECUTE`.

---

## 2. Flujo

```text
Pointer down en priceLine stop (fase permitida + showsPlanLevels)
  → G3: ghost line + preview local (precio, ΔR/€ si hay entry+qty conocidos)
  → validateOperationalLevels en vivo
  → inválido: feedback visual; al soltar NO abre Confirm
Pointer up válido
  → G4: navegar/abrir Confirm con signedStop = precio ghost
  → ticket recalcula risk signature / override (V1.25)
  → firma humana (SEMI) — gráfico no ejecuta
```

---

## 3. Mapa estado × interacción

| Fase / contexto                            | Drag stop | Commit                                                                      |
| ------------------------------------------ | --------- | --------------------------------------------------------------------------- |
| Vigilancia / descubierto / sin plan levels | No (G0)   | —                                                                           |
| Armada / Preparada                         | G3        | G4 → Confirm apertura (`signedStop`)                                        |
| Posición                                   | G3        | G4 → Confirm (protect/ajuste vía ticket; **no** `PositionRevision` directo) |
| Disparada                                  | No        | —                                                                           |

---

## 4. Invariantes (testables)

1. Drag **no** llama protect/reduce/execute APIs.
2. `signedStop` del intent Confirm = precio al soltar (dentro de tolerancia float).
3. Geometría inválida ⇒ cero apertura de Confirm desde drag.
4. Trail / T1 / T2 / entry lines no tienen hit-target de drag.
5. Fuera de Estudio o `showsPlanLevels=false` ⇒ comportamiento idéntico a G0.
6. Confirm sigue siendo la única firma (copy / CTA intactos).

---

## 5. Superficie de código (ancla)

| Pieza                  | Path                                                     |
| ---------------------- | -------------------------------------------------------- |
| Capas niveles (hoy G0) | `chart-operational-plan-levels-layer.tsx`                |
| Builder niveles        | `operational-plan-chart-levels.ts`                       |
| Contexto fase          | `use-instrument-operational-context`                     |
| Confirm                | `supervised-f3-panel.tsx` + ruta `/confirm` / drawer Hoy |
| Geometría              | `operational-levels.ts`                                  |

---

## 6. Criterio de hecho (R5)

- [x] Pointer drag stop en fases permitidas con ghost.
- [x] Soltar válido abre Confirm con `signedStop`.
- [x] Soltar inválido no abre Confirm.
- [x] Vitest: hit-policy + geometría + no-drag en DISPARADA / sin plan.
- [x] Freeze: sin B-δ · sin OCO · sin flip execute · nav L1 intacta.
