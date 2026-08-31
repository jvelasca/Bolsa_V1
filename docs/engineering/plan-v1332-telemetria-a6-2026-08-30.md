# Plan — V1.33.2 Telemetría A6

> **Padre:** [`traspaso-relevo-v1-33-1-wire-estudio-hit-2026-08-30.md`](./traspaso-relevo-v1-33-1-wire-estudio-hit-2026-08-30.md) · estudio §3.2 A6.  
> **AsOf:** 2026-08-30.  
> **Estado:** **CERRADO (código + tests + docs).**

## Objetivo

Responder A6 con un scorecard **read-only**: qué hay que ver en verde **antes** de ampliar AUTO (Radar/Hoy) o thaw estricto. Measure ≠ Accept · ≠ flip `PAPER_D_EXECUTE`.

## Decisiones

| ID  | Decisión                                                                               |
| --- | -------------------------------------------------------------------------------------- |
| D1  | Embudo A-δ desde dictámenes (`estudio_alarma` / `estudio_dictamen`); no corre propose. |
| D2  | P1–P5 reutilizan OE-1/A0. `expandSourcesReady` = P1–P5 PASS + EdgeReport paridad SEMI. |
| D3  | `lastPropose` = snapshot in-process del POST auto-propose (se pierde al restart).      |
| D4  | UI: Consola (card) + strip Asesor. Sin nav L1 nueva.                                   |
| D5  | ≠ Alembic · ≠ Radar/Hoy AUTO · ≠ thaw · ≠ execute on.                                  |
| D6  | `sourcesShouldContract` simétrico a expand (alert-only; reversión manual).             |

## Kernel

```text
GET /instrument-daily-opinions/auto-telemetry
→ funnel Estudio + P1–P5 OE-1 + EdgeReport parity + lastPropose
→ gates.expandSourcesReady / thawEstrictoReady
→ Consola + Asesor (strip)
```

## Freeze

Confirm = firma · gráfico G0 · AUTO execute env off · nav L1 · LLM no ejecuta.
