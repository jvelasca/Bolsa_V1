# RELEVO — V1.28 Daily Cockpit (2026-08-28)

> **AsOf:** 2026-08-28 · **Estado:** **CÓDIGO** — producto V1.28-beta, **sin tag todavía**.  
> **Padre:** [`traspaso-relevo-v1-27-position-operating-model-2026-08-28.md`](./traspaso-relevo-v1-27-position-operating-model-2026-08-28.md) · [`roadmap-v127-path-to-10-2026-08-28.md`](./roadmap-v127-path-to-10-2026-08-28.md).  
> **Tag certificado:** `v1.26-beta` → `96c0d5d7`. Tip de `main` incluye V1.27 POM (`3315b69a`) + este V1.28 (código; sin commit/tag aún).

---

## 0. Qué cierra V1.28

B-α (G2) en el **shell Mercado existente**: qué hago en &lt;10 s vía badges en Listas + toasts DISPARADA/T1. **No** es Hoy nuevo, **no** remonta `HoyCommandStrip`, **no** UX 10/10 (eso es V1.31).

| Pieza                                                            | Estado               |
| ---------------------------------------------------------------- | -------------------- |
| Badge fase en Listas (Disparada / Propuesta / T1 ●)              | CÓDIGO               |
| Misma máquina `resolveMercadoCockpitPhase` (batch, no N hooks)   | CÓDIGO               |
| Toast DISPARADA → CTA «Ver en Mercado»                           | CÓDIGO               |
| Toast T1 tocado **informativo** (H2: tocado ≠ reducido; sin CTA) | CÓDIGO + tests copy  |
| Primera pasada silenciosa (no spam al abrir)                     | CÓDIGO               |
| Pref `operativaToastEnabled` (Config → Notificaciones)           | CÓDIGO + tests prefs |
| Poller Estudio 60s en `PlatformShell`                            | CÓDIGO               |

**Archivos clave:** `operativa-phase-toast.ts` · `operativa-phase-toast-poller.tsx` · `list-operativa-phase-context.tsx` · `list-operativa-phase-badge.tsx` · `open-instrument-in-trading.ts`.

**No** se tocó: drag · AUTO · nav L1 · Confirm bypass · Web Notifications · palette/hotkeys.

## 1. Freeze intacto

Confirm = firma · gráfico G0 · sin drag · AUTO off · `PAPER_D_EXECUTE` off · nav L1 congelada · LLM no ejecuta.

Estudio AUTO+gráfico §8 **Aplazado** (N4 pendiente). **No** `diseno-operativa-auto-grafico-ACORDADO-*`.

## 2. Next (un epic)

| Epic      | Qué                                                                                                                                                                                    | Fuera                 |
| --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------- |
| **V1.29** | Exit and profit — UI ExitPolicy; trail no empeora riesgo — **CÓDIGO** → [`traspaso-relevo-v1-29-exit-and-profit-2026-08-28.md`](./traspaso-relevo-v1-29-exit-and-profit-2026-08-28.md) | Drag · nav nueva      |
| **V1.30** | Portfolio intelligence (`EffectiveTradingPolicy`; Encaja)                                                                                                                              | Drag · nav nueva      |
| Frente B  | Drag B-γ                                                                                                                                                                               | Hasta N4 + §8 ACUERDO |
| Frente A  | AUTO A-β                                                                                                                                                                               | V1.33; A-γ rechazada  |
| V1.31     | UX 10/10 (palette / densidad)                                                                                                                                                          | ≠ este V1.28          |

## 3. Arranque siguiente chat

1. Este relevo + [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) + roadmap path-to-10.
2. `pnpm --filter @bolsa/shared test` (**430**) · `pnpm test:decision-spine` (**530**) · web: `operativa-phase-toast` + `notification-prefs`.
3. Smoke: Estudio + TRIGGERED → badge Disparada + toast; posición T1 tocado sin `target1AchievedAt` → badge T1 ● + toast info.
4. No abrir drag / AUTO.
5. Deuda tag: `v1.27-beta` / `v1.28-beta` aún no publicados (certificado sigue `v1.26-beta`).
