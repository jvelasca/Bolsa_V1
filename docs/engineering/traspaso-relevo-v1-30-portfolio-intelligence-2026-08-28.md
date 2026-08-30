RELEVO — V1.30 Portfolio intelligence (2026-08-28)

> **AsOf:** 2026-08-28 · **Estado:** **CÓDIGO** — producto V1.30-beta, **sin tag todavía**.  
> **Padre:** [`traspaso-relevo-v1-29-exit-and-profit-2026-08-28.md`](./traspaso-relevo-v1-29-exit-and-profit-2026-08-28.md) · [`roadmap-v127-path-to-10-2026-08-28.md`](./roadmap-v127-path-to-10-2026-08-28.md).  
> **Tag certificado:** `v1.26-beta` → `96c0d5d7`. Tip de `main` incluye V1.27–V1.30 (código; sin commit/tag aún).

---

## 0. Qué cierra V1.30

**Portfolio intelligence** en el shell existente: `EffectiveTradingPolicy` como SoT de límites de encaje (sector / concentración) desde plantilla de perfil activo; **Encaja vs cartera** en scenario, priority y Config. **No** drag · **no** AUTO · **no** nav L1 nueva.

| Pieza                                                              | Estado         |
| ------------------------------------------------------------------ | -------------- |
| `resolveEffectiveTradingPolicy` (TS + PY)                          | CÓDIGO + tests |
| Default scenario/priority: moderate 30% sector (≠ hardcode 40)     | CÓDIGO + tests |
| Hook `useEffectiveTradingPolicy` → perfil activo                   | CÓDIGO         |
| Hoy ranking + what-if + F3 Confirm scenario usan política efectiva | CÓDIGO         |
| Config → Perfil: preview «Encaja: max sector …»                    | CÓDIGO         |
| What-if: línea «Límite sector (política)»                          | CÓDIGO         |

**Archivos clave:** `effective-trading-policy.ts` · `portfolio-scenario.ts` · `operational-priority.ts` · `use-effective-trading-policy.ts` · `mesa-hoy-page.tsx` · `mesa-what-if-panel.tsx` · `supervised-f3-panel.tsx` · `investor-profile-panel.tsx` · `effective_trading_policy.py`.

**No** se tocó: drag · AUTO · Confirm bypass · nav L1 · segundo motor Fit · veto real (sigue `check_opening` / PortfolioFit v1 en gate).

## 1. Freeze intacto

Confirm = firma · gráfico G0 · sin drag · AUTO off · `PAPER_D_EXECUTE` off · nav L1 congelada · LLM no ejecuta.

Estudio AUTO+gráfico §8 **Aplazado** (N4 pendiente).

## 2. Next (un epic)

| Epic      | Qué                           | Fuera                 |
| --------- | ----------------------------- | --------------------- |
| **V1.31** | UX 10/10 (palette / densidad) | Drag · AUTO           |
| Frente B  | Drag B-γ                      | Hasta N4 + §8 ACUERDO |
| Frente A  | AUTO A-β                      | V1.33; A-γ rechazada  |
| V1.32     | SEMI paper maduro             | ≠ V1.31 UX            |

## 3. Arranque siguiente chat

1. Este relevo + [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) + roadmap path-to-10.
2. `pnpm --filter @bolsa/shared test` · web smoke: perfil Conservador → what-if muestra límite sector 20%; Moderado 30%; Config muestra línea Encaja.
3. py: `test_effective_trading_policy.py`.
4. No abrir drag / AUTO.
5. Deuda tag: `v1.27` / `v1.28` / `v1.29` / `v1.30` aún no publicados (certificado sigue `v1.26-beta`).
