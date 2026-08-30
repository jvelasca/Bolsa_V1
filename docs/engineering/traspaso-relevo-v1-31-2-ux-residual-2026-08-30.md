# RELEVO — V1.31.2 Residual UX (2026-08-30)

> **AsOf:** 2026-08-30 · **Estado:** **CÓDIGO** — layouts · flash tick · KPI Protección, **sin tag**.  
> **Padre:** [`traspaso-relevo-v1-31-1-tema-claro-2026-08-30.md`](./traspaso-relevo-v1-31-1-tema-claro-2026-08-30.md) · [`plan-v1312-ux-residual-2026-08-30.md`](./plan-v1312-ux-residual-2026-08-30.md).  
> **Tag certificado:** `v1.26-beta` → `96c0d5d7`. Tip incluye V1.27–V1.33.2 + V1.31.1 + V1.31.2 (código; sin commit/tag aún).

---

## 0. Qué cierra V1.31.2

**Residual UX 10/10** — layouts SIMPLE/TRADER/ANALISTA · flash tick en listas · KPI Protección Cartera. Rojo ≠ drag · ≠ AUTO · ≠ thaw.

| Pieza                                              | Estado         |
| -------------------------------------------------- | -------------- |
| `named-layout.ts` + `applyNamedLayout` dock        | CÓDIGO + tests |
| Config General + top bar + palette `layout-*`      | CÓDIGO + tests |
| `usePriceFlash` + CSS + `lastClose`                | CÓDIGO + tests |
| `aggregateMesaProtectionKpi` + `MesaProteccionKpi` | CÓDIGO + tests |
| Hoy Sin acción + chip Libro                        | CÓDIGO         |

**Archivos clave:** `named-layout.ts` · `trading-layout-store.ts` · `command-registry.ts` · `price-flash.ts` · `use-price-flash.ts` · `list-item-accordion.tsx` · `mesa-protection-state.ts` · `mesa-proteccion-kpi.tsx` · `mesa-hoy-page.tsx`.

**No** se tocó: drag · AUTO · thaw · nav L1 · Confirm · gráfico G0.

## 1. Freeze intacto

Confirm = firma · gráfico G0 · sin drag · AUTO execute env off · nav L1 · LLM no ejecuta · H2 kill asimétrico.

## 2. Next (un epic)

| Epic                  | Qué                                       | Fuera                 |
| --------------------- | ----------------------------------------- | --------------------- |
| Persist `lastPropose` | Histórico telemetría A6                   | Alembic sin necesidad |
| Frente B              | Drag B-γ                                  | N4 + §8 ACUERDO       |
| Tag deuda             | `v1.27`…`v1.33.2` + `v1.31.1` + `v1.31.2` | —                     |

## 3. Arranque siguiente chat

1. Este relevo + [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).
2. `pnpm --filter @bolsa/web test -- src/features/command-palette src/features/mesa/mesa-proteccion src/features/trading/lists-tab/price-flash src/features/trading/lists-tab/use-price-flash`
3. Smoke: Ctrl+K → «Layout: Simple»; Config → Trader; lista flash al cambiar close; Hoy Protección `n/N`; Libro chip compacto.
4. No abrir drag / thaw / A-γ / Radar-Hoy AUTO / flip execute.
5. Deuda tag: `v1.27`…`v1.33.2` + `v1.31.1` + `v1.31.2` aún no publicados.
