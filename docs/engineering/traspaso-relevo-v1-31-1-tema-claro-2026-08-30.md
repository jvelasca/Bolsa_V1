# RELEVO — V1.31.1 Tema claro (2026-08-30)

> **AsOf:** 2026-08-30 · **Estado:** **CÓDIGO** — tema dark/light/system, **sin tag**.  
> **Padre:** [`traspaso-relevo-v1-33-2-telemetria-a6-2026-08-30.md`](./traspaso-relevo-v1-33-2-telemetria-a6-2026-08-30.md) · [`plan-v1311-tema-claro-2026-08-30.md`](./plan-v1311-tema-claro-2026-08-30.md) · residual V1.31.  
> **Tag certificado:** `v1.26-beta` → `96c0d5d7`. Tip incluye V1.27–V1.33.2 + V1.31.1 (código; sin commit/tag aún).

---

## 0. Qué cierra V1.31.1

**Tema claro** — preferencia `dark` \| `light` \| `system` (default dark), tokens CSS, Config → General, command palette, anti-FOUC. Rojo ≠ layouts nombrados · ≠ flash tick · ≠ drag.

| Pieza                                       | Estado         |
| ------------------------------------------- | -------------- |
| `ui-theme.ts` resolve / apply / cycle       | CÓDIGO + tests |
| Tokens `--bolsa-*` + `@custom-variant dark` | CÓDIGO         |
| Persist `uiTheme` en `ui-store`             | CÓDIGO         |
| Config General select + palette theme-\*    | CÓDIGO + tests |
| Anti-FOUC `index.html`                      | CÓDIGO         |

**Archivos clave:** `ui-theme.ts` · `index.css` · `ui-store.ts` · `general-settings-section.tsx` · `command-registry.ts` · `index.html`.

**No** se tocó: layouts SIMPLE/TRADER/ANALISTA · flash tick · KPI Protección · drag · AUTO · thaw · nav L1 · Confirm.

## 1. Freeze intacto

Confirm = firma · gráfico G0 · sin drag · AUTO execute env off · nav L1 · LLM no ejecuta · H2 kill asimétrico.

## 2. Next (un epic)

| Epic                  | Qué                                             | Fuera                 |
| --------------------- | ----------------------------------------------- | --------------------- |
| V1.31 residual        | Layouts nombrados · flash tick · KPI Protección | Drag                  |
| Persist `lastPropose` | Histórico telemetría A6                         | Alembic sin necesidad |
| Frente B              | Drag B-γ                                        | N4 + §8 ACUERDO       |

## 3. Arranque siguiente chat

1. Este relevo + [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) + residual V1.31.
2. `pnpm --filter @bolsa/web test -- src/features/command-palette`
3. Smoke: Config → Tema Claro → shell claro; Ctrl+K → «Tema: Oscuro»; Sistema sigue OS; reload sin flash.
4. No abrir drag / thaw / A-γ / Radar-Hoy AUTO / flip execute.
5. Deuda tag: `v1.27`…`v1.33.2` + `v1.31.1` aún no publicados.
