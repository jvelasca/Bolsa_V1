# RELEVO / TRASPASO — Track B split backtests B8 → apertura B9 (2026-08-23)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1.
> **Propósito:** texto de paso oficial para el **NUEVO AGENTE / NUEVO CHAT**. Leer este doc + backlog §0 + `PROJECT_STATE.md` §2b + `plan-split-backtests-page-2026-08-22.md` **antes de tocar nada**.
> **Fuente de coordinación:** GitHub [`jvelasca/Bolsa_V1`](https://github.com/jvelasca/Bolsa_V1) `origin/main`. SHA vivo = `git fetch && git rev-parse origin/main` (no asumir SHA de este fichero).
> **Estado al redactar (verificado):** código B8 = `6e998bd` · docs stamp pendiente push · **R-13 CERRADA** · **Track B EN CURSO** · split backtests **B1–B8 HECHAS** · tag **`v1.6.0-beta` → `c3964fc`** intacto.
> **AsOf:** 2026-08-23.

---

## 1. Estado verificado (firma — no adivinar)

- **HEAD/rama:** código B8 = `6e998bd`. SHA vivo tras push docs = `git rev-parse origin/main`.
- **Commits split B1–B8 (de más nuevo a más antiguo):**

  | Commit    | Contenido                                                                      |
  | --------- | ------------------------------------------------------------------------------ |
  | `6e998bd` | **B8** — `lib/backtest-assistant-controller.ts` (factory + effects Asistente)  |
  | `09f908b` | **B7** — `lib/backtest-list-auto-controller.ts` (factory + effects Lista AUTO) |
  | `5c03ff7` | **B6** — `lib/backtest-page-navigation.ts` (factory nav helpers)               |
  | `ca13981` | **B5** — `hooks/use-backtest-url-sync.ts` (deep-links + guard listAuto)        |
  | `5475c09` | **B4** — `hooks/use-backtest-derived-data.ts` (derivados + anti-stale)         |
  | `bcadea9` | **B3** — `hooks/use-backtest-page-mutations.ts` + reorder helpers nav          |
  | `fcdc857` | **B2** — `hooks/use-backtest-page-queries.ts`                                  |
  | `6271c8c` | **B1** — `backtests-page.constants.ts`                                         |

- **Herencia previa (intacta):** docs stamp relevo B7 `6fe1d67` · Research→Radar F4′–F6′ `240c846` · plan B0 `b2ee0f2` · tag `v1.6.0-beta` → `c3964fc`.
- **Track B — split `backtests-page`:** B0 plan ✅ · **B1–B8 código ✅** · **B9–B12 pendientes**.
- **LOC página (aprox. post-B8):** ~2837 (partía ~4697; post-B7 ~3143). Controller Asistente ~729 LOC.
- **Monitor purge V2:** T+0 19/19 · ventana 4–8 sem · E8 **N**.
- **R-9 F9:** diferida (ADR-028).

### Artefactos B1–B8

| Fase | Fichero                                                                | Notas                                                                                                                                                                                                                    |
| ---- | ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| B1   | `apps/web/src/features/backtests/backtests-page.constants.ts`          | `STRATEGY_OPTIONS` + re-exports tipos                                                                                                                                                                                    |
| B2   | `apps/web/src/features/backtests/hooks/use-backtest-page-queries.ts`   | Queries + glue coach/freshness contiguo                                                                                                                                                                                  |
| B3   | `apps/web/src/features/backtests/hooks/use-backtest-page-mutations.ts` | 4 mutations; helpers nav reordenados **antes** del hook                                                                                                                                                                  |
| B4   | `apps/web/src/features/backtests/hooks/use-backtest-derived-data.ts`   | Derivados + detail anti-stale; cableado tras mutations, antes de effects matrix                                                                                                                                          |
| B5   | `apps/web/src/features/backtests/hooks/use-backtest-url-sync.ts`       | 10 deep-link effects; guard listAuto en sync `instrumentId`                                                                                                                                                              |
| B6   | `apps/web/src/features/backtests/lib/backtest-page-navigation.ts`      | Factory `createBacktestPageNavigation`: `patchSearchParams`/`openLibrary`/`setTab`/`selectRun`/`selectInstrument`/`openInstrumentInValor`                                                                                |
| B7   | `apps/web/src/features/backtests/lib/backtest-list-auto-controller.ts` | Factory `createBacktestListAutoController` + hook `useBacktestListAutoEffects` (campaña, supervisión, frescura, soft pause/resume keep-alive); Play → `startListAutoCampaign()`                                          |
| B8   | `apps/web/src/features/backtests/lib/backtest-assistant-controller.ts` | Factory `createBacktestAssistantController` + hook `useBacktestAssistantEffects` (Play, `executeAssistantStep`, Universo→Lab, CORE-P, Lab paso a paso); hand-off Lista AUTO vía `executeAssistantStep`/`settleFullCycle` |

### Deuda explícita post-B8 (no auto-cerrar)

- Lab handlers — extracción **B9** (`lib/backtest-lab-handlers.ts`): `reanalyzeLabWithCoach` · `optimizeSemifinalFromCoach` · `openGuidedOptimize` · `openLabBoard` · `runExploreValue` (callbacks desde Asistente B8).
- `proposeFinalistMutation` sigue en la página (depende de derivados).
- Queries tardías en página: `linkedTrialQuery` · `replayBarsQuery` · `drawingReplayQuery`.
- Effects matrix fingerprint / sync `setMatrixRows` siguen en página.
- Wizards con `STRATEGY_OPTIONS` local — fuera de alcance split hasta fase dedicada.
- Smoke manual pendiente: play ciclo 1 valor · Lista AUTO pause/resume fuera de `/backtests` · deep-links `?runId=` / `?focus=coach`.

---

## 2. PROTOCOLO OBLIGATORIO del nuevo agente — VIGENTE

1. **Read-first:** backlog §0 · `PROJECT_STATE.md` §2b · `plan-split-backtests-page-2026-08-22.md` · este doc.
2. **Una fase = un subagente acotado** + verificación coordinador + batería + aprobación por commit + push `main`.
3. **Anti-saturación:** el chat anterior cerró tras B8. **Este chat nuevo** abre B9; B9 es **Alto** (Lab handlers) — **no encadenar B9+B10** en el mismo chat sin relevo. No reabrir B7 ni B8.

### Batería mínima (web)

```bash
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web lint
pnpm --filter @bolsa/web test
```

Smoke B9: Lab reanalyze · optimize semifinal desde Coach · hand-off Asistente intacto (`optimizeSemifinalFromCoach` callback desde B8).

---

## 3. Deudas / decisiones pendientes (NO auto-cerrar)

| Ítem                       | Estado / regla                                                                        |
| -------------------------- | ------------------------------------------------------------------------------------- |
| **Split backtests B9–B12** | **SIGUIENTE** — plan `plan-split-backtests-page-2026-08-22.md` · 1 fase = 1 subagente |
| **Purge storage V2**       | MONITOR · revisión métricas ~2026-09-19 (4 sem)                                       |
| **Ops manuales**           | secret scanning UI · `TRUSTED_PROXIES` prod · `BP/.L`→`BP.L` · `logs/dev`             |
| **F9 B1** (opcional)       | 2 tests market→domain + import-linter — solo si propietario abre                      |
| **Motor money**            | freeze                                                                                |
| **Gobernanza IA**          | freeze                                                                                |
| **`contract:gen`**         | freeze salvo fase pactada                                                             |

---

## 4. TEXTOS DE PASO PARA EL NUEVO AGENTE (pegar directamente)

### 4.1 Brief de arranque (nuevo chat principal)

> CONTEXTO (2026-08-23): main = git rev-parse origin/main → 6e998bd (código B8; docs stamp si ya pusheado). Track B EN CURSO. Split backtests **B1–B8 ✅** (6271c8c · fcdc857 · bcadea9 · 5475c09 · ca13981 · 5c03ff7 · 09f908b · 6e998bd). Research→Radar F4′–F6′ ✅ (240c846). LEE: traspaso-relevo-track-b-b8-apertura-b9-2026-08-23.md · backlog §0 · plan-split-backtests-page-2026-08-22.md. Tarea: backtests **B9** (Lab handlers) — 1 subagente, sin commits sin aprobación. Riesgo **Alto**. No reabrir B7 ni B8.

### 4.2 Brief subagentes (patrón)

> Una fase = subagente acotado: read-first backlog §0 + plan split §3 fase Bx + archivos exactos + qué NO tocar + batería esperada + **NO commits ni push** + reporte file:line. Coordinador re-verifica antes de proponer commit. Anti-saturación: **no encadenar B9+B10** en el mismo chat sin relevo.

---

## 5. Enlaces

- Plan split: `plan-split-backtests-page-2026-08-22.md`
- Relevo anterior (B7 → B8): `traspaso-relevo-track-b-b7-apertura-b8-2026-08-23.md` (histórico)
- Plan Research→Radar: `plan-unificacion-research-radar-2026-08-21.md` (F4′–F6′ ✅)
- Audit-pack vivo: `audit-pack-estado-global-2026-08-22.md`
- Backlog: `backlog-trabajo-2026-08-20.md` §0

---

## 6. Cierres registrados (sesión 2026-08-23)

| Fecha      | Hito                                    | Commit    |
| ---------- | --------------------------------------- | --------- |
| 2026-08-23 | Split backtests **B8** Asistente        | `6e998bd` |
| 2026-08-23 | Split backtests **B7** Lista AUTO       | `09f908b` |
| 2026-08-23 | Split backtests **B6** navegación       | `5c03ff7` |
| 2026-08-23 | Split backtests **B5** URL sync         | `ca13981` |
| 2026-08-23 | Split backtests **B4** derivados        | `5475c09` |
| 2026-08-23 | Split backtests **B3** mutations        | `bcadea9` |
| 2026-08-23 | Split backtests **B2** queries          | `fcdc857` |
| 2026-08-23 | Split backtests **B1** constantes       | `6271c8c` |
| 2026-08-23 | Track B F4′–F6′ Research→Radar (previo) | `240c846` |

> **Siguiente:** backtests **B9** (Lab handlers — `lib/backtest-lab-handlers.ts`). Riesgo **Alto**. Nuevo chat (anti-saturación).
