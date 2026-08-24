# Plan — R-9 F9 analytics↔market V2 desacople (Ciclo 4/5)

> **Padre:** [ADR-030](../adr/030-analytics-market-decouple-v2.md) · [plan-r9 § FASE 9](./plan-r9-refactor-hardening-2026-08-20.md) · [engineering-index](./engineering-index-2026-08-03.md) §1.
> **AsOf:** 2026-08-24 · HEAD verificado **`e3b943a`** (tag `v1.7.0-beta`) · `main` == `origin/main`.
> **Estado:** **Fase 0 (audit docs) CERRADA** en Ciclo 4/5 · **F9-A implementación NO abierta** hasta subagente aprobado.
> **Método:** citas `path:line` verificadas en disco; sin memoria.

---

## 0. Objetivo

Completar el desacople `analytics ↔ market` pendiente de R-9 FASE 9 con **alcance acotado (F9-A)**: higiene de tests, contrato import-linter, verificación de dependencias. El puente `legacy_portfolio_id` (**F9-B**) queda **fuera** de este plan.

---

## 1. Inventario verificado (Fase 0 — read-only)

### 1.1 Ciclo `src/` — RESUELTO (F4)

| Dirección          | Imports | Notas                                                             |
| ------------------ | ------- | ----------------------------------------------------------------- |
| analytics → market | **0**   | `packages/py/analytics/src/**`                                    |
| market → analytics | **0**   | `news_snapshot.py:11-15` usa `bolsa_domain.entities.market_event` |

Tipos movidos a domain (F4): `MarketEvent`, `MarketEventCalendar`, `EventBlackoutContext`, `build_market_event`, `event_decay_weight` (`bolsa_domain/entities/market_event.py`); `prefer_summary_excerpt` (`bolsa_domain/value_objects/excerpt.py`).

### 1.2 Violaciones residuales — tests only

| ID  | File                                                | Line | Import                                                                          | Fix F9-A1                                                               |
| --- | --------------------------------------------------- | ---- | ------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| V1  | `packages/py/market/tests/test_news_snapshot.py`    | 5    | `from bolsa_analytics.cognitive import MarketEventCalendar`                     | → `bolsa_domain.entities.market_event`                                  |
| V2  | `packages/py/market/tests/test_filing_store_f2b.py` | 7    | `from bolsa_analytics.knowledge.filing_summary import heuristic_filing_summary` | Mover tests de resumen a `analytics/tests/`; market test solo I/O store |

### 1.3 Dependencias `pyproject.toml`

| Paquete             | Declara                                                     | Correcto         |
| ------------------- | ----------------------------------------------------------- | ---------------- |
| `bolsa-analytics`   | `bolsa-domain`, `bolsa-ai`, numpy, pandas, vectorbt, optuna | ✅ sin market    |
| `bolsa-market`      | `bolsa-domain`, pydantic, httpx                             | ✅ sin analytics |
| `bolsa-application` | domain + analytics + market                                 | ✅ orquestación  |

### 1.4 import-linter (`packages/py/.importlinter`)

Contratos actuales (4/4, verdes post F9-A2):

| Contrato                        | Tipo         | Alcance                                                |
| ------------------------------- | ------------ | ------------------------------------------------------ |
| `domain-purity`                 | forbidden    | domain → no infra/analytics/application/ai/api/SDK LLM |
| `no-ai-sdk-outside-bolsa-ai`    | forbidden    | capas → no openai/ollama directo                       |
| `no-ai-package-in-domain`       | forbidden    | domain → no bolsa_ai                                   |
| `analytics-market-independence` | independence | bolsa_analytics ↔ bolsa_market sin imports cruzados    |

**F9-A2 (2026-08-24):** contrato `analytics-market-independence` añadido (ADR-030 §2.3). `lint-imports` 4/4 KEPT (441 files, 2156 deps). CI Python aún **no** invoca lint-imports — propuesta A2.3 en fase separada.

### 1.5 Re-export compat (no violación, deuda menor)

`packages/py/analytics/src/bolsa_analytics/cognitive/__init__.py:3-9` re-exporta `MarketEvent*` desde domain. Consumidores legacy pueden importar vía analytics; **no crea ciclo**.

### 1.6 F9-B inventario (referencia — NO ejecutar en F9-A)

`legacy_portfolio_id` — ~34 ficheros Python en `packages/py/**`, más:

- `apps/api-python/src/bolsa_api/schemas/accounts.py`
- `apps/api-python/src/bolsa_api/schemas/account_mappers.py`
- `packages/shared/src/accounts.ts`

Requiere ADR + migración + `contract:gen`. **PARKED.**

---

## 2. Fases

### Fase 0 — Audit read-only + docs ✅ (Ciclo 4/5)

| #   | Entregable                  | Estado  |
| --- | --------------------------- | ------- |
| 0.1 | Mapa violaciones file:line  | ✅ §1.2 |
| 0.2 | ADR-030 alcance F9-A / F9-B | ✅      |
| 0.3 | Este plan + traspaso        | ✅      |
| 0.4 | Backlog §0 RELEVO mínimo    | ✅      |

**Cero código · cero commit · cero push.**

---

### F9-A1 — Higiene tests (implementación)

**Alcance:** solo `packages/py/market/tests/` + posible nuevo fichero `packages/py/analytics/tests/test_filing_summary_heuristic.py`.

