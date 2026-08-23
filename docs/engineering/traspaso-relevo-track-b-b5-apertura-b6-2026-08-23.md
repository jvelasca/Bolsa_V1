# RELEVO / TRASPASO — Track B split backtests B5 → apertura B6 (2026-08-23)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1.
> **Propósito:** texto de paso oficial para el **NUEVO AGENTE / NUEVO CHAT**. Leer este doc + backlog §0 + `PROJECT_STATE.md` §2b + `plan-split-backtests-page-2026-08-22.md` **antes de tocar nada**.
> **Fuente de coordinación:** GitHub [`jvelasca/Bolsa_V1`](https://github.com/jvelasca/Bolsa_V1) `origin/main`. SHA vivo = `git fetch && git rev-parse origin/main` (no asumir SHA de este fichero).
> **Estado al redactar (verificado):** `local main` = `ca13981` (B5) · docs stamp pendiente push · **R-13 CERRADA** · **Track B EN CURSO** · split backtests **B1–B5 HECHAS** · tag **`v1.6.0-beta` → `c3964fc`** intacto.
> **AsOf:** 2026-08-23.

---

## 1. Estado verificado (firma — no adivinar)

- **HEAD/rama:** código B5 = `ca13981`. SHA vivo tras push = `git rev-parse origin/main`.
- **Commits split B1–B5 (de más nuevo a más antiguo):**

  | Commit    | Contenido                                                               |
  | --------- | ----------------------------------------------------------------------- |
  | `ca13981` | **B5** — `hooks/use-backtest-url-sync.ts` (deep-links + guard listAuto) |
  | `5475c09` | **B4** — `hooks/use-backtest-derived-data.ts` (derivados + anti-stale)  |
  | `bcadea9` | **B3** — `hooks/use-backtest-page-mutations.ts` + reorder helpers nav   |
  | `fcdc857` | **B2** — `hooks/use-backtest-page-queries.ts`                           |
  | `6271c8c` | **B1** — `backtests-page.constants.ts`                                  |

- **Herencia previa (intacta):** docs stamp relevo B4 `b52284c` · Research→Radar F4′–F6′ `240c846` · plan B0 `b2ee0f2` · tag `v1.6.0-beta` → `c3964fc`.
- **Track B — split `backtests-page`:** B0 plan ✅ · **B1–B5 código ✅** · **B6–B12 pendientes**.
- **LOC página (aprox. post-B5):** ~4146 (partía ~4697; post-B4 ~4261).
- **Monitor purge V2:** T+0 19/19 · ventana 4–8 sem · E8 **N**.
- **R-9 F9:** diferida (ADR-028).

### Artefactos B1–B5

| Fase | Fichero                                                                | Notas                                                                                                      |
| ---- | ---------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| B1   | `apps/web/src/features/backtests/backtests-page.constants.ts`          | `STRATEGY_OPTIONS` + re-exports tipos                                                                      |
| B2   | `apps/web/src/features/backtests/hooks/use-backtest-page-queries.ts`   | Queries + glue coach/freshness contiguo                                                                    |
| B3   | `apps/web/src/features/backtests/hooks/use-backtest-page-mutations.ts` | 4 mutations; helpers `patchSearchParams`/`openLibrary`/`setTab`/`selectRun` reordenados **antes** del hook |
| B4   | `apps/web/src/features/backtests/hooks/use-backtest-derived-data.ts`   | Derivados + detail anti-stale; cableado tras mutations, antes de effects matrix                            |
| B5   | `apps/web/src/features/backtests/hooks/use-backtest-url-sync.ts`       | 10 deep-link effects; guard listAuto en sync `instrumentId`; nav helpers **no** movidos (B6)               |

### Deuda explícita post-B5 (no auto-cerrar)

- Helpers nav aún en página (`patchSearchParams` / `openLibrary` / `setTab` / `selectRun` / `selectInstrument`) — extracción **B6**.
- `proposeFinalistMutation` sigue en la página (depende de derivados).
- Queries tardías en página: `linkedTrialQuery` · `replayBarsQuery` · `drawingReplayQuery`.
- Effects matrix fingerprint / sync `setMatrixRows` siguen en página.
- Wizards con `STRATEGY_OPTIONS` local — fuera de alcance split hasta fase dedicada.
- Smoke manual B5 pendiente: `?runId=` / `?focus=coach` / Lista AUTO pause fuera de `/backtests`.

---

## 2. PROTOCOLO OBLIGATORIO del nuevo agente — VIGENTE

1. **Read-first:** backlog §0 · `PROJECT_STATE.md` §2b · `plan-split-backtests-page-2026-08-22.md` · este doc.
2. **Una fase = un subagente acotado** + verificación coordinador + batería + aprobación por commit + push `main`.
3. **Anti-saturación:** el chat anterior cerró tras B5. **Este chat nuevo** abre B6; B6 es **Alto** (navegación) — no encadenar B6+B7 sin relevo.

### Batería mínima (web)

```bash
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web lint
pnpm --filter @bolsa/web test
```

Smoke B6: deep-links intactos tras mover nav helpers · keep-alive `patchSearchParams` fuera de `/backtests`.

---

## 3. Deudas / decisiones pendientes (NO auto-cerrar)

| Ítem                       | Estado / regla                                                                        |
| -------------------------- | ------------------------------------------------------------------------------------- |
| **Split backtests B6–B12** | **SIGUIENTE** — plan `plan-split-backtests-page-2026-08-22.md` · 1 fase = 1 subagente |
| **Purge storage V2**       | MONITOR · revisión métricas ~2026-09-19 (4 sem)                                       |
| **Ops manuales**           | secret scanning UI · `TRUSTED_PROXIES` prod · `BP/.L`→`BP.L` · `logs/dev`             |
| **F9 B1** (opcional)       | 2 tests market→domain + import-linter — solo si propietario abre                      |
| **Motor money**            | freeze                                                                                |
| **Gobernanza IA**          | freeze                                                                                |
| **`contract:gen`**         | freeze salvo fase pactada                                                             |

**No paralelizar B7 y B8** (estado compartido).

---

## 4. TEXTOS DE PASO PARA EL NUEVO AGENTE (pegar directamente)

### 4.1 Brief de arranque (nuevo chat principal)

> CONTEXTO (2026-08-23): main = git rev-parse origin/main → ca13981 (código B5). Track B EN CURSO. Split backtests **B1–B5 ✅** (6271c8c · fcdc857 · bcadea9 · 5475c09 · ca13981). Research→Radar F4′–F6′ ✅ (240c846). LEE: traspaso-relevo-track-b-b5-apertura-b6-2026-08-23.md · backlog §0 · plan-split-backtests-page-2026-08-22.md. Tarea: backtests **B6** (navegación) — 1 subagente, sin commits sin aprobación. Riesgo Alto.

### 4.2 Brief subagentes (patrón)

> Una fase = subagente acotado: read-first backlog §0 + plan split §3 fase Bx + archivos exactos + qué NO tocar + batería esperada + **NO commits ni push** + reporte file:line. Coordinador re-verifica antes de proponer commit. Anti-saturación: no encadenar B6+B7 en el mismo chat sin relevo.

---

## 5. Enlaces

- Plan split: `plan-split-backtests-page-2026-08-22.md`
- Relevo anterior (B4 → B5): `traspaso-relevo-track-b-b4-apertura-b5-2026-08-23.md` (histórico)
- Plan Research→Radar: `plan-unificacion-research-radar-2026-08-21.md` (F4′–F6′ ✅)
- Audit-pack vivo: `audit-pack-estado-global-2026-08-22.md`
- Backlog: `backlog-trabajo-2026-08-20.md` §0

---

## 6. Cierres registrados (sesión 2026-08-23)

| Fecha      | Hito                                    | Commit    |
| ---------- | --------------------------------------- | --------- |
| 2026-08-23 | Split backtests **B5** URL sync         | `ca13981` |
| 2026-08-23 | Split backtests **B4** derivados        | `5475c09` |
| 2026-08-23 | Split backtests **B3** mutations        | `bcadea9` |
| 2026-08-23 | Split backtests **B2** queries          | `fcdc857` |
| 2026-08-23 | Split backtests **B1** constantes       | `6271c8c` |
| 2026-08-23 | Track B F4′–F6′ Research→Radar (previo) | `240c846` |

> **Siguiente:** backtests **B6** (navegación — `lib/backtest-page-navigation.ts`).
