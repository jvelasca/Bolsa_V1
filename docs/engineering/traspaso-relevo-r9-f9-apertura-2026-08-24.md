# RELEVO / TRASPASO — R-9 F9 analytics↔market · apertura Ciclo 4 (docs) → F9-A implementación

> **Padre:** [ADR-030](../adr/030-analytics-market-decouple-v2.md) · [plan-r9-f9-analytics-market-2026-08-24.md](./plan-r9-f9-analytics-market-2026-08-24.md) · [plan-r9 § FASE 9](./plan-r9-refactor-hardening-2026-08-20.md).
> **Propósito:** handoff del subagente **docs-only Ciclo 4/5** al **subagente F9-A implementación**.
> **AsOf:** 2026-08-24.

---

## 1. Estado verificado (firma — no adivinar)

| Campo                    | Valor                                                   |
| ------------------------ | ------------------------------------------------------- |
| **HEAD**                 | `e3b943a9003074a4f5bdbf5790da6b651bffa691`              |
| **Tag**                  | `v1.7.0-beta` (exact match HEAD)                        |
| **Rama**                 | `main` == `origin/main`                                 |
| **Working tree**         | docs Ciclo 4 añadidos (sin commit)                      |
| **Decisión propietario** | Abrir **5 ciclos en orden**; Ciclo 4 = R-9 F9 docs-only |

---

## 2. Qué se creó en Ciclo 4 (docs-only)

| Archivo                                                         | Rol                                                               |
| --------------------------------------------------------------- | ----------------------------------------------------------------- |
| `docs/adr/030-analytics-market-decouple-v2.md`                  | Decisión: F9-A (higiene+guardrail) vs F9-B (legacy bridge PARKED) |
| `docs/engineering/plan-r9-f9-analytics-market-2026-08-24.md`    | Fases Fase 0 / F9-A1–A3 / F9-B parked                             |
| `docs/engineering/traspaso-relevo-r9-f9-apertura-2026-08-24.md` | Este handoff                                                      |
| `docs/engineering/backlog-trabajo-2026-08-20.md` §0             | RELEVO mínimo Ciclo 4                                             |

**Cero commits** · **cero push** · **cero código Python/TS** (salvo docs).

---

## 3. Hallazgos clave (para no re-auditar)

1. **Ciclo `src/` ROTO desde F4** — 0 imports cruzados analytics↔market en producción.

2. **Deuda real = 2 tests** (no src):

   | File                                                | Line | Import                                                              |
   | --------------------------------------------------- | ---- | ------------------------------------------------------------------- |
   | `packages/py/market/tests/test_news_snapshot.py`    | 5    | `bolsa_analytics.cognitive.MarketEventCalendar`                     |
   | `packages/py/market/tests/test_filing_store_f2b.py` | 7    | `bolsa_analytics.knowledge.filing_summary.heuristic_filing_summary` |

3. **`pyproject.toml` deps ya correctas** — ni analytics ni market se declaran mutuamente.

4. **import-linter:** 3 contratos verdes; **falta** contrato `analytics-market-independence` (diseño en ADR-030 §2.3).

5. **F9-B `legacy_portfolio_id` PARKED** — ~34 ficheros Python; requiere ADR+migración+contract:gen; **NO abrir en F9-A**.

6. **`lint-imports` no ejecutado** en este entorno (App Control Policy) — re-verificar en subagente/CI.

---

## 4. Decisiones de diseño (para no re-debatir en F9-A)

1. **F9-A only** — tests + import-linter; sin tocar legacy bridge.

2. **V1 fix:** import `MarketEventCalendar` desde `bolsa_domain.entities.market_event` (canónico F4).

3. **V2 fix:** mover tests de `heuristic_filing_summary` a `analytics/tests/`; market test solo store I/O.

4. **Re-export compat** `bolsa_analytics.cognitive.MarketEvent*` — **mantener** (no breaking).

5. **Grafo permitido:** `application` importa analytics **y** market; analytics/market solo domain.

---

## 5. Brief subagente F9-A1 (implementación — primer slice)

```
CONTEXTO (2026-08-24): repo Bolsa_V1, HEAD e3b943a, tag v1.7.0-beta, main==origin/main.
Ciclo 4/5 DOCS CERRADO. Tu misión: F9-A1 — higiene tests (SIN import-linter aún).

LEE PRIMERO:
- docs/adr/030-analytics-market-decouple-v2.md
- docs/engineering/plan-r9-f9-analytics-market-2026-08-24.md (§2 F9-A1, §3 NO TOUCH)
- packages/py/market/tests/test_news_snapshot.py
- packages/py/market/tests/test_filing_store_f2b.py
- packages/py/analytics/src/bolsa_analytics/knowledge/filing_summary.py

TAREA F9-A1:
1. Fix V1: domain import en test_news_snapshot.py:5
2. Fix V2: split tests → analytics/tests/ para heuristic; market test store-only
3. Verificar: rg 'bolsa_analytics' packages/py/market → 0

NO TOCAR:
- src/ producción (ya limpio)
- legacy_portfolio_id / F9-B
- application / infrastructure / api
- contract:gen
- import-linter (→ F9-A2 subagente separado)
- Motor money / pending-delete / workers / IA

BATERÍA (esperada VERDE):
- pytest market tests tocados
- pytest analytics tests (nuevo si aplica)
- ruff check packages/py/market packages/py/analytics → 0

NO commit · NO push · devuelve diff + file:line + batería al coordinador.
```

---

## 6. Brief subagente F9-A2 (segundo slice — tras A1)

```
Misión: F9-A2 — contrato import-linter analytics↔market independence.
Alcance: packages/py/.importlinter únicamente (+ verificar CI si ya invoca lint-imports).
Prerrequisito: F9-A1 cerrado (tests limpios).
Batería: uv run lint-imports --config packages/py/.importlinter → 4/4 verde.
Ver ADR-030 §2.3 para snippet del contrato.
```

---

## 7. Secuencia ciclos 5/5 (contexto coordinador)

| Ciclo | Tema                          | Estado al redactar                 |
| ----- | ----------------------------- | ---------------------------------- |
| 1     | OrderProposal/Journal         | F1 working tree (pendiente commit) |
| 2     | Audit-pack 24d                | CERRADO docs                       |
| 3     | Monitor Purge V2+ops          | CERRADO docs                       |
| **4** | **R-9 F9 analytics↔market**   | **DOCS CERRADO (este relevo)**     |
| 5     | (siguiente según propietario) | Pendiente                          |

---

## 8. Enlaces

- Backlog §0: `docs/engineering/backlog-trabajo-2026-08-20.md`
- ADR previo diferido: `docs/adr/028-r9-f9-analytics-market-deferred.md`
- F4 evidencia ciclo roto: `docs/engineering/traspaso-f4-arquitectura-python-2026-08-11.md`
- import-linter config: `packages/py/.importlinter`
- Traspaso R-9 original F9: `docs/engineering/traspaso-relevo-cierre-r9-f1-f8-apertura-f9-2026-08-20.md`
