# RELEVO — V1.34 Frente B Drag B-γ (2026-08-30)

> **AsOf:** 2026-08-30 · **Estado:** **CÓDIGO** — stop drag → Confirm; **sin tag**.  
> **Padre:** [`diseno-operativa-auto-grafico-ACORDADO-2026-08-30.md`](./diseno-operativa-auto-grafico-ACORDADO-2026-08-30.md) · [`plan-v134-frente-b-drag-b-gamma-2026-08-30.md`](./plan-v134-frente-b-drag-b-gamma-2026-08-30.md).  
> **Tag certificado:** `v1.26-beta` → `96c0d5d7`. Tip incluye V1.27–V1.34 + V1.31.1 + V1.31.2 (código; sin commit/tag aún).

---

## 0. Qué cierra V1.34

**B-γ** — G3 ghost + G4 Confirm `signedStop`. Solo stop vigente. §8 ACUERDO + N4 archivada.

| Pieza                                                    | Estado          |
| -------------------------------------------------------- | --------------- |
| Política fases + geometría (`validateOperationalLevels`) | CÓDIGO + vitest |
| Prefill `signedStop` + drawer opts                       | CÓDIGO + vitest |
| Handle drag en `ChartOperationalPlanLevelsLayer`         | CÓDIGO          |
| Posición → enqueue protect override                      | CÓDIGO + vitest |
| Preparada → setActive cola existente + Confirm           | CÓDIGO          |

**Archivos clave:** `chart-stop-drag-policy.ts` · `chart-stop-drag-commit.ts` · `chart-operational-plan-levels-layer.tsx` · `confirm-drawer.ts` · `supervised-f3-panel.tsx` · `propose-position-exit.ts`.

**No** se tocó: B-δ · OCO · entrada/T1/T2 drag · flip execute · thaw · Alembic.

## 1. Freeze intacto

Confirm = firma · gráfico no autoriza · sin PositionRevision desde chart · AUTO execute env off · nav L1 · LLM no ejecuta · H2 kill asimétrico.

## 2. Next (un epic)

| Epic              | Qué                                     | Fuera     |
| ----------------- | --------------------------------------- | --------- |
| Tag deuda         | `v1.27`…`v1.34` + `v1.31.1` + `v1.31.2` | —         |
| Entrada drag      | Deep pedía entry; owner aplazó          | Solo stop |
| UI histórico rico | Tabla proposes A6                       | Strip N   |

## 3. Arranque siguiente chat

1. Este relevo + [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) + diseño ACORDADO.
2. `pnpm exec vitest run src/features/charts/chart-stop-drag-policy.test.ts src/features/charts/chart-stop-drag-commit.test.ts` (cwd `apps/web`).
3. Smoke: Mercado · valor preparada/posición con niveles → handle rojo → arrastrar stop válido → Confirm con stop prefilled; inválido no abre; disparada sin handle.
4. No abrir B-δ / OCO / flip execute / thaw.
5. Deuda tag: `v1.27`…`v1.34` + `v1.31.1` + `v1.31.2` aún no publicados.