| #    | Tarea     | Detalle                                                                                                    |
| ---- | --------- | ---------------------------------------------------------------------------------------------------------- |
| A1.1 | Fix V1    | `test_news_snapshot.py:5` → import domain                                                                  |
| A1.2 | Fix V2    | Extraer tests que usan `heuristic_filing_summary` a analytics; `test_filing_store_f2b.py` queda store-only |
| A1.3 | Verificar | `rg 'bolsa_analytics' packages/py/market` → 0 matches                                                      |

**Batería A1:**

| Comando                                                                                                   | Objetivo |
| --------------------------------------------------------------------------------------------------------- | -------- |
| `pytest packages/py/market/tests/test_news_snapshot.py packages/py/market/tests/test_filing_store_f2b.py` | verde    |
| `pytest packages/py/analytics/tests/test_filing_summary*.py` (nuevo)                                      | verde    |
| `ruff check packages/py/market packages/py/analytics`                                                     | 0        |

---

### F9-A2 — Contrato import-linter (implementación) ✅ CERRADO 2026-08-24

**Alcance:** `packages/py/.importlinter` + documentación en README py si aplica.

| #    | Tarea                                           | Detalle                                                                                   | Estado |
| ---- | ----------------------------------------------- | ----------------------------------------------------------------------------------------- | ------ |
| A2.1 | Añadir contrato `analytics-market-independence` | type `independence`, modules `bolsa_analytics` + `bolsa_market`                           | ✅     |
| A2.2 | CI/local                                        | `lint-imports --config packages/py/.importlinter` → 4/4 verde (441 files, 2156 deps)      | ✅     |
| A2.3 | Opcional CI step                                | Python CI **no** invoca lint-imports hoy — proponer en fase separada (no bloqueante F9-A) | ⏸️     |

**Batería A2:** lint-imports 4/4 ✅ · ruff N/A (INI) · regresión pytest market+analytics (coordinador).

**Nota entorno:** `lint-imports.exe` bloqueado por App Control Policy (os 4551); verificado vía `python -c "… importlinter.cli …"`.

---

### F9-A3 — Cierre docs (implementación)

| #    | Tarea                                                   | Detalle                             |
| ---- | ------------------------------------------------------- | ----------------------------------- |
| A3.1 | Actualizar `plan-r9-refactor-hardening` § FASE 9 estado | F9-A cerrada                        |
| A3.2 | `PROJECT_STATE.md` + backlog update-last                | commit coordinador                  |
| A3.3 | Traspaso cierre F9-A                                    | `traspaso-relevo-r9-f9-cierre-*.md` |

---

### F9-B — Puente legacy (PARKED — fuera de alcance)

| #   | Entregable                            | Prerrequisitos                                  |
| --- | ------------------------------------- | ----------------------------------------------- |
| B1  | ADR deprecación `legacy_portfolio_id` | Decisión propietario · ventana sin freeze money |
| B2  | Migración Alembic + backfill strategy | ADR B1                                          |
| B3  | OpenAPI + `contract:gen` pactado      | ADR B1                                          |
| B4  | Eliminar bridge en repos/application  | B2+B3                                           |

**NO abrir en Ciclo 4/5 ni sin ADR propio.**

---

## 3. NO TOUCH

| Zona                                                              | Motivo               |
| ----------------------------------------------------------------- | -------------------- |
| `packages/py/application/src/bolsa_application/accounts/trade.py` | Motor money          |
| Ledger / custodia / idempotency repos                             | Freeze parcial       |
| `pending-delete/**` riesgo alto                                   | Purge V2 monitor     |
| Workers / `scheduler_worker.py`                                   | R-8C.2 diferido      |
| `packages/py/ai/**` gobernanza                                    | Freeze IA            |
| `contract:gen` / OpenAPI                                          | Solo F9-B futuro     |
| Re-export `MarketEvent*` en analytics                             | Mantener compat F9-A |

---

## 4. Orden de subagentes (implementación)

```text
Fase 0 (docs) ──► F9-A1 (tests) ──► F9-A2 (import-linter) ──► F9-A3 (docs cierre)
                      │                    │
                      └──── batería ───────┘
```

**Un subagente por slice** · alcances disjuntos · coordinador re-verifica diffs + batería antes de commit.

---

## 5. Brief subagente F9-A1 (pegar al abrir implementación)

```
CONTEXTO (2026-08-24): HEAD e3b943a, tag v1.7.0-beta. Ciclo 4/5 DOCS CERRADO (ADR-030 + este plan).
Misión: F9-A1 — higiene tests analytics↔market. SIN import-linter aún (→ F9-A2).

LEE PRIMERO:
- docs/adr/030-analytics-market-decouple-v2.md §1.3, §2.2
- docs/engineering/plan-r9-f9-analytics-market-2026-08-24.md §2 F9-A1

TAREAS:
1. test_news_snapshot.py:5 → import MarketEventCalendar from bolsa_domain.entities.market_event
2. test_filing_store_f2b.py:7 → quitar import analytics; mover tests heuristic a analytics/tests/
3. rg 'bolsa_analytics' packages/py/market → 0

NO TOCAR: src/ producción, application, infra, contract:gen, legacy_portfolio_id.

BATERÍA: pytest market tests tocados + analytics tests nuevos · ruff 0 · NO commit sin aprobación.
```

---

## 6. Referencias

- [ADR-030](../adr/030-analytics-market-decouple-v2.md)
- [ADR-028](../adr/028-r9-f9-analytics-market-deferred.md)
- [traspaso F4](./traspaso-f4-arquitectura-python-2026-08-11.md)
- [traspaso apertura F9](./traspaso-relevo-r9-f9-apertura-2026-08-24.md)
- [traspaso cierre R-9 F1-F8](./traspaso-relevo-cierre-r9-f1-f8-apertura-f9-2026-08-20.md)
