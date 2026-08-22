# PLAN R-13 — Cierre R-12 y consolidación BETA (2026-08-22)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (`Product / Ops`).
> **Ancla:** `docs/engineering/PROJECT_STATE.md` §2ad · `docs/engineering/backlog-trabajo-2026-08-20.md` §0 · premisas ⭐§0.
> **Supersede:** el ciclo vivo deja de ser R-12. R-12 queda **CERRADA** (`plan-r12-auditoria-ux-2026-08-21.md`).
> **Partida (verificada):** `origin/main` = **`5edbcb5`** · tag **`v1.5.0-beta` → `5e52bd6`** · tag `v1.3.0` → `b778292` intacto · `v1.5.0-beta-39-g5edbcb5`.
> **Estado del plan:** A0–A2 **HECHAS** + A3 **HECHA** (tag `v1.6.0-beta` = `c3964fc` pusheado). Track B producto **BLOQUEADO**.

---

## 0. Anti-alucinación — qué NO se repite

R-12 cerró la reparación post-auditoría. **Prohibido** reabrir:

- R-11 · Relevo UNO/DOS · Track A–C · R12-409 · EXEC-B-CONC · R12-SCHED · R12-ACCOUNTS
- R12-AUTH F1–F10 + F8b–F8e · F7b apply **local** · F7c · JWT-only · `scan.completed` + cron stamp
- Motor money · `PAPER_D_EXECUTE` · gobernanza IA · Belief/H
- Purge `pending-delete` alto · apply F7b prod · `contract:gen` salvo fase · split `backtests-page` · fusión Research→Radar

## 1. Protocolo (serie)

1. Una fase = un subagente. Paralelo solo con ficheros disjuntos y sin pisar estado vivo.
2. Tests en cada fase de código. Coordinador re-verifica file:line + batería.
3. Firma: `git fetch && git rev-parse origin/main` + `git status` antes de tocar.
4. Saturación → traspaso + chat nuevo. Documento manda.

## 2. Fases

| Fase                   | Estado        | Entregable                                                                                            |
| ---------------------- | ------------- | ----------------------------------------------------------------------------------------------------- |
| A0 cierre + firma      | HECHA         | este plan · premisas ciclo R-13 · SHA `5edbcb5` · README `v1.5.0-beta` · CHANGELOG `[Unreleased]` JWT |
| A1 inventario residual | HECHA         | §4 de este doc (file:line)                                                                            |
| A2 E8 micro + tests    | HECHA         | `normalizeChartNewTabSeed` purged after contract tests; extract/apply kept                            |
| A3 tag `v1.6.0-beta`   | **HECHA**     | tag `v1.6.0-beta` = `c3964fc` pusheado; `v1.5.0-beta` / `v1.3.0` no retagueados (intactos)            |
| Track B producto       | **BLOQUEADO** | god-page / Research→Radar: plan propio, OK línea a línea                                              |

## 3. Inventario residual (resumen A1)

Verificado por subagente + coordinador contra `5edbcb5` (HEAD = `origin/main`).

## 4. Inventario A1 (evidencia file:line)

### 4.1 Docs/ADR desfasados

| Ítem                     | Evidencia                                                                                                                                                | Veredicto              |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- |
| JWT-only; no `tokens.py` | `apps/api-python/src/bolsa_api/auth/` = `jwt.py` · `session.py` · `principal.py` · `roles.py` · `request_principal.py`. Middleware `middleware/auth.py`. | KEEP-DOC (código vivo) |
| ADR-004 §0 flujo HMAC    | `docs/adr/004-prorealtime-ui-platform.md:29` «token HMAC determinista, no JWT»                                                                           | KEEP-DOC (banner A1)   |
| ADR-027 Contexto pre-JWT | `docs/adr/027-auth-multi-user-jwt-hybrid.md:16-17` cita `tokens.py` SHA-256; cabecera ya dice JWT-only                                                   | KEEP-DOC (banner A1)   |
| Plan D4 §1               | `plan-r12-auth-d4-jwt-multiuser-2026-08-22.md:17-19` ya HISTÓRICO (A0)                                                                                   | MONITOR                |

### 4.2 Ops fuera de repo

| Ítem                   | Checklist                                          | Veredicto        |
| ---------------------- | -------------------------------------------------- | ---------------- |
| `TRUSTED_PROXIES` prod | `ops-r1-seguridad-operaciones-2026-08-19.md:36-41` | MONITOR (manual) |
| Secret scanning UI     | mismo ops § secret scanning                        | MONITOR          |
| `BP/.L` → `BP.L` en BD | ops-r1 + PROJECT_STATE F-WORKER-1                  | MONITOR          |
| `logs/dev`             | ops-r1 · gitignore `logs/**`                       | MONITOR          |

### 4.3 Purge V2 (E8 N — no purge)

| Ítem                                                          | Reader                                        | Veredicto |
| ------------------------------------------------------------- | --------------------------------------------- | --------- |
| `readLegacyPendingOrders`                                     | `use-pending-orders.ts:17-27`, `:42-72`       | MONITOR   |
| `readLegacyTimeframeFavorites`                                | `workspace-store-core.ts:652-663`, `:748-751` | MONITOR   |
| `chartDataStrip` / `chartNewTabSeed` / `newChartConfigSource` | workspace persist                             | MONITOR   |
| Ventana T+0                                                   | 19/19 · 0 purges                              | MONITOR   |

### 4.4 E8 micro

| Ítem                                              | Evidencia                                                                           | Veredicto    |
| ------------------------------------------------- | ----------------------------------------------------------------------------------- | ------------ |
| `normalizeChartNewTabSeed`                        | **Purged R-13 A2.** Tests: `chart-new-tab-setup.test.ts` (extract/apply + absence). | **HECHO**    |
| `extractChartNewTabSeed` / `applyChartNewTabSeed` | vivos en `workspace-store-core.ts:41-42`, `:521-523`                                | **NO tocar** |

### 4.5 Parked

| Ítem                    | Evidencia                                                | Veredicto        |
| ----------------------- | -------------------------------------------------------- | ---------------- |
| `backtests-page.tsx`    | ~4698 LOC                                                | PARKED (Track B) |
| Research→Radar          | `plan-unificacion-research-radar-2026-08-21.md` APARCADO | PARKED           |
| R-9 F9 analytics↔market | `plan-r9` + traspaso R-9 F9                              | PARKED           |

## 5. Batería

Docs: SHA escrito = `git rev-parse origin/main` al abrir / al commit. Código A2: typecheck + tests de la zona.
