# Roadmap — Bolsa V1 → ~10/10 (V1.27+)

> **AsOf:** 2026-08-28 · **Estado:** **HOJA DE RUTA** — padre [`traspaso-relevo-v1-26-position-lifecycle-integrity-2026-08-28.md`](./traspaso-relevo-v1-26-position-lifecycle-integrity-2026-08-28.md).  
> **Estudio AUTO+gráfico:** [`estudio-operativa-auto-y-grafico-2026-08-28.md`](./estudio-operativa-auto-y-grafico-2026-08-28.md) §8 = **Aplazado** (drag/AUTO no se implementan aquí).

**Regla:** no añadir módulo/pantalla/botón si no mejora qué sabe el inversor, qué decide, qué riesgo tiene, qué firma, y cómo sabemos que se ejecutó.

**Gráfico:** §8 **ACUERDO B-γ** · código **V1.34** (stop-only → Confirm). B-δ / OCO / entry drag fuera.

**Numeración:** V1.26 = lifecycle integrity (ya en código). El Position Operating Model de las auditorías es **V1.27**, no un segundo V1.26.

| Tag            | Nombre                       | Criterio de salida                                                                                                                           |
| -------------- | ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| **v1.26-beta** | Position Lifecycle Integrity | Tag + CI GREEN                                                                                                                               |
| **V1.27**      | Position Operating Model     | Evento ≠ decisión; Golden Path; atención recon — **CÓDIGO** (`3315b69a`; sin tag)                                                            |
| **V1.28**      | Daily cockpit                | Qué hago en &lt;10 s **en el shell existente**; toasts B-α (G2) — **CÓDIGO** (sin tag)                                                       |
| **V1.29**      | Exit and profit              | UI de ExitPolicy; trail no empeora riesgo — **CÓDIGO** (sin tag)                                                                             |
| **V1.30**      | Portfolio intelligence       | `EffectiveTradingPolicy`; Encaja vs cartera — **CÓDIGO** (sin tag)                                                                           |
| **V1.31**      | UX 10/10                     | Palette + densidad + tema (V1.31.1) + residual layouts/flash/KPI (V1.31.2); **CÓDIGO** (sin tag); drag B-γ solo si §8 ACUERDO                |
| **V1.32**      | SEMI paper maduro            | Entrada/salida simétricas supervisadas — **CÓDIGO** (sin tag)                                                                                |
| **V1.33**      | AUTO A-β + gobernanza        | Paridad SEMI + EdgeReport + A-δ Estudio + wire Estudio→hit (V1.33.1) + telemetría A6 (V1.33.2) — **CÓDIGO** (sin tag); `PAPER_D_EXECUTE` off |

Una fase cierra con código + tests + contrato + Golden/Failure Path + doc.

## V1.27 — máquina (cero motores nuevos)

```text
PositionState + mark
  + ExitPlan          ← EVENTO
  + ExitPolicy        ← plantillas conservative/moderate/aggressive_swing
  + ExitPermission    ← GATE
  + tesis / recon
  → PositionDecision  ← proyección (no tabla)
  → Confirm / HOLD
  → PositionRevision
```

`PositionStatus` durable sigue `OPEN | PARTIAL | PROTECTED | CLOSED`. `T1_REACHED` es vista, no columna rival.

## Tras POM (V1.28+ / Lab / Frentes A·B)

| Tema                                                                  | Cuándo                                                           | Fuera                              |
| --------------------------------------------------------------------- | ---------------------------------------------------------------- | ---------------------------------- |
| V1.28 cockpit + toasts DISPARADA/T1 (B-α, G2)                         | **Hecho** (relevo V1.28)                                         | Drag, nav L1 nueva                 |
| V1.29 Exit and profit                                                 | **Hecho** (relevo V1.29)                                         | Drag, AUTO                         |
| V1.30 Portfolio intelligence                                          | **Hecho** (relevo V1.30)                                         | Drag, AUTO                         |
| V1.31 UX 10/10 (palette + densidad + tema V1.31.1 + residual V1.31.2) | **Hecho** (relevos V1.31 / V1.31.1 / V1.31.2)                    | Drag, AUTO                         |
| V1.32 SEMI paper maduro                                               | **Hecho** (relevo V1.32)                                         | Drag, AUTO                         |
| V1.33 AUTO A-β + gobernanza                                           | **Hecho** (relevo V1.33 + wire Estudio→hit V1.33.1 + A6 V1.33.2) | A-γ, thaw estricto                 |
| Lab `risk_policy` desde `backtests.py`                                | **Hecho en V1.27** (default Moderado)                            | —                                  |
| Frente B drag B-γ                                                     | **CÓDIGO V1.34** (tag v1.34.1-beta)                              | B-δ, trail autoridad, OCO, entrada |
| **V1.35 Position Operating Hardening**                                | **CÓDIGO** (post-auditoría v1.34.1-beta)                         | UI Mercado 2.0, nav L1             |
| **V1.36 Daily Operating UI**                                          | **CÓDIGO** (cockpit POSICIÓN + copy humano)                      | Backend operativo (congelado)      |
| **V1.37 Operational Truth**                                           | **CÓDIGO** — misma decisión en Mercado/Hoy/Journal/Operaciones   | Motor nuevo, backend               |
| **V1.38 Entry Operating UX**                                          | **CÓDIGO** — PREPARADA→CONFIRMADA, no BUY                        | Drag, AUTO                         |
| **V1.39 Position Operating UX**                                       | **CÓDIGO** — una CTA primaria                                    | Drag, AUTO                         |
| **V1.40 Exit Management UX**                                          | **CÓDIGO** — ruta visual Stop/T1/T2                              | OCO, trail autoridad               |
| **V1.41 Daily Desk**                                                  | **CÓDIGO** — Hoy inbox (quitar paneles)                          | Segundo Mercado                    |
| **V1.41.2 Operational Honesty**                                       | **CERRADO** — tag `v1.41.2-beta` → `ebb11e07`                    | ExecutionState, TradeStory         |
| **V1.41.3 Honesty Residuals**                                         | **CERRADO** — tag `v1.41.3-beta` → `a8101ab7`                    | ExecutionState, TradeStory         |
| **V1.42 Operating Excellence**                                        | Parked — modelo/cockpit/TradeStory/DailyDesk 2.0                 | OpportunityScore, AUTO, drag       |
| Frente A AUTO A-β                                                     | V1.33; EdgeReport exigido                                        | A-γ, thaw estricto, broker live    |

## Lean de acuerdo (owner)

Ver §8 del estudio: AUTO Aplazado (lean A-β); gráfico Aplazado (lean B-α ahora, B-γ destino); A-γ y B-δ rechazados.
