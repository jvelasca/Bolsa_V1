# PLAN — Split `backtests-page.tsx` (god-page Track B)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 · traspaso R-13 §3 (Track B BLOQUEADO).
> **Propósito:** plan director para fragmentar `apps/web/src/features/backtests/backtests-page.tsx` (~4697 LOC) en módulos mantenibles sin cambiar semántica.
> **Estado:** **EN CURSO.** B0 plan ✅ · **B1–B6 código ✅** (`6271c8c`·`fcdc857`·`bcadea9`·`5475c09`·`ca13981`·`5c03ff7`) · B7–B12 pendientes. Relevo vivo: `traspaso-relevo-track-b-b6-apertura-b7-2026-08-23.md`.
> **AsOf:** 2026-08-23 · HEAD vivo = `git rev-parse origin/main` (partida B6 = `5c03ff7`).
> **Origen:** informe read-only [Backtests split plan](e5353a50-0ca1-40f4-ae76-ba1a925b4e5a).

---

## 0. Contexto

| Campo              | Valor                                                                         |
| ------------------ | ----------------------------------------------------------------------------- |
| Archivo            | `apps/web/src/features/backtests/backtests-page.tsx`                          |
| LOC                | **4697**                                                                      |
| Export público     | solo `BacktestsPage` (línea 286)                                              |
| Consumidor externo | `platform-shell.tsx:47,156` (keep-alive Lista AUTO)                           |
| Ya extraído        | `lib/backtest-orchestration.ts` (759 LOC) · paneles F4.8 (~15 módulos)        |
| Barrel             | **no existe** `index.ts` — path estable `@/features/backtests/backtests-page` |

**Freeze (no tocar):** gobernanza IA · `pending-delete` alto · `contract:gen` · motor money · early return post-hooks (:3354) · supresiones ESLint refs abort (:1226–1235).

---

## 1. Objetivo

Reducir `backtests-page.tsx` a **~400–600 LOC** (shell + composición). Patrón: mover + tipar, **cero lógica nueva** (P2.1 / F4.8).

---

## 2. Módulos propuestos

| Fichero                                | Responsabilidad                               | LOC aprox. |
| -------------------------------------- | --------------------------------------------- | ---------- |
| `backtests-page.constants.ts`          | `STRATEGY_OPTIONS`, aliases tipos             | ~15        |
| `hooks/use-backtest-page-queries.ts`   | Bloque queries React Query                    | ~180       |
| `hooks/use-backtest-page-mutations.ts` | Mutations + onSuccess mínimo                  | ~140       |
| `hooks/use-backtest-derived-data.ts`   | Derivados + detail anti-stale                 | ~320       |
| `hooks/use-backtest-url-sync.ts`       | Deep-links URL + guards listAuto              | ~160       |
| `lib/backtest-page-navigation.ts`      | `selectInstrument`, `patchSearchParams`, etc. | ~250       |
| `lib/backtest-list-auto-controller.ts` | Lista AUTO, supervisión, freshness            | ~750       |
| `lib/backtest-assistant-controller.ts` | Asistente, Universo→Lab, play                 | ~550       |
| `lib/backtest-lab-handlers.ts`         | reanalyze, optimize detail                    | ~350       |
| `backtests-page-run-tab.tsx`           | Tab `run` (wizard + result + monitor)         | ~1050      |
| `backtests-page-jobs-tab.tsx`          | Tab `jobs`                                    | ~90        |
| `backtests-page.tsx`                   | Shell restante                                | ~450       |

---

## 3. Fases acotadas (una = un subagente)

| Fase      | Alcance                       | Riesgo       | Paralelo         |
| --------- | ----------------------------- | ------------ | ---------------- |
| **B0**    | Este plan + mapa consumidores | Ninguno      | —                |
| **B1** ✅ | Constantes/tipos (`6271c8c`)  | Bajo         | —                |
| **B2** ✅ | Queries (`fcdc857`)           | Medio        | —                |
| **B3** ✅ | Mutations (`bcadea9`)         | Medio        | —                |
| **B4** ✅ | Derivados (`5475c09`)         | Medio        | —                |
| **B5** ✅ | URL sync (`ca13981`)          | **Alto**     | —                |
| **B6** ✅ | Navegación (`5c03ff7`)        | Alto         | —                |
| **B7**    | Lista AUTO                    | **Muy alto** | **SIGUIENTE**    |
| **B8**    | Asistente                     | **Muy alto** | —                |
| **B9**    | Lab handlers                  | Alto         | —                |
| **B10**   | JSX tab `run`                 | Medio        | B11 (tras B6–B9) |
| **B11**   | JSX tab `jobs`                | Bajo         | B10              |
| **B12**   | Thin shell final              | Medio        | —                |

**No paralelizar B7 y B8** (estado compartido).

---

## 4. Batería por fase

```bash
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web lint
pnpm --filter @bolsa/web test
```

Smoke manual: play ciclo 1 valor · Lista AUTO pause/resume fuera de `/backtests` · deep-links `?runId=` / `?focus=coach`.

**Sin** `contract:gen`.

---

## 5. Riesgos críticos

- **Regla de Hooks:** early return en :3354 tras ~150 hooks — no mover hooks antes del return.
- **Keep-alive:** `platform-shell.tsx:139–157` — probar campaña activa con página oculta.
- **Carrera URL ↔ Lista AUTO:** effects :2001–2040 — checklist manual en B5/B7.
- **Props drilling tab run:** tipar `BacktestPageViewModel` antes de B10.

---

## 6. Criterio de aceptación

- `backtests-page.tsx` ≤ 600 LOC.
- Único import externo sin cambios (`platform-shell.tsx`).
- Batería verde tras cada fase.
- Cero cambio de comportamiento observable.
