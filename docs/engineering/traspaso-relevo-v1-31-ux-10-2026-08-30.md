# RELEVO — V1.31 UX 10/10 (palette + densidad) (2026-08-30)

> **AsOf:** 2026-08-30 · **Estado:** **CÓDIGO** — producto V1.31-beta, **sin tag todavía**.  
> **Padre:** [`traspaso-relevo-v1-30-portfolio-intelligence-2026-08-28.md`](./traspaso-relevo-v1-30-portfolio-intelligence-2026-08-28.md) · [`roadmap-v127-path-to-10-2026-08-28.md`](./roadmap-v127-path-to-10-2026-08-28.md).  
> **Tag certificado:** `v1.26-beta` → `96c0d5d7`. Tip de `main` incluye V1.27–V1.31 (código; sin commit/tag aún).

---

## 0. Qué cierra V1.31

**UX 10/10 (slice palette + densidad)** en el shell existente: command palette `Ctrl/⌘K`, hotkeys L1 `Alt+1…5` / `Alt+C` Confirmar, densidad `comfortable` \| `compact` persistida, Config → Atajos. **No** drag · **no** AUTO · **no** layouts nombrados · **no** tema claro · **no** nav L1 nueva.

| Pieza                                                | Estado         |
| ---------------------------------------------------- | -------------- |
| `filterCommands` + registry (nav / config / density) | CÓDIGO + tests |
| Palette UI + host en `platform-shell`                | CÓDIGO         |
| Hotkeys L1 (guard editable)                          | CÓDIGO + tests |
| `uiDensity` en `ui-store` + `data-density` CSS       | CÓDIGO         |
| Config → General: toggle densidad                    | CÓDIGO         |
| Config → Atajos: lista `PLATFORM_SHORTCUTS`          | CÓDIGO         |
| Top bar: botón ⌘K                                    | CÓDIGO         |

**Archivos clave:** `command-registry.ts` · `command-palette.tsx` · `command-palette-host.tsx` · `keyboard.ts` · `platform-shortcuts.ts` · `ui-density.ts` · `ui-store.ts` · `platform-shell.tsx` · `app-top-bar.tsx` · `general-settings-section.tsx` · `platform-config-dialog.tsx` · `index.css`.

**No** se tocó: drag · AUTO · Confirm bypass · nav L1 · flash tick · layouts SIMPLE/TRADER/ANALISTA · tema claro · KPI Protección.

## 1. Freeze intacto

Confirm = firma · gráfico G0 · sin drag · AUTO off · `PAPER_D_EXECUTE` off · nav L1 congelada · LLM no ejecuta.

Estudio AUTO+gráfico §8 **Aplazado** (N4 pendiente).

## 2. Next (un epic)

| Epic           | Qué                                                                    | Fuera                 |
| -------------- | ---------------------------------------------------------------------- | --------------------- |
| **V1.32**      | SEMI paper maduro                                                      | Drag · AUTO           |
| V1.31 residual | Tema claro **Hecho** (V1.31.1) · layouts · flash tick · KPI Protección | Drag · AUTO           |
| Frente B       | Drag B-γ                                                               | Hasta N4 + §8 ACUERDO |
| Frente A       | AUTO A-β                                                               | V1.33; A-γ rechazada  |

## 3. Arranque siguiente chat

1. Este relevo + [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) + roadmap path-to-10.
2. `pnpm --filter @bolsa/web test -- src/features/command-palette` · smoke: `Ctrl+K` → Hoy; `Alt+1` → `/mesa`; Config → Compact; Atajos lista visible.
3. No abrir drag / AUTO.
4. Deuda tag: `v1.27` / `v1.28` / `v1.29` / `v1.30` / `v1.31` aún no publicados (certificado sigue `v1.26-beta`).
