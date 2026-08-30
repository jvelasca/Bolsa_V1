# Plan — V1.31.1 Tema claro

> **Padre:** [`traspaso-relevo-v1-33-2-telemetria-a6-2026-08-30.md`](./traspaso-relevo-v1-33-2-telemetria-a6-2026-08-30.md) · residual V1.31.  
> **AsOf:** 2026-08-30.  
> **Estado:** **CERRADO (código + tests + docs).**

## Objetivo

Cerrar el residual **tema claro** del path-to-10: preferencia `dark` \| `light` \| `system` en shell existente, sin tocar Confirm / drag / AUTO / nav L1.

## Decisiones

| ID  | Decisión                                                                              |
| --- | ------------------------------------------------------------------------------------- |
| D1  | Persistencia local (mismo store que densidad). Default **dark** (producto histórico). |
| D2  | Tokens CSS `--bolsa-*` + `@theme` → utilities; `data-theme` en `<html>`.              |
| D3  | `@custom-variant dark` ligado a `data-theme=dark` (no solo OS).                       |
| D4  | Config → General select + palette (tema-\*). Anti-FOUC en `index.html`.               |
| D5  | ≠ layouts SIMPLE/TRADER/ANALISTA · ≠ flash tick · ≠ KPI Protección · ≠ drag.          |

## Kernel

```text
uiTheme (persist) → resolve(system?) → data-theme=light|dark
→ tokens light/dark · dark: utilities · Config + Ctrl+K
```

## Freeze

Confirm = firma · gráfico G0 · AUTO execute env off · nav L1 · LLM no ejecuta.
