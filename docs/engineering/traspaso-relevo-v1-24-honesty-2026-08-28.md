# RELEVO — V1.24 Honestidad semántica (2026-08-28)

> **AsOf:** 2026-08-28 · **Estado:** **CÓDIGO LISTO → PUBLICACIÓN** — tag `v1.24-beta` (tras commit).
> **Padre:** [`traspaso-relevo-tag-v1-23-beta-2026-08-28.md`](./traspaso-relevo-tag-v1-23-beta-2026-08-28.md) · auditoría 10/10 · plan V1.24 Honesty Audit.
> **Tag relevo:** [`traspaso-relevo-tag-v1-24-beta-2026-08-28.md`](./traspaso-relevo-tag-v1-24-beta-2026-08-28.md).

---

## 0. Qué cierra V1.24

| Pieza                                                            | Estado         |
| ---------------------------------------------------------------- | -------------- |
| Fases cockpit allowlist: BLOCKED/EXPIRED/CANCELLED ≠ Preparada   | CÓDIGO + tests |
| Trailing: una verdad (`isTrailingStopApplied` + direction)       | CÓDIGO + tests |
| Vocabulario canónico (`product-vocabulary.ts`)                   | CÓDIGO         |
| Ranking: Encaja/Vigilable/Bloqueada · Calidad N/100              | CÓDIGO + tests |
| Chip Barrido (≠ Datos OHLCV) · marketDataAsOf cableado           | CÓDIGO         |
| Operaciones = `OperationalPlanView` builders · queryKey `"mesa"` | CÓDIGO         |
| Ruta T1: tocado ≠ gestionado (`targetProgressHint`)              | CÓDIGO         |
| `stopInicial` sin fallback a vigente                             | CÓDIGO + tests |
| Contrato `sameOperationalPlanAcrossSurfaces`                     | CÓDIGO + tests |
| Hoy: Estudio unavailable ≠ empty 0                               | CÓDIGO + tests |
| `%` nulo muted · `formatPrice` sin € universal                   | CÓDIGO         |

## 1. Freeze heredado (intactos)

Confirm = firma · `PAPER_D_EXECUTE` off · AUTO off · Ranking ≠ BUY · trail thin ≠ autoridad · LLM no ejecuta · LAB ≠ TRADING · OpportunityScore aparcado · DEX-1…5 · nav L1 congelada · shell Mercado LISTAS\|GRÁFICO\|OPERATIVA · BETA.

## 2. Fuera de V1.24 (deuda / siguiente epic)

No mezclar mañana sin palabra explícita:

| Prioridad        | Tema                                                                                             |
| ---------------- | ------------------------------------------------------------------------------------------------ |
| V1.25            | Risk-based sizing único · riesgo €+R en Confirm · what-if before/after en ticket · sector limits |
| Lab              | Backtest `risk_policy` nunca pasado desde `backtests.py` (all-in)                                |
| AUTO path        | `paper_auto` fill sin `sync_position_after_ledger_fill` (freeze OFF)                             |
| Producto         | Grid Cobertura 180 · batch propose · promover trail · OpportunityScore · VaR/correlación · thaw  |
| UX 10/10 (V1.28) | Command palette · hotkeys · layouts nombrados · flash tick · densidad · Cartera KPI Protección   |

## 3. Arranque mañana

1. Leer este relevo + [`traspaso-relevo-tag-v1-24-beta-2026-08-28.md`](./traspaso-relevo-tag-v1-24-beta-2026-08-28.md).
2. Confirmar CI tag GREEN; si falta, pin URL en el tag relevo.
3. Elegir **un** epic (recomendado: V1.25 operational safety **o** Lab backtest risk_policy — no ambos).
4. No reabrir vocabulario Preparada/Datos/Calidad sin test de contrato.

## 4. Verificación local (pre-tag)

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/web exec tsc --noEmit
pnpm test:daily-ops:offline
pnpm test:decision-spine
```

Tests focalizados V1.24: `operativa-cockpit-phase` · `mesa-opportunity-language` · `mesa-cobertura-kpi` · `same-operational-plan-across-surfaces` · `operational-plan-view` · `hoy-en-la-mesa`.
