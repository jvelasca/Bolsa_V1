# F0.5/F0.6 — Plan de implementación (código) — CERRADO

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (Product / Ops).
> **AsOf:** 2026-08-24 · ancla viva `git fetch; git rev-parse origin/main` = **`36dd6e3`** (`main == origin/main`).
> **Estado:** **CERRADO.** F0.5b PortfolioFit v1 (`3670a09`) · F0.6b Decision Board backend (`8df8a65`) · F0.6-UI (`672e88f`) · D2/Esc.3/D1/deuda SEMI/D3 cerradas. Cierre de auditoría 2026-08-24: H1 `proposal_sector` en SEMI + H2 fail-closed si `GetPortfolioSummary` lanza (working tree; pendiente commit).
> **Base:** [AS-IS F0.1](./fase0-decision-spine-asis-2026-08-24.md) · [TO-BE F0.2](./fase0-decision-spine-tobe-2026-08-24.md) · [Mapping F0.3](./fase0-decision-spine-mapping-2026-08-24.md) · [Descargue F0.4](./fase0-decision-spine-descarga-2026-08-24.md).

---

## 1. Qué se implementó (dos fases de código — HECHAS)

### F0.5 — PortfolioFit (único **create**) — CERRADA

- **Origen:** stub en `composite_score.py` (`portfolioConstraints` · `status="not_evaluated"`). El stub **permanece** (pata Composite no puntúa cartera); Fit vive como módulo aparte `portfolio_fit.py`.
- **Hecho:** `compute_portfolio_fit` (as-if fill, concentración activo+sector, VETO) · `MaxSectorExposure` en Policy Gate · cableado AUTO `execution_router`→`check_opening` y SEMI `confirm_recommendation`→`check_opening`.
- **Frontera respetada:** no se tocaron internals de `ExecuteTrade`.

### F0.6 — Daily Decision Board (vista, no orquestador) — CERRADA

- **Hecho:** `GetDecisionBoard` + `GET /accounts/{account_id}/decision-board` + UI `/decision-board` solo lectura.
- **Frontera respetada:** no hay `DailyOrchestrator`.

---

## 2. Orden ejecutado

| Orden | Fase        | Estado | Commit / nota                                     |
| ----- | ----------- | ------ | ------------------------------------------------- |
| 1     | **F0.5a**   | ✅     | métrica = concentración cesta activo+sector, VETO |
| 2     | **F0.5b**   | ✅     | `3670a09`                                         |
| 3     | **F0.6a/b** | ✅     | backend `8df8a65`                                 |
| 4     | **F0.6-UI** | ✅     | `672e88f` (`contract:gen` pactado)                |

> F0.5/F0.6 **no se reabren**. El cierre de auditoría (H1/H2) es parche acotado sobre el confirm SEMI, no una nueva fase Fit/Daily.

---

## 3. Riesgo y anti-objetivos (siguen vigentes)

- **NO** reabrir `ExecuteTrade` internals ni motor money (congelado).
- **NO** `contract:gen` salvo fase pactada explícita.
- **NO** tocar Belief, gobernanza IA, Track B B1–B12, `pending-delete` E8.
- Fit sigue siendo el **único create** del spine; Ranking / OrderProposal / Attribution = no-op (F0.3).

---

## 4. Criterio de parada — cumplido

1. Propietario aprobó F0.5 y F0.6. D1/D2/D3 cerradas.
2. Métrica de encaje y fuente Daily (Decision Board) acordadas.
3. Código + tests + relevos en `main` hasta `36dd6e3`. H1/H2 en working tree (cierre auditoría).

---

## 5. Cierre de auditoría 2026-08-24 (H1 / H2)

| Id     | Decisión                                                                                                                                                   | Código                                                                                              |
| ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| **H1** | SEMI resuelve `proposal_sector` desde `instruments.sector` (mismo SoT que AUTO `hit.sector`)                                                               | `confirm_recommendation.py` `_resolve_proposal_sector` + DI `instruments=get_instrument_repository` |
| **H2** | Si `GetPortfolioSummary` está inyectado y **lanza** → fail-closed (`risk_veto`). Alineado con D1 (sin override). `portfolio_summary=None` no aplica cesta. | `_risk_allows_opening`                                                                              |

Batería del cierre: ruff 0 (ficheros tocados) · mypy confirm 0 · pytest confirm+fit+board **49 passed** · vitest Decision Board **6/6** · `tsc -b --noEmit` 0.
