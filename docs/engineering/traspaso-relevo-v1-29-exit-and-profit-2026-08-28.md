# RELEVO — V1.29 Exit and profit (2026-08-28)

> **AsOf:** 2026-08-28 · **Estado:** **CÓDIGO** — producto V1.29-beta, **sin tag todavía**.  
> **Padre:** [`traspaso-relevo-v1-28-daily-cockpit-2026-08-28.md`](./traspaso-relevo-v1-28-daily-cockpit-2026-08-28.md) · [`roadmap-v127-path-to-10-2026-08-28.md`](./roadmap-v127-path-to-10-2026-08-28.md).  
> **Tag certificado:** `v1.26-beta` → `96c0d5d7`. Tip de `main` incluye V1.27–V1.28 + este V1.29 (código; sin commit/tag aún).

---

## 0. Qué cierra V1.29

**Exit and profit** en el shell existente: superficie de `ExitPolicy` (plantillas conservative / moderate / aggressive_swing) + trail que **no empeora** el stop vigente. **No** drag · **no** AUTO · **no** nav L1 nueva.

| Pieza                                                                                      | Estado               |
| ------------------------------------------------------------------------------------------ | -------------------- |
| Advisory ExitPlan con `suggestedQty` / `suggestedStop` / `policyTemplateId` / `trailWidth` | CÓDIGO               |
| Perfil activo → `resolve_exit_policy` en `GET /portfolio`                                  | CÓDIGO               |
| Reduce CTA usa qty de ExitPolicy (no mitad hardcode si hay evento)                         | CÓDIGO + tests       |
| Config → Perfil: preview T1%/T2%/trailWidth                                                | CÓDIGO               |
| Operativa: hint «T1 → reducir X% (moderado)» bajo CTAs                                     | CÓDIGO               |
| `mapTrailPlan` respeta `trailWidth` (tight 0.75 / medium 1.0 / wide 1.25)                  | CÓDIGO + tests TS/PY |
| `clampStopNotWorsen` en trail hint + protect enqueue                                       | CÓDIGO + tests       |
| CTA Proteger oculto si clamp = stop vigente                                                | CÓDIGO + tests       |

**Archivos clave:** `exit-policy.ts` · `trail-plan.ts` · `position-state.ts` (`clampStopNotWorsen`) · `evaluate_exit_plan.py` · `extra_mappers.py` · `propose-position-exit.ts` · `investor-profile-panel.tsx` · `position-exit-drawer-actions.tsx`.

**No** se tocó: drag · AUTO · Confirm bypass · nav L1 · segundo motor ExitPlan · trail como autoridad de `currentStop`.

## 1. Freeze intacto

Confirm = firma · gráfico G0 · sin drag · AUTO off · `PAPER_D_EXECUTE` off · nav L1 congelada · LLM no ejecuta.

Estudio AUTO+gráfico §8 **Aplazado** (N4 pendiente).

## 2. Next (un epic)

| Epic      | Qué                                                                  | Fuera                 |
| --------- | -------------------------------------------------------------------- | --------------------- |
| **V1.30** | Portfolio intelligence — `EffectiveTradingPolicy`; Encaja vs cartera | Drag · AUTO           |
| Frente B  | Drag B-γ                                                             | Hasta N4 + §8 ACUERDO |
| Frente A  | AUTO A-β                                                             | V1.33; A-γ rechazada  |
| V1.31     | UX 10/10 (palette / densidad)                                        | ≠ este V1.29          |

## 3. Arranque siguiente chat

1. Este relevo + [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) + roadmap path-to-10.
2. `pnpm --filter @bolsa/shared test` · web: `propose-position-exit` · py: `test_confirm_exit_chain` (advisory) + `test_trail_plan`.
3. Smoke: perfil Moderado → T1 tocado → reduce qty ≈ 30%; protect con hint peor que vigente → clamp / sin CTA; Config muestra línea «Salida T1 …».
4. No abrir drag / AUTO.
5. Deuda tag: `v1.27` / `v1.28` / `v1.29` aún no publicados (certificado sigue `v1.26-beta`).
