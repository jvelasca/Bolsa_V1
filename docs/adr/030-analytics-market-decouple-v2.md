# ADR-030: R-9 F9 analytics↔market — alcance V2 desacople (estado verificado 2026-08-24)

**Estado:** Aceptado (docs-only; implementación F9-A requiere plan aprobado)  
**Fecha:** 2026-08-24  
**Contexto:** Ciclo 4/5 post-tag `v1.7.0-beta` · propietario aprobó abrir los 5 ciclos en orden · [ADR-028](./028-r9-f9-analytics-market-deferred.md) difería F9; este ADR **reabre F9 con alcance acotado**.

**Depende de:** [plan-r9 § FASE 9](../engineering/plan-r9-refactor-hardening-2026-08-20.md) · [traspaso F4](../engineering/traspaso-f4-arquitectura-python-2026-08-11.md) (P0.6 ciclo roto) · [ADR-028](./028-r9-f9-analytics-market-deferred.md) (estado base verificado).

**Plan de ejecución:** [`plan-r9-f9-analytics-market-2026-08-24.md`](../engineering/plan-r9-f9-analytics-market-2026-08-24.md)

---

## 1. Contexto

### 1.1 Historia

La auditoría original (pre-F4) reportó ciclo `bolsa_analytics ↔ bolsa_market`. **F4 (2026-08-11)** movió tipos compartidos a `bolsa_domain` y rompió el ciclo en **`src/`** (ver `traspaso-f4-arquitectura-python-2026-08-11.md` § P0.6).

**ADR-028 (2026-08-22)** verificó el estado en HEAD `b4efeff` y **difirió** F9 (Opción A) por freeze R-13. El propietario **aprobó reabrir F9** como Ciclo 4/5 (docs-only en este paso).

### 1.2 Estado verificado (HEAD `e3b943a`, tag `v1.7.0-beta`)

| Ítem                                    | Resultado                        | Evidencia                                                                             |
| --------------------------------------- | -------------------------------- | ------------------------------------------------------------------------------------- |
| `analytics → market` en `src/`          | **0 imports**                    | `rg 'from bolsa_market\|import bolsa_market' packages/py/analytics/src` → vacío       |
| `market → analytics` en `src/`          | **0 imports**                    | `news_snapshot.py:11-15` importa `bolsa_domain.entities.market_event`, no analytics   |
| `market/tests → analytics`              | **2 ficheros**                   | ver §1.3                                                                              |
| `pyproject.toml` analytics              | **NO declara** `bolsa-market`    | `packages/py/analytics/pyproject.toml:6-13`                                           |
| `pyproject.toml` market                 | **NO declara** `bolsa-analytics` | `packages/py/market/pyproject.toml:6-10`                                              |
| `application` declara ambos             | **Sí (orquestación)**            | `packages/py/application/pyproject.toml:6-10`                                         |
| Re-export compat `MarketEvent*`         | **Activo**                       | `bolsa_analytics/cognitive/__init__.py:3-9` re-exporta desde domain                   |
| Contrato import-linter analytics↔market | **No existe**                    | `packages/py/.importlinter` — 3 contratos (domain-purity, no-ai-sdk, no-ai-in-domain) |
| Puente `legacy_portfolio_id`            | **Activo**                       | ~34 ficheros Python + OpenAPI/shared (ver plan F9-B)                                  |

**Nota:** `uv run lint-imports` no ejecutable en este entorno (App Control Policy); contratos existentes documentados como verdes en ADR-028. Re-verificar en CI/subagente implementación.

### 1.3 Violaciones file:line (mapa verificado)

| #   | Dirección                | Archivo                                             | Línea | Import                                                                          |
| --- | ------------------------ | --------------------------------------------------- | ----- | ------------------------------------------------------------------------------- |
| V1  | market/tests → analytics | `packages/py/market/tests/test_news_snapshot.py`    | 5     | `from bolsa_analytics.cognitive import MarketEventCalendar`                     |
| V2  | market/tests → analytics | `packages/py/market/tests/test_filing_store_f2b.py` | 7     | `from bolsa_analytics.knowledge.filing_summary import heuristic_filing_summary` |

**No hay ciclo cerrado:** analytics no importa market en ningún path (`src/` ni `tests/`).

### 1.4 Grafo objetivo (ya cumplido en producción)

```text
bolsa_domain
    ↑           ↑
bolsa_analytics   bolsa_market     (independientes — sin arista cruzada)
    ↑           ↑
    └─── bolsa_application ───┘    (orquesta ambos; permitido)
            ↑
    bolsa_infrastructure / bolsa_api
```

---

## 2. Decisión

### 2.1 Dividir F9 en dos tracks

