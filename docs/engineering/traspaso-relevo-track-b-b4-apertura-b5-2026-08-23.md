# RELEVO / TRASPASO — Track B split backtests B4 → apertura B5 (2026-08-23)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1.
> **Propósito:** texto de paso oficial para el **NUEVO AGENTE / NUEVO CHAT**. Leer este doc + backlog §0 + `PROJECT_STATE.md` §2b + `plan-split-backtests-page-2026-08-22.md` **antes de tocar nada**.
> **Fuente de coordinación:** GitHub [`jvelasca/Bolsa_V1`](https://github.com/jvelasca/Bolsa_V1) `origin/main`. SHA vivo = `git fetch && git rev-parse origin/main` (no asumir SHA de este fichero).
> **Estado al redactar (verificado):** `local main = origin/main = 5475c09` · working tree limpio · **R-13 CERRADA** · **Track B EN CURSO** · split backtests **B1–B4 HECHAS** · tag **`v1.6.0-beta` → `c3964fc`** intacto.
> **AsOf:** 2026-08-23.

---

## 1. Estado verificado (firma — no adivinar)

- **HEAD/rama:** `main` == `origin/main` == `5475c09`. Árbol limpio tras push.
- **Commits split B1–B4 (de más nuevo a más antiguo):**

  | Commit    | Contenido                                                              |
  | --------- | ---------------------------------------------------------------------- |
  | `5475c09` | **B4** — `hooks/use-backtest-derived-data.ts` (derivados + anti-stale) |
  | `bcadea9` | **B3** — `hooks/use-backtest-page-mutations.ts` + reorder helpers nav  |
  | `fcdc857` | **B2** — `hooks/use-backtest-page-queries.ts`                          |
  | `6271c8c` | **B1** — `backtests-page.constants.ts`                                 |

- **Herencia previa (intacta):** docs stamp relevo B4 `89f1982` · Research→Radar F4′–F6′ `240c846` · plan B0 `b2ee0f2` · tag `v1.6.0-beta` → `c3964fc`.
- **Track B — split `backtests-page`:** B0 plan ✅ · **B1–B4 código ✅** · **B5–B12 pendientes**.
- **LOC página (aprox. post-B4):** ~4261 (partía ~4697; post-B3 ~4446).
- **Monitor purge V2:** T+0 19/19 · ventana 4–8 sem · E8 **N**.
- **R-9 F9:** diferida (ADR-028).

### Artefactos B1–B4

| Fase | Fichero                                                                | Notas                                                                                                      |
| ---- | ---------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| B1   | `apps/web/src/features/backtests/backtests-page.constants.ts`          | `STRATEGY_OPTIONS` + re-exports tipos                                                                      |
| B2   | `apps/web/src/features/backtests/hooks/use-backtest-page-queries.ts`   | Queries + glue coach/freshness contiguo                                                                    |
| B3   | `apps/web/src/features/backtests/hooks/use-backtest-page-mutations.ts` | 4 mutations; helpers `patchSearchParams`/`openLibrary`/`setTab`/`selectRun` reordenados **antes** del hook |
| B4   | `apps/web/src/features/backtests/hooks/use-backtest-derived-data.ts`   | Derivados + detail anti-stale; cableado tras mutations, antes de effects matrix                            |

### Deuda explícita post-B4 (no auto-cerrar)

- `proposeFinalistMutation` sigue en la página (depende de derivados).
- Queries tardías en página: `linkedTrialQuery` · `replayBarsQuery` · `drawingReplayQuery`.
- Effects matrix fingerprint / sync `setMatrixRows` siguen en página.
- Helpers nav aún en página (extracción B5/B6).
- Wizards con `STRATEGY_OPTIONS` local — fuera de alcance split hasta fase dedicada.

---

## 2. PROTOCOLO OBLIGATORIO del nuevo agente — VIGENTE

1. **Read-first:** backlog §0 · `PROJECT_STATE.md` §2b · `plan-split-backtests-page-2026-08-22.md` · este doc.
2. **Una fase = un subagente acotado** + verificación coordinador + batería + aprobación por commit + push `main`.
3. **Anti-saturación:** el chat anterior cerró tras B4. **Este chat nuevo** abre B5; B5 es **Alto** (URL sync) — no encadenar B5+B6 sin relevo.

### Batería mínima (web)

```bash
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web lint
pnpm --filter @bolsa/web test
```

Smoke B5: deep-links `?runId=` / `?focus=coach` · Lista AUTO pause/resume fuera de `/backtests`.

---

## 3. Deudas / decisiones pendientes (NO auto-cerrar)

| Ítem                       | Estado / regla                                                                        |
| -------------------------- | ------------------------------------------------------------------------------------- |
| **Split backtests B5–B12** | **SIGUIENTE** — plan `plan-split-backtests-page-2026-08-22.md` · 1 fase = 1 subagente |
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

> CONTEXTO (2026-08-23): main = git rev-parse origin/main → 5475c09. Track B EN CURSO. Split backtests **B1–B4 ✅** (6271c8c · fcdc857 · bcadea9 · 5475c09). Research→Radar F4′–F6′ ✅ (240c846). LEE: traspaso-relevo-track-b-b4-apertura-b5-2026-08-23.md · backlog §0 · plan-split-backtests-page-2026-08-22.md. Tarea: backtests **B5** (URL sync) — 1 subagente, sin commits sin aprobación. Riesgo Alto.

### 4.2 Brief subagentes (patrón)

> Una fase = subagente acotado: read-first backlog §0 + plan split §3 fase Bx + archivos exactos + qué NO tocar + batería esperada + **NO commits ni push** + reporte file:line. Coordinador re-verifica antes de proponer commit. Anti-saturación: no encadenar B5+B6 en el mismo chat sin relevo.

---

## 5. Enlaces

- Plan split: `plan-split-backtests-page-2026-08-22.md`
- Relevo anterior (B1–B3 → B4): `traspaso-relevo-track-b-b1-b3-apertura-b4-2026-08-23.md` (histórico)
- Plan Research→Radar: `plan-unificacion-research-radar-2026-08-21.md` (F4′–F6′ ✅)
- Audit-pack vivo: `audit-pack-estado-global-2026-08-22.md`
- Backlog: `backlog-trabajo-2026-08-20.md` §0

---

## 6. Cierres registrados (sesión 2026-08-23)

| Fecha      | Hito                                    | Commit    |
| ---------- | --------------------------------------- | --------- |
| 2026-08-23 | Split backtests **B4** derivados        | `5475c09` |
| 2026-08-23 | Split backtests **B3** mutations        | `bcadea9` |
| 2026-08-23 | Split backtests **B2** queries          | `fcdc857` |
| 2026-08-23 | Split backtests **B1** constantes       | `6271c8c` |
| 2026-08-23 | Track B F4′–F6′ Research→Radar (previo) | `240c846` |

> **Siguiente:** backtests **B5** (URL sync — `hooks/use-backtest-url-sync.ts`).
