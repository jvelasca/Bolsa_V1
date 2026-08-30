# RELEVO — V1.34 Frente B Drag B-γ (2026-08-30)

> **AsOf:** 2026-08-30 · **Estado:** **PUBLICADO** — stop drag → Confirm; tag tip `v1.34-beta` → `b5d6bc29`.  
> **Padre:** [`diseno-operativa-auto-grafico-ACORDADO-2026-08-30.md`](./diseno-operativa-auto-grafico-ACORDADO-2026-08-30.md) · [`plan-v134-frente-b-drag-b-gamma-2026-08-30.md`](./plan-v134-frente-b-drag-b-gamma-2026-08-30.md).  
> **Tags:** `v1.34-beta` → `b5d6bc29` · `v1.27-beta` → `3315b69a` · previo `v1.26-beta` → `96c0d5d7`. Handoff [`traspaso-relevo-tag-v1-34-beta-2026-08-30.md`](./traspaso-relevo-tag-v1-34-beta-2026-08-30.md).

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
| Tag deuda         | — cerrada (`v1.27-beta` + `v1.34-beta`) | —         |
| Entrada drag      | Deep pedía entry; owner aplazó          | Solo stop |
| UI histórico rico | Tabla proposes A6                       | Strip N   |

## 3. Arranque siguiente chat

1. Este relevo + [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) + diseño ACORDADO.
2. `pnpm exec vitest run src/features/charts/chart-stop-drag-policy.test.ts src/features/charts/chart-stop-drag-commit.test.ts` (cwd `apps/web`).
3. Smoke: Mercado · valor preparada/posición con niveles → handle rojo → arrastrar stop válido → Confirm con stop prefilled; inválido no abre; disparada sin handle.
4. No abrir B-δ / OCO / flip execute / thaw.
5. Tags publicados: `v1.27-beta` → `3315b69a` · `v1.34-beta` → `b5d6bc29` (absorbidos V1.28–V1.33.3).