| Track                          | Alcance                                                                    | Riesgo                | Este ADR                                     |
| ------------------------------ | -------------------------------------------------------------------------- | --------------------- | -------------------------------------------- |
| **F9-A — Higiene + guardrail** | Corregir V1/V2 · contrato import-linter `independence` · re-verificar deps | **Bajo**              | **IN SCOPE**                                 |
| **F9-B — Puente legacy**       | Deprecar `legacy_portfolio_id` (DB + API + migración)                      | **Alto** (money path) | **OUT OF SCOPE** — ADR propio + fase pactada |

**ADR-028 Opción A queda parcialmente superseded:** el diferimiento global cede a **F9-A acotado**; **F9-B sigue diferido** (freeze money / `contract:gen`).

### 2.2 F9-A — Correcciones aprobadas (diseño, no implementadas)

| Violación                                        | Fix propuesto                                                                                                                                                                                                                                    | Rationale                                                                |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------ |
| **V1** `MarketEventCalendar` vía analytics       | Importar `from bolsa_domain.entities.market_event import MarketEventCalendar`                                                                                                                                                                    | Tipo canónico desde F4; re-export analytics es compat-only               |
| **V2** `heuristic_filing_summary` en test market | **Opción preferida:** mover aserciones de resumen heurístico a `packages/py/analytics/tests/` (test de `filing_summary.py`); el test market (`test_filing_store_f2b.py`) conserva solo I/O de `filing_store` + `prefer_summary_excerpt` (domain) | Evita arista test market→analytics; respeta frontera knowledge vs ingest |

**Alternativa V2 (no preferida):** mover `heuristic_filing_summary` a `bolsa_domain` — rechazada: mezcla narrativa/heurística de knowledge en domain puro.

### 2.3 Contrato import-linter (diseño)

Añadir a `packages/py/.importlinter`:

```ini
[importlinter:contract:analytics-market-independence]
name = analytics y market no se importan entre sí
type = independence
modules =
    bolsa_analytics
    bolsa_market
```

**Alcance:** solo módulos bajo `src/bolsa_*` (root packages). Los tests en `packages/py/market/tests/` **no** entran en el grafo import-linter por defecto — por eso V1/V2 persisten sin fallar lint-imports hoy. F9-A corrige tests **y** añade el contrato como guardrail futuro.

### 2.4 Re-export compat `bolsa_analytics.cognitive.MarketEvent*`

**Decisión:** **mantener** en F9-A (no breaking). Deprecación documental opcional en docstring del `__init__.py`; eliminación en fase posterior si grep de consumidores → 0 fuera de re-export.

### 2.5 F9-B — Puente `legacy_portfolio_id` (diferido)

Permanece **fuera de F9-A**. Requiere:

- ADR dedicado (migración DB, cardinalidad portfolio, OpenAPI)
- `contract:gen` pactado
- Ventana sin freeze money

Inventario aproximado: ~34 ficheros `packages/py/**`, `apps/api-python` schemas, `packages/shared/src/accounts.ts`.

---

## 3. Consecuencias

### Positivas

- Criterio R-9 F9 **parcialmente cumplido** tras F9-A: sin ciclo src, tests limpios, import-linter con contrato explícito, deps ya declaradas correctamente.
- Guardrail CI evita regresión del ciclo F4.

### Negativas / limitaciones

- F9-B sigue como deuda V2; no cierra R-9 plan § FASE 9 al 100% (puente legacy pendiente).
- Re-export analytics→domain añade indirección hasta limpieza futura.

### NO TOUCH (F9-A)

- Motor money / ledger / ExecuteTrade
- `pending-delete` riesgo alto
- Workers R-8C.2 / scheduler
- Gobernanza IA
- `contract:gen` (salvo fase F9-B futura)
- Migraciones DB (F9-A es tests + import-linter only)

---

## 4. Criterios de aceptación

| Criterio                               | F9-A           | F9-B        |
| -------------------------------------- | -------------- | ----------- |
| 0 imports cruzados `src/`              | ✅ ya cumplido | —           |
| 0 imports cruzados tests               | Tras F9-A1     | —           |
| import-linter verde (+ contrato nuevo) | Tras F9-A2     | —           |
| deps `pyproject.toml` declaradas       | ✅ ya cumplido | —           |
| Puente legacy deprecado                | —              | F9-B futuro |

**Batería F9-A esperada:** ruff 0 · mypy 0 ficheros tocados · pytest market + analytics sin regresión · `lint-imports` 4/4 contratos verdes.

---

## 5. Referencias

- [`plan-r9-refactor-hardening-2026-08-20.md`](../engineering/plan-r9-refactor-hardening-2026-08-20.md) § FASE 9
- [`plan-r9-f9-analytics-market-2026-08-24.md`](../engineering/plan-r9-f9-analytics-market-2026-08-24.md)
- [`traspaso-relevo-r9-f9-apertura-2026-08-24.md`](../engineering/traspaso-relevo-r9-f9-apertura-2026-08-24.md)
- [`traspaso-f4-arquitectura-python-2026-08-11.md`](../engineering/traspaso-f4-arquitectura-python-2026-08-11.md)
- [ADR-028](./028-r9-f9-analytics-market-deferred.md)
