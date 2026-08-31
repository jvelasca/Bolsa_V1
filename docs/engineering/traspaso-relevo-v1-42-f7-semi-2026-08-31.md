# RELEVO — V1.42 F7 SEMI complete (2026-08-31)

> **Padre:** [`plan-v142-f7-semi-2026-08-31.md`](./plan-v142-f7-semi-2026-08-31.md) · [`spec-v142-operating-excellence-2026-08-31.md`](./spec-v142-operating-excellence-2026-08-31.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** **CERRADO** — simetría SEMI entrada/salida · Confirm = firma · trail honesty GP-08.  
> **No tag** en este slice (código en tip; release-tag cuando el owner lo pida).

---

## 0. Qué cierra F7

| Pieza                                                                                                | Estado          |
| ---------------------------------------------------------------------------------------------------- | --------------- |
| `PositionExitDrawerActions` — primaryOnly default · 1 CTA Reducir/Salir                              | CÓDIGO + vitest |
| Hoy `DailyDeskInbox` — posición enqueue → Confirm                                                    | CÓDIGO + vitest |
| Trail copy «no aplicado · requiere Confirm» (POT secondary · Mercado trailing · OperationalPlanView) | CÓDIGO          |
| Phrase §B.5 T1+HOLD · Confirm `F3ExitPlanBlock` labels humanos                                       | CÓDIGO          |
| Cockpit ¿Por qué? Plan = phaseLabel / mapa humano (no WATCH/ARMED/TRIGGERED)                         | CÓDIGO          |

**Regla:** SEMI = IA → Risk → Policy → **Humano confirma** → Execution. Hint trail ≠ `currentStop`. Ranking ≠ BUY. Sin motores nuevos.

## 1. Freeze

Confirm = firma · Spine · Router · `PAPER_D_EXECUTE` off · AUTO execute off · LIVE thaw off · `protect_hint` thin ≠ autoridad · sin drag · sin F8.

## 2. Honestidad / parked

| Capacidad                                                                    | Notas                                                                                                                                              |
| ---------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| Trail Confirm → PositionRevision → `currentStop` como ciclo producto cerrado | UI honesty shipped; **no** inventar auto-apply. Si revision durable no cierra autoridad de stop en todos los wires, queda gap documentado — no F8. |
| HoyCommandStrip / MesaAttentionQueue (legacy)                                | Fuera del chrome F6; no reabiertos                                                                                                                 |
| PAPER AUTO (omit firma)                                                      | **F8**                                                                                                                                             |

## 3. Next

| Tag | Nombre     | Notas                                                  |
| --- | ---------- | ------------------------------------------------------ |
| F8  | PAPER AUTO | Mismos objetos; omite firma humana · sin thaw estricto |

## 4. Pre-flight

Ver plan F7 §criterios.
