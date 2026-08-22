# RELEVO / TRASPASO — Track B micro-ciclo Research→Radar F4′–F6′ → apertura split backtests B1+ (2026-08-23)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1.
> **Propósito:** texto de paso oficial para el **NUEVO AGENTE / NUEVO CHAT** (mañana). Leer este doc + backlog §0 + `PROJECT_STATE.md` §2b + premisas ⭐§0 **antes de tocar nada**.
> **Fuente de coordinación:** GitHub [`jvelasca/Bolsa_V1`](https://github.com/jvelasca/Bolsa_V1) `origin/main`. SHA vivo = `git fetch && git rev-parse origin/main` (no asumir SHA de este fichero).
> **Estado al redactar (verificado):** `local main = origin/main = 2eba070` · working tree limpio · **R-13 CERRADA** · **Track B EN CURSO** (capítulo Research→Radar F4′–F6′ **HECHO**) · tag **`v1.6.0-beta` → `c3964fc`** intacto.
> **AsOf:** 2026-08-23.

---

## 1. Estado verificado (firma — no adivinar)

- **HEAD/rama:** `main` == `origin/main` == `2eba070`. Árbol limpio tras push.
- **Commits de hoy (2026-08-22/23, de más nuevo a más antiguo):**

  | Commit    | Contenido                                                                                    |
  | --------- | -------------------------------------------------------------------------------------------- |
  | `240c846` | **Track B F4′–F6′** — copy hub Señales + toasts B0 + tests `screenersHrefAfterTrackerCreate` |
  | `b2ee0f2` | docs post-R-13: audit-pack v2, plan split backtests B0, ADR-028 F9, sellado Research F3      |
  | `b4efeff` | docs: cierre R-13 + traspaso anterior                                                        |

- **Track B — Research→Radar:** F1–F3 doc ✅ · **F4′–F6′ código ✅** (`240c846`). Vocabulario: nav/página `SEÑALES_LABEL`; CTAs Camino B `PAPER_PATH_RADAR.cta` («Rastreador») intacto.
- **Track B — split `backtests-page`:** plan B0 ✅ (`plan-split-backtests-page-2026-08-22.md`). **B1–B12 pendientes** — siguiente capítulo.
- **Monitor purge V2:** T+0 19/19 · ventana 4–8 sem abierta 2026-08-22 · E8 **N**.
- **R-9 F9:** diferida (ADR-028). B1 opcional (2 tests + import-linter) — no abierto.

---

## 2. PROTOCOLO OBLIGATORIO del nuevo agente — VIGENTE

1. **Read-first:** backlog §0 · `PROJECT_STATE.md` §2b · `plan-split-backtests-page-2026-08-22.md` · este doc.
2. **Una fase = un subagente acotado** + verificación coordinador + batería + aprobación por commit + push `main`.
3. **Anti-saturación:** este chat anterior cerró tras F4′–F6′. **Abrir chat nuevo** para backtests B1+.

### Batería mínima (web)

```bash
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web lint
pnpm --filter @bolsa/web test
```

---

## 3. Deudas / decisiones pendientes (NO auto-cerrar)

| Ítem                       | Estado / regla                                                                        |
| -------------------------- | ------------------------------------------------------------------------------------- |
| **Split backtests B1–B12** | **SIGUIENTE** — plan `plan-split-backtests-page-2026-08-22.md` · 1 fase = 1 subagente |
| **Purge storage V2**       | MONITOR · revisión métricas ~2026-09-19 (4 sem)                                       |
| **Ops manuales**           | secret scanning UI · `TRUSTED_PROXIES` prod · `BP/.L`→`BP.L` · `logs/dev`             |
| **F9 B1** (opcional)       | 2 tests market→domain + import-linter — solo si propietario abre                      |
| **Motor money**            | freeze                                                                                |
| **Gobernanza IA**          | freeze                                                                                |
| **`contract:gen`**         | freeze salvo fase pactada                                                             |

---

## 4. TEXTOS DE PASO PARA EL NUEVO AGENTE (pegar directamente)

### 4.1 Brief de arranque (nuevo chat principal)

> CONTEXTO (2026-08-23, firma verificada): repo `Bolsa_V1`, `main` = `2eba070`, árbol **limpio**, **R-13 CERRADA**, **Track B EN CURSO**. Research→Radar **F4′–F6′ HECHAS** (`240c846`). Audit-pack v2 (`b2ee0f2`). Tag **`v1.6.0-beta` → `c3964fc`**.
> **LEE PRIMERO:** `traspaso-relevo-track-b-f4-f6-apertura-backtests-b1-2026-08-23.md` · backlog §0 · `PROJECT_STATE.md` §2b · `plan-split-backtests-page-2026-08-22.md`.
> **Tarea inmediata:** abrir **backtests B1** (constantes/tipos) — un subagente, ficheros disjuntos, sin tocar `backtest-orchestration.ts` lógica. Batería web completa. NO commits sin aprobación.
> **NO tocar:** motor money · gobernanza IA · purge storage alto · `contract:gen` · paralelizar B7+B8.

### 4.2 Brief subagentes (patrón)

> Una fase = subagente acotado: read-first backlog §0 + plan split §3 fase Bx + archivos exactos + qué NO tocar + batería esperada + **NO commits ni push** + reporte file:line. Coordinador re-verifica antes de proponer commit.

---

## 5. Enlaces

- Plan split: `plan-split-backtests-page-2026-08-22.md`
- Plan Research→Radar: `plan-unificacion-research-radar-2026-08-21.md` (F4′–F6′ ✅)
- Audit-pack vivo: `audit-pack-estado-global-2026-08-22.md`
- Relevo anterior: `traspaso-relevo-cierre-r13-consolidacion-beta-siguiente-2026-08-22.md`
- Backlog: `backlog-trabajo-2026-08-20.md` §0

---

## 6. Cierres registrados (sesión 2026-08-22/23)

| Fecha      | Hito                           | Commit    |
| ---------- | ------------------------------ | --------- |
| 2026-08-23 | Track B F4′–F6′ Research→Radar | `240c846` |
| 2026-08-22 | docs post-R-13 + audit-pack v2 | `b2ee0f2` |
| 2026-08-22 | R-13 cierre documental         | `b4efeff` |

> **Siguiente:** backtests **B1** (o monitor/ops si propietario elige pausa).
