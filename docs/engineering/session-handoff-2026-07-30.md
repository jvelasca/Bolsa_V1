# Handoff sesión 2026-07-30 (cierre + pausa)

> **Superseded para operativa DÍA D / CORE-R:** [`session-handoff-2026-07-31.md`](./session-handoff-2026-07-31.md).  
> Retomar FA / pause audit con [`product-pause-audit-2026-07-30.md`](./product-pause-audit-2026-07-30.md).  
> Complementa [`list-auto-ops-2026-07-29.md`](./list-auto-ops-2026-07-29.md) ·  
> [`backtesting-funnel-handoff-2026-07-29.md`](./backtesting-funnel-handoff-2026-07-29.md) ·  
> Ayuda → Backtesting (`backtesting-tracker.ts`).

**As-of Ayuda:** `HELP_CONTENT_AS_OF` = **2026-07-30**.  
**Backup docs:** `docs/engineering/backups/2026-07-30/`.

---

## 1. Qué quedó listo hoy

| Área | Qué |
|------|-----|
| Deuda operativa | Prevención runId en TOP · backfill · `audit:ibex35:missing` · AENA closed |
| Lista AUTO ops | Play sobre **IBEX 35** + frescura · lista «IBEX sin TOP» = ops a borrar (no producto) |
| Keep-alive | Campaña sigue al ir a Trading · chip en barra estado · badge Backtesting |
| Anti-hang | Universo 0 OK / Lab sin jobs / failed / watchdog 8 min → siguiente ticker |
| Frescura v1.2 | Omitir **solo con Finalistas reales** · Eliminar Finalistas limpia huella |
| CORE-P deep-dive | Familias Lab por horizonte + aviso mismatch perfil en Finalistas |
| Mapa IA | Ya en Ayuda → Plataforma IA (marcado hecho) |
| Embudo UX | Rail **5 etapas** · soft-ACK latch · prefs Auto-ACK / Pausar · settle `finalistsSaved`/`Skipped` |
| **Listas / índices v1.0** | Catálogo mundial · Suscribir A→B→C · familias hub · congelar · Últ. sync · soft-cap AUTO · resumen estado en Universo Lista · clic → Valor |
| **FA / FIE F0** | Diseño FIE + contrato shared/Python v3 + `fcfYield` · Piotroski aplazado F2 · ver `fundamental-intelligence-engine-2026-07-30.md` |
| Pausa producto | Auditoría eficacia — FA track activo (no pausado) |

### Cómo debe comportarse Lista AUTO (usuario)

1. Universo → **Lista IBEX 35** → ciclo ON → **Play** (no «Probar lista»). Si aparece «IBEX… SIN TOP», elimínala.
2. Pref «**Omitir si Finalistas frescos**» ON.
3. Puedes ir a **Trading**: footer muestra `Lista AUTO n/N · SYM · fase…`.
4. Tras **reinicio** app+API: segundo Play **omite** solo valores **con** Finalistas si no hay barra/contexto nuevo.
5. **Reevaluar resto** = forzar. **Eliminar Finalistas** en panel TOP = vaciar + reanalizar (Biblioteca ≠ TOP).

### Comandos útiles

```bash
pnpm test:coach
pnpm audit:ibex35
pnpm audit:ibex35:missing
pnpm --filter @bolsa/web exec vitest run \
  src/features/backtests/backtest-finalists-freshness.test.ts \
  src/features/backtests/backtest-finalists-freshness-restart.test.ts \
  src/features/backtests/backtest-run-context.test.ts
```

---

## 2. Pendiente (prioridad)

| # | Track | Notas |
|---|--------|--------|
| 1 | **FA / FIE → F1** | F0 cerrado (contrato v3 + `fcfYield`). Siguiente: panel Valor + chip lista. Diseño: `fundamental-intelligence-engine-2026-07-30.md` |
| 2 | **F1b copiloto** | Ollama explica Score_FUND + facts; no calcula |
| 3 | **Smoke frescura live** | Reinicio real → Play IBEX → tablero mayoritariamente Omitido |
| 4 | **CORE-R / CORE-P / Monitor** | Paralelo; no bloquea F1 |
| — | Auto-paper **D** | **Congelado** hasta ranking TA+FA+perfil (F3) |
| — | Piotroski / SEC RAG | F2 / F2b |

---

## 3. Docs / Ayuda tocados

| Archivo | Qué |
|---------|-----|
| `docs/HELP.md` | Sync 2026-07-30 · enlaces handoff + list-auto-ops |
| `docs/engineering/session-handoff-2026-07-30.md` | Este cierre |
| `docs/engineering/list-auto-ops-2026-07-29.md` | Frescura v1.1 · keep-alive · anti-hang · guía usuario |
| `docs/engineering/research-lifecycle.md` | Sync + tabla Lista AUTO |
| `docs/engineering/backtesting-funnel-handoff-2026-07-29.md` | Pointer → este handoff |
| `apps/web/.../help-content-as-of.ts` | `2026-07-30` |
| `apps/web/.../help-registry.ts` | Fuentes Backtesting |
| `apps/web/.../backtesting-tracker.ts` | Resumen · pasos · tracking · NEXT · idea frescura |
| `apps/web/.../ai-platform-tracker.ts` | Nota Lista AUTO frescura v1.1 |
| `research/observations/ISSUES.md` | frescura-restart Fixed · CORE-P / CORE-R |

**Código de soporte (ya en árbol):**  
`backtest-finalists-freshness.ts` · `backtest-run-context.ts` · `list-auto-activity-store.ts` · `platform-shell.tsx` · `trading-status-bar.tsx` · `backtests-page.tsx`.

---

## 4. Congelado (no tocar sin decisión)

Auto-paper D · Discovery/Planner · Belief UI deep · unificar A+B · Lab UI P3–P9 deep.

---

## 5. Arranque mañana (checklist 5 min)

1. API + web up · `pnpm audit:ibex35:missing` (sanity).
2. Backtesting → Lista IBEX · prefs ciclo + omitir ON → **Play**.
3. Esperado: mayoría **Omitido** (si no hubo barra nueva).
4. Si falla: mirar fingerprint / perfil listo / `bolsa-backtest-run-context-v1` · doc §3 frescura en list-auto-ops.
5. Luego: CORE-R (ISSUES crítico) o CORE-P E2E según energía.
