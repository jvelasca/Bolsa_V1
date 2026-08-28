# Roadmap — Bolsa V1 → ~10/10 (V1.27+)

> **AsOf:** 2026-08-28 · **Estado:** **HOJA DE RUTA** — padre [`traspaso-relevo-v1-26-position-lifecycle-integrity-2026-08-28.md`](./traspaso-relevo-v1-26-position-lifecycle-integrity-2026-08-28.md).  
> **Estudio AUTO+gráfico:** [`estudio-operativa-auto-y-grafico-2026-08-28.md`](./estudio-operativa-auto-y-grafico-2026-08-28.md) §8 = **Aplazado** (drag/AUTO no se implementan aquí).

**Regla:** no añadir módulo/pantalla/botón si no mejora qué sabe el inversor, qué decide, qué riesgo tiene, qué firma, y cómo sabemos que se ejecutó.

**Gráfico:** G0 read-only. Cero drag hasta §8 ACUERDO + N4 + doc `diseno-operativa-auto-grafico-ACORDADO-*`.

**Numeración:** V1.26 = lifecycle integrity (ya en código). El Position Operating Model de las auditorías es **V1.27**, no un segundo V1.26.

| Tag            | Nombre                       | Criterio de salida                                               |
| -------------- | ---------------------------- | ---------------------------------------------------------------- |
| **v1.26-beta** | Position Lifecycle Integrity | Tag + CI GREEN                                                   |
| **V1.27**      | Position Operating Model     | Evento ≠ decisión; Golden Path; atención recon                   |
| **V1.28**      | Daily cockpit                | Qué hago en &lt;10 s **en el shell existente**; toasts B-α (G2)  |
| **V1.29**      | Exit and profit              | UI de ExitPolicy; trail no empeora riesgo                        |
| **V1.30**      | Portfolio intelligence       | `EffectiveTradingPolicy`; Encaja vs cartera                      |
| **V1.31**      | UX 10/10                     | Palette/densidad; **drag B-γ solo si §8 ACUERDO**                |
| **V1.32**      | SEMI paper maduro            | Entrada/salida simétricas supervisadas                           |
| **V1.33**      | AUTO A-β + gobernanza        | Paridad SEMI + EdgeReport; `PAPER_D_EXECUTE` off hasta evidencia |

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

| Tema                                          | Cuándo                                                    | Fuera                           |
| --------------------------------------------- | --------------------------------------------------------- | ------------------------------- |
| V1.28 cockpit + toasts DISPARADA/T1 (B-α, G2) | POM verde                                                 | Drag, nav L1 nueva              |
| Lab `risk_policy` desde `backtests.py`        | P1 fechado: mismo epic POM o chat siguiente si no bloquea | All-in silencioso               |
| Frente B drag B-γ                             | N4 + §8 ACUERDO + POM congelado                           | B-δ, trail autoridad, OCO       |
| Frente A AUTO A-β                             | V1.33; EdgeReport exigido                                 | A-γ, thaw estricto, broker live |

## Lean de acuerdo (owner)

Ver §8 del estudio: AUTO Aplazado (lean A-β); gráfico Aplazado (lean B-α ahora, B-γ destino); A-γ y B-δ rechazados.
