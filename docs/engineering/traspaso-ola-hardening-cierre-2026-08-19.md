# Traspaso — Cierre de la ola de hardening (F-IND-2 → F-HLTH-1) y relevo a F-DEBT-1 (P1.9)

- **Fecha:** 2026-08-19
- **Rama base:** `stage/f1-integridad-financiera-2026-08-11` (punto de partida de la sub-ola: merge F-IND-1 `79fa155`).
- **Cierre de sub-ola MERGEADO a `main`:** el tip de `main` tras el merge es `94aee47` (fast-forward de toda la ola F1→F5a + la sub-ola sub-integral pendiente).
- **Próxima fase pactada:** **F-DEBT-1 = P1.9 API thin** (alcance exclusivo). `mypy ~450` ya cerrado (P1.6); **P2.6 DTOs TS↔Py → F-DEBT-2** (deuda futura).

---

## 1. Lo que cierra esta sub-ola (commits ahora en `main`)

> Merge fast-forward `eb31a7d..94aee47` → `origin/main`. La sub-ola de fases F-IND-2 → F-HLTH-1 queda MERGEADA.

| Fase     | Commit    | Contenido                                                                                                         | Batería                                                                |
| -------- | --------- | ----------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| F-IND-2  | `09fb06b` | Batería de causalidad en CI (`feature_at_t` con/sin barra futura idéntico; 34 tests)                              | ruff/mypy ✓ · analytics 362✓                                           |
| F-FIN-1  | `f595761` | Fail-closed del default de cartera global (`get_or_create_default_portfolio` eliminado; scope por cuenta ADR-008) | ruff/mypy ✓ · infra 49 / app 224 / api 29                              |
| F-FIN-2  | `9a35405` | Ejercicio fiscal en `GetTaxReport` (`fiscal_year_range`; sin truncado de cost basis; fees del año)                | ruff/mypy ✓ · domain 14 / app 224 / infra 49 / api 29 + int 1          |
| F-SEG-1  | `4b7a984` | Fail-closed production + `secrets.compare_digest`                                                                 | ruff/mypy ✓ · config/auth 14 / api 29 / infra 49 / app 224 / startup 5 |
| F-SEG-2  | `dcb8a37` | Auditoría git + rotación de logs + redacción de secretos                                                          | ruff 0 · node --check OK · config 15 / hygiene 3 / infra 57            |
| F-SEG-3  | `e628ae3` | CORS mínimo privilegio + `X-Forwarded-For`/TrustedHost                                                            | ruff 0 · config/rate/cors 38 / api offline 47                          |
| F-HLTH-1 | `2400a4b` | Mojibake en `workspace-store-core.ts` (2 strings UI + ~28 JSDoc)                                                  | web typecheck 0 / lint 0 / build OK                                    |

Documentos de estado ya actualizados: `docs/engineering/PROJECT_STATE.md` (§3/§4/§6/§7) y `engineering-index-2026-08-03.md` §5 (entradas por fase).

---

## 2. Acciones pendientes acumuladas (no bloqueantes)

- **F-SEG-2 / auditoría git:** activar **GitHub secret scanning** nativo y confirmar `gitleaks.yml`; limpiar manualmente `logs/dev/*.log` (~150 MB).
- **F-SEG-3 / rate-limit:** definir `TRUSTED_PROXIES` en producción con los IPs del proxy de borde.
- **F-SEG-2:** decidir si se purga del historial público los valores dev históricos `bolsa:bolsa_dev` / `bolsa-dev-secret` (recomendación filter-repo/BFG; no es urgente, son valores de desarrollo).
- **F-IND-1/2:** la guardia de causalidad puede cambiar resultados de backtests con `chikou`; documentado, **no recalcular aún**.
- **Auth JWT:** diferida (decisión D4) hasta decidir exponer la app.

---

## 3. Próxima fase pactada — F-DEBT-1 (P1.9 API thin)

- **Alcance EXCLUSIVO:** adelgazar los endpoints de FastAPI (los proxies/serializaciones delgados actuales = deuda de F4/F5b). NO tocar P2.6 ni reabrir nada de la sub-ola.
- **Contexto fuente:** `docs/engineering/traspaso-nueva-ola-fin-refactorizacion-2026-08-12.md` §3.3 y `traspaso-cierre-refactorizacion-2026-08-12.md`.
- **Deuda ya cerrada:** `mypy ~450 por fases` (P1.6 → gate bloqueante full-tree `6a89f6c`, 0/243 files).
- **Deuda futura registrada:** F-DEBT-2 = P2.6 DTOs TS↔Py (consolidar tipos web-only en `packages/shared`: `RecommendationV1`/`CoreRVerdict`/`RunManifest`/`execution-policies`/`tax-report`, etc.).

---

## 4. Texto de traspaso (pegar en el nuevo hilo)

> **CONTEXTO:** Ola de hardening pactada 2026-08-11 terminando. Toda la ola F1→F5a + la sub-ola F-IND-2/F-FIN-1/F-FIN-2/F-SEG-1/F-SEG-2/F-SEG-3/F-HLTH-1 está **MERGEADA y PUSHEADA a `main`** (`origin/main` = `94aee47`). Working tree limpio. CI verde.
> **ESTADO VIVO + DEUDA:** `docs/engineering/PROJECT_STATE.md` (LEER PRIMERO) · mapa de fases en `engineering-index-2026-08-03.md` §5.
> **PRÓXIMA FASE:** **F-DEBT-1 = P1.9 API thin** (adelgazar endpoints FastAPI). **ALCANCE EXCLUSIVO: SOLO P1.9.** `mypy ~450` ya cerrado (P1.6, `6a89f6c`); **P2.6 DTOs TS↔Py → F-DEBT-2** (deuda futura). Riesgo Medio. Después: F-WORKER-1 (auto-sync `BP/.L`, retomar con `resume`) · F-DEBT-2.
> **Contexto de P1.9:** `docs/engineering/traspaso-nueva-ola-fin-refactorizacion-2026-08-12.md` §3.3 y `traspaso-cierre-refactorizacion-2026-08-12.md` (elección de una deuda por hilo).
> **Protocolo:** PR por fase desde el checkpoint; batería por PR (`mypy` bloqueante full-tree 0/243 · `ruff` 0 · pytest · `contract:check` bidireccional · web typecheck/lint/test · shared test); aprobación por commit; merge a `stage/f1-*`. **Saturación:** máx. ~3 subagentes en paralelo.
> **Freeze:** sin features nuevas · no reabrir Belief/H · no gobernanza IA · **auth JWT diferida (D4)** hasta decisión de exponer la app.
> **Warnings/acciones:** auto-sync `BP/.L` (Yahoo 404) → F-WORKER-1; activar GitHub secret scanning; limpiar `logs/dev/*` (~150 MB); definir `TRUSTED_PROXIES` en prod.
