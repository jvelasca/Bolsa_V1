# RELEVO / TRASPASO — cierre Track B split backtests B12 → decisión de ciclo (2026-08-24)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1.
> **Propósito:** texto de paso oficial para el **NUEVO AGENTE / NUEVO CHAT** tras el cierre de **Track B split backtests (B0–B12)**. Leer este doc + backlog §0 + `PROJECT_STATE.md` §2b + `plan-split-backtests-page-2026-08-22.md` **antes de tocar nada**.
> **Fuente de coordinación:** GitHub [`jvelasca/Bolsa_V1`](https://github.com/jvelasca/Bolsa_V1) `origin/main`. SHA vivo = `git fetch && git rev-parse origin/main` (no asumir SHA de este fichero).
> **Estado al redactar (verificado):** `main` == `origin/main` == **`bb15d1a`** (B12 código `3f9bd7e` + cierre docs) · árbol limpio · **R-13 CERRADA** · **Track B split backtests CERRADO (B0–B12)** · tag **`v1.6.0-beta` → `c3964fc`** intacto.
> **AsOf:** 2026-08-24.

---

## 1. Estado verificado (firma — no adivinar)

- **HEAD/rama:** `main` == `origin/main` == **`bb15d1a`**. Árbol limpio. Serie push B10–B12: `bef3c9f` B10 · `50649a3` B11 · `0723a7e` docs B11 · `3f9bd7e` B12 · `bb15d1a` cierre docs.
- **Commits split B1–B12 (de más nuevo a más antiguo):**

  | Commit    | Contenido                                                                                              |
  | --------- | ------------------------------------------------------------------------------------------------------ |
  | `3f9bd7e` | **B12** — thin shell vía `useBacktestPageModel`; `backtests-page.tsx` 321 LOC                          |
  | `50649a3` | **B11** — `backtests-page-jobs-tab.tsx` (JSX tab `jobs`; `BacktestPageJobsViewModel` + presentacional) |
  | `bef3c9f` | **B10** — `backtests-page-run-tab.tsx` (JSX tab `run`; `BacktestPageViewModel` + presentacional)       |
  | `7e2d24f` | **B9** — `lib/backtest-lab-handlers.ts` (2 factories Lab: nav + coach)                                 |
  | `6e998bd` | **B8** — `lib/backtest-assistant-controller.ts` (factory + effects Asistente)                          |
  | `09f908b` | **B7** — `lib/backtest-list-auto-controller.ts` (factory + effects Lista AUTO)                         |
  | `5c03ff7` | **B6** — `lib/backtest-page-navigation.ts` (factory nav helpers)                                       |
  | `ca13981` | **B5** — `hooks/use-backtest-url-sync.ts` (deep-links + guard listAuto)                                |
  | `5475c09` | **B4** — `hooks/use-backtest-derived-data.ts` (derivados + anti-stale)                                 |
  | `bcadea9` | **B3** — `hooks/use-backtest-page-mutations.ts` + reorder helpers nav                                  |
  | `fcdc857` | **B2** — `hooks/use-backtest-page-queries.ts`                                                          |
  | `6271c8c` | **B1** — `backtests-page.constants.ts`                                                                 |

- **Herencia previa (intacta):** Research→Radar F4′–F6′ `240c846` · plan B0 `b2ee0f2` · tag `v1.6.0-beta` → `c3964fc` · R-13 CERRADA.
- **Track B — split `backtests-page`:** B0 plan ✅ · **B1–B12 código ✅** · **CERRADO**.
- **LOC post-B12:** `backtests-page.tsx` **321** · `hooks/use-backtest-page-model.ts` **1645** (partía ~4697).
- **Criterio plan cumplido:** shell ≤ 600 LOC ✅ · export `BacktestsPage` ✅ · consumidor `platform-shell.tsx` import intacto ✅.
- **Batería B12 (coordinador):** typecheck 0 · lint 0 errores · test **754/754**.
- **Monitor purge V2:** T+0 19/19 · ventana 4–8 sem · E8 **N**.
- **R-9 F9:** diferida (ADR-028).

### Artefacto B12

| Fichero                                                            | LOC aprox. | Notas                                                                                                                                                                                               |
| ------------------------------------------------------------------ | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `apps/web/src/features/backtests/hooks/use-backtest-page-model.ts` | 1645       | Hook orquestador: queries, mutations, derivados, URL sync, controllers B6–B9, VMs tab run/jobs, header + rail + zone settings, cableado tabs strategies/history                                     |
| `apps/web/src/features/backtests/backtests-page.tsx`               | 321        | Thin shell: `useBacktestPageModel()` + composición JSX + early return post-hooks; único export `BacktestsPage`; import externo estable `@/features/backtests/backtests-page` (`platform-shell.tsx`) |

### Deuda explícita post-split (no auto-cerrar)

- **Smoke manual pendiente** (no bloqueante para cierre): play ciclo 1 valor · Lista AUTO pause/resume fuera de `/backtests` · deep-links `?runId=` / `?focus=coach` · tab run (wizard/result/monitor) · tab jobs (Lab optimizar) · keep-alive Lista AUTO con página oculta.
- Wizards con `STRATEGY_OPTIONS` local — fuera de alcance split hasta fase dedicada.
- Purge storage V2 — MONITOR 4–8 semanas.
- Ops manuales — `TRUSTED_PROXIES` prod · secret scanning UI · `BP/.L`→`BP.L` en BD · `logs/dev`.
- Freeze vigente — motor money · gobernanza IA · `contract:gen` salvo fase pactada.

**No reabrir B1–B12.** El split está **CERRADO**.

---

## 2. PROTOCOLO OBLIGATORIO del nuevo agente — VIGENTE

> Premisas **E1–E9** en `docs/PROJECT_PREMISES.md` ⭐§0 y §4.

1. **Read-first:** backlog §0/§1 · `PROJECT_STATE.md` §2b · este doc.
2. **Una fase = un subagente acotado** + verificación coordinador + batería + aprobación por commit + push `main`.
3. **Anti-saturación:** relevo con texto de paso firmado si el hilo se degrada.

### Batería mínima (web — referencia)

```bash
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web lint
pnpm --filter @bolsa/web test
```

---

## 3. Deudas / decisiones pendientes (NO auto-cerrar)

| Ítem                         | Origen            | Regla / estado                                                                             |
| ---------------------------- | ----------------- | ------------------------------------------------------------------------------------------ |
| **Smoke manual backtests**   | plan split §4     | Checklist pendiente — no bloqueante para cierre split; ejecutar antes de release si aplica |
| **Wizards STRATEGY_OPTIONS** | deuda post-split  | Local en wizards — fase dedicada futura; no reabrir split                                  |
| **Purge storage V2**         | R-12/R-13 A1 §4.3 | **MONITOR** 4–8 semanas · T+0 19/19 · E8 **N** (sin purge).                                |
| **Ops manuales**             | ops-r1            | `TRUSTED_PROXIES` prod · secret scanning UI · `BP/.L`→`BP.L` en BD · `logs/dev`.           |
| **Gobernanza IA**            | freeze E7         | NO tocar salvo decisión.                                                                   |
| **`contract:gen`**           | freeze            | NO salvo fase pactada.                                                                     |
| **Motor money**              | freeze            | NO tocar (`ExecuteTrade`, custodia apply).                                                 |
| **Research→Radar F4′–F6′**   | Track B previo    | ✅ `240c846` — **no reabrir**                                                              |

### Candidatos próximos (aparcado — requieren decisión del propietario)

| Candidato                       | Plan / evidencia                                      |
| ------------------------------- | ----------------------------------------------------- |
| Auditoría externa estado global | `audit-pack-estado-global-2026-08-22.md` (actualizar) |
| Modo monitor puro               | Purge V2 + ops checklist, sin commits de código       |
| R-9 F9 analytics↔market         | `plan-r9` + traspaso R-9 F9 (diferida, ADR-028)       |
| Smoke manual backtests          | Checklist plan split §4                               |
| Otro ciclo producto             | Requiere plan + OK línea a línea (E1)                 |

> **Punto de decisión:** Track B split backtests quedó **CERRADO (B0–B12)**. La próxima tarea requiere **definir el siguiente ciclo**. No abrir código sin plan/decisión aprobada (E1).

---

## 4. TEXTOS DE PASO PARA EL NUEVO AGENTE (pegar directamente)

### 4.1 Brief de arranque (nuevo chat principal)

> CONTEXTO (2026-08-24, firma verificada): repo `Bolsa_V1`, `main` == `origin/main` == **`bb15d1a`**, árbol limpio. **Track B split backtests CERRADO (B0–B12)** · B12 código `3f9bd7e` shell 321 LOC · tag **`v1.6.0-beta` → `c3964fc`** · **R-13 CERRADA** · Research→Radar F4′–F6′ ✅ (`240c846`). **No hay ciclo activo predefinido.**
> **LEE PRIMERO:** este doc (§1–§5) · `docs/engineering/backlog-trabajo-2026-08-20.md` §0 · `docs/PROJECT_PREMISES.md` ⭐§0 · `docs/engineering/PROJECT_STATE.md` §2b.
> **Tarea inmediata (decisión, NO fase abierta):** confirmar con el propietario **qué ciclo se abre** (auditoría externa · monitor purge/ops · smoke manual backtests · otro). NO abrir código sin plan/decisión (E1).
> **NO tocar:** purge storage alto · gobernanza IA · motor money · `contract:gen` salvo fase · reabrir split B1–B12.

### 4.2 Brief subagentes (patrón)

> Una fase = subagente acotado: read-first backlog §0 + premisas E1–E9 + archivos exactos + qué NO tocar + mapa consumidores + batería esperada + **NO commits ni push** + reporte file:line. Coordinador re-verifica antes de proponer commit.

---

## 5. Enlaces (fuentes de verdad)

- Backlog: `docs/engineering/backlog-trabajo-2026-08-20.md` (§0 · §6)
- Plan split: `docs/engineering/plan-split-backtests-page-2026-08-22.md` (✅ CERRADO)
- Premisas: `docs/PROJECT_PREMISES.md` ⭐§0
- Estado vivo: `docs/engineering/PROJECT_STATE.md` §2b
- Índice: `docs/engineering/engineering-index-2026-08-03.md` §5
- Relevo B11 apertura (histórico): `traspaso-relevo-track-b-b11-apertura-b12-2026-08-23.md`
- Relevo R-13 cierre (histórico): `traspaso-relevo-cierre-r13-consolidacion-beta-siguiente-2026-08-22.md`
- Pending-delete alto: `docs/engineering/pending-delete/README.md`
- Ops: `docs/engineering/ops-r1-seguridad-operaciones-2026-08-19.md`

---

## 6. Cierres registrados (sesión 2026-08-24)

| Fecha      | Hito                                    | Commit    |
| ---------- | --------------------------------------- | --------- |
| 2026-08-24 | Split backtests **B12** thin shell      | `3f9bd7e` |
| 2026-08-24 | **Cierre documental** Track B split B12 | `bb15d1a` |
| 2026-08-23 | Split backtests **B11** tab `jobs`      | `50649a3` |
| 2026-08-23 | Split backtests **B10** tab `run`       | `bef3c9f` |
| 2026-08-23 | Split backtests **B9** Lab handlers     | `7e2d24f` |
| 2026-08-23 | Split backtests **B8** Asistente        | `6e998bd` |
| 2026-08-23 | Split backtests **B7** Lista AUTO       | `09f908b` |
| 2026-08-23 | Split backtests **B6** navegación       | `5c03ff7` |
| 2026-08-23 | Split backtests **B5** URL sync         | `ca13981` |
| 2026-08-23 | Split backtests **B4** derivados        | `5475c09` |
| 2026-08-23 | Split backtests **B3** mutations        | `bcadea9` |
| 2026-08-23 | Split backtests **B2** queries          | `fcdc857` |
| 2026-08-23 | Split backtests **B1** constantes       | `6271c8c` |
| 2026-08-23 | Track B F4′–F6′ Research→Radar (previo) | `240c846` |

> **Track B split backtests CERRADO (B0–B12).** **Siguiente: decisión de ciclo** (patrón post-R-13). No abrir código sin plan/decisión aprobada.
