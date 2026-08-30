# Plan — V1.31.2 Residual UX (layouts · flash · KPI Protección)

> **Padre:** [`traspaso-relevo-v1-31-1-tema-claro-2026-08-30.md`](./traspaso-relevo-v1-31-1-tema-claro-2026-08-30.md) · residual V1.31.  
> **AsOf:** 2026-08-30.  
> **Estado:** **CERRADO (código + tests + docs).**

## Objetivo

Cerrar el residual V1.31 path-to-10: layouts nombrados · flash tick · KPI Protección Cartera, sin tocar Confirm / drag / AUTO / nav L1.

## Decisiones

| ID  | Decisión                                                                                                         |
| --- | ---------------------------------------------------------------------------------------------------------------- |
| D1  | Layouts = presets de dock Mercado sobre `trading-layout-store`. No nuevas regiones shell.                        |
| D2  | SIMPLE = gráfico+operativa; TRADER = todo abierto; ANALISTA = listas+gráfico+operativa. Persist `namedLayoutId`. |
| D3  | Flash tick en celda `lastClose` (+ cierre expandido). ~450ms emerald/rose.                                       |
| D4  | KPI = `Confirmada / N` vía `aggregateMesaProtectionKpi` + `buildMesaProtectionState`.                            |
| D5  | Superficie: Hoy Sin acción + chip compacto Libro/posiciones.                                                     |
| D6  | ≠ drag · ≠ AUTO · ≠ thaw · ≠ nav L1 · ≠ Confirm bypass.                                                          |

## Kernel

```text
namedLayout → applyDockSnapshot → trading-layout-store
price tick → usePriceFlash → CSS flash up|down
open positions → buildMesaProtectionState[] → protegidas/N
```

## Freeze

Confirm = firma · gráfico G0 · AUTO execute env off · nav L1 · LLM no ejecuta.
