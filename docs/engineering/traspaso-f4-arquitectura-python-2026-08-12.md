# Traspaso — F4 Arquitectura Python (2026-08-12)

> **Padre único:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) §5 (sub-entrada de la Auditoría consolidada, junto a F1/F2/F3a/F3b/F5a).
> **Fuentes de verdad (leer primero):** [audit-consolidado-internas-externas-2026-08-11.md](./audit-consolidado-internas-externas-2026-08-11.md) (P0.6/P1.6/P1.9 + D0–D5) · [traspaso-f3a-procesos-db-2026-08-11.md](./traspaso-f3a-procesos-db-2026-08-11.md) (§6 deuda → F4).
> **Rama de ejecución:** `stage/f4-arquitectura-python-2026-08-12` (desgajada desde `stage/f1-*`, tras merge PR #33).
> **Regla del hilo:** NO tocar código fuera del alcance F4 pactado. Cambios validados con la batería antes del commit.
> **Estado:** F4 COMPLETADO (P0.6 ✓ · 7 ruff gates ✓ · P1.6 gate scoped ✓). Ver §4–§7.

---

## 0. Alcance pactado (decisión del usuario, este hilo)

Del plan F4 (Arquitectura Python) se ejecuta en **este** hilo:

- **P0.6** — Romper el **ciclo de dependencias `analytics ↔ market`** y arreglar las deps no declaradas en `pyproject.toml`. Alcance confirmado por el usuario: **mover `MarketEvent` a domain Y mover `prefer_summary_excerpt` a domain** (a ambos lados del ciclo), de modo que `analytics` y `market` quedan como **pares que solo dependen de `domain`** (sin arista ni ciclo cruzado).
- **P1.6** — **mypy gate duro por fases.** Alcance confirmado por el usuario como **gate selectivo por fase ("files_only")**: NO bloquear todo el árbol (~451 errores preexistentes); solo bloquear (quitar `continue-on-error`) sobre los **ficheros nuevos/tocados en F4** que quedan mypy-clean. El resto del árbol mantiene `continue-on-error` hasta su fase.
- **ruff gates** — Cerrar los **7 errores de ruff** heredados de F3b/F5a: `portfolio.py` (api) y `alembic/env.py`, `001_timescaledb_extension.py`, `account_migration.py`, `migrations.py`, `portfolio_repository.py`, `test_daily_ops_digest_pdf.py` (infra).

**Excluido de F4 (deuda registrada, NO resuelta aquí):** **P1.9 (API thin** — composition root ~1100 líneas + rutas con SQL directo) hilo propio pendiente. **P0.6 deps no declaradas en `application` → `ai`** (imports dinámicos `bolsa_ai.get_default_proxy`) se mantienen (uso lazy). **D4 auth** → F5b. Deuda F5a §6 (fidelidad DTOs, `openapi-fetch`) → fase posterior.

**Anti-objetivos (D5):** cero features.

## 1. Diagnóstico confirmado en código

### P0.6 — ciclo `analytics ↔ market` + deps no declaradas

Dos aristas cruzadas (ninguna declarada en los `pyproject.toml`):

| Arista                 | Fichero                                        | Import                                                                 | pyproject afectado                    |
| ---------------------- | ---------------------------------------------- | ---------------------------------------------------------------------- | ------------------------------------- |
| **analytics → market** | `analytics/.../knowledge/filing_summary.py:10` | `from bolsa_market.filing_store import prefer_summary_excerpt`         | `analytics` NO declara `bolsa-market` |
| **market → analytics** | `market/.../news_snapshot.py:11`               | `from bolsa_analytics.cognitive.market_events import MarketEvent, ...` | `market` NO declara `bolsa-analytics` |

- `MarketEvent` + `MarketEventCalendar` + `EventBlackoutContext` + `build_market_event` + `event_decay_weight` vivían en `analytics/cognitive/market_events.py` (puro, sin deps externas → migrable a `domain`).
- `prefer_summary_excerpt` era un **helper de texto puro** (sin I/O) definido en `market/filing_store.py` → migrable a `domain`.

### P1.6 — mypy no es gate duro

- `.github/workflows/python-ci.yml`: paso `Mypy` con `continue-on-error: true` (~451 errores preexistentes en `domain/market/infrastructure/apps`, deuda tipada).

### ruff gates (7 errores heredados F3b/F5a)

- `I001` en `portfolio.py` (api) + `alembic/env.py`, `001_timescaledb_extension.py`, `account_migration.py`, `migrations.py`, `portfolio_repository.py` (infra).
- `B007` (variable de loop `day` sin uso) en `test_daily_ops_digest_pdf.py` (infra).

## 2. Decisiones de diseño (F4)

- **`MarketEvent` a domain**: nuevo módulo `bolsa_domain/entities/market_event.py` (el contenido de `analytics/cognitive/market_events.py` es stdlib-puro: `dataclasses/datetime/typing/uuid`). Domain ya depende de nada; `market` y `application` importan de domain.
- **`prefer_summary_excerpt` a domain**: nuevo `bolsa_domain/value_objects/excerpt.py` (función pura de texto). `analytics/knowledge/filing_summary.py`, `application/instrument_filings.py` y el test `market/tests/test_filing_store_f2b.py` pasan a importarla de domain. **`market/filing_store.py` deja de exponerla** (no la usaba internamente; era solo re-export).
- **Re-export de compatibilidad en `analytics/cognitive/__init__.py`**: se mantiene la exportación de `MarketEvent*`/`build_market_event`/`event_decay_weight` desde el paquete `bolsa_analytics.cognitive` (ahora importando desde domain) para no romper a los consumidores que lo usaban vía el paquete.
- **Grafo resultante P0.6**: `domain` ← {`analytics`, `market`} y {`domain`, `analytics`, `market`} ← `application`. Sin ciclo `analytics↔market`; sin deps cruzadas no declaradas.
- **P1.6 gate scoped**: añadir paso **bloqueante** `Mypy — gate scoped F4` que corre mypy sólo sobre los 13 ficheros de F4 (nuevos/tocados, mypy-limpios) dentro de los árboles que CI ya gestiona (`domain/market/infrastructure/apps`). El paso global `Mypy` sigue `continue-on-error` hasta la fase correspondiente. `application` queda fuera del gate CI (no está en el target mypy de CI; sus ficheros tocados tienen deuda tipada **preexistente** no relacionada con el cambio de import).

## 3. Implementación (por sub-área)

### P0.6 — romper el ciclo (primer commit atómico)

| Fichero(s)                                                                                                                                                           | Qué                                                                                                                                                                                                                                                        |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `domain/.../entities/market_event.py` (nuevo)                                                                                                                        | `ImpactLevel`, `MarketEvent`, `MarketEventCalendar`, `EventBlackoutContext`, `build_market_event`, `event_decay_weight` + constantes (`EARNINGS_TYPES`, `FED_TYPES`, `ECB_TYPES`, `HIGH_IMPACT_MACRO`, `_parse_ts`) — trasladado verbatim desde analytics. |
| `domain/.../value_objects/excerpt.py` (nuevo)                                                                                                                        | `prefer_summary_excerpt` trasladado desde `market/filing_store.py`.                                                                                                                                                                                        |
| `analytics/cognitive/market_events.py` (eliminado)                                                                                                                   | Contenido movido a domain; sin referencias restantes.                                                                                                                                                                                                      |
| `market/news_snapshot.py`                                                                                                                                            | Importa `MarketEvent*` desde `bolsa_domain.entities.market_event`. **+2 fixes mypy preexistentes** en el fichero (para dejarlo mypy-clean y gateable): guard `raw is None` en `earnings_from_quote_summary` y rename `cached_events` (evita `no-redef`).   |
| `market/filing_store.py`                                                                                                                                             | Se elimina `prefer_summary_excerpt` (no re-export).                                                                                                                                                                                                        |
| `analytics/knowledge/filing_summary.py` / `news_assessment.py` / `cognitive/__init__.py`                                                                             | Importan `MarketEvent*` / `prefer_summary_excerpt` desde domain. `cognitive/__init__.py` mantiene el re-export.                                                                                                                                            |
| `application/.../propose_recommendation.py`, `risk_engine.py`, `execution_router.py`, `trading_policy_guard.py`, `shared_event_calendar.py`, `instrument_filings.py` | `MarketEventCalendar` / `prefer_summary_excerpt` desde domain.                                                                                                                                                                                             |
| `market/tests/test_filing_store_f2b.py`                                                                                                                              | `prefer_summary_excerpt` desde domain.                                                                                                                                                                                                                     |

**Verificación de ciclo:** `market/src` con 0 imports de `bolsa_analytics`; `analytics/src` con 0 imports de `bolsa_market`. Grafo sin ciclo.

### ruff gates (segundo commit atómico)

- `ruff check --fix` sobre los 6 ficheros con `I001` (sólo re-ordenación de imports, sin cambio de comportamiento) + fix manual de `B007` en `test_daily_ops_digest_pdf.py` (`for i in range(29, 36)` quitando la variable `day` sin usar). Resultado: **`ruff check packages/py apps/api-python --config pyproject.toml` → `All checks passed!` (0 errores)** — cierre de los 7 gates heredados de F3b/F5a.

### P1.6 — mypy gate scoped (tercer commit atómico)

- `.github/workflows/python-ci.yml`: se añade el paso **`Mypy — gate scoped F4 (bloqueante)`** (sin `continue-on-error`) sobre los 13 ficheros de F4. El paso `Mypy` global sigue `continue-on-error` (deuda preexistente, por fase).

## 4. Validación de idempotencia / no-regresión

- El contenido de `market_events.py` se movió **verbatim** a domain (mismos tipos/constantes/funciones) → comportamiento idéntico; el re-export en `cognitive/__init__.py` mantiene la superficie pública.
- `prefer_summary_excerpt` se movió verbatim y se cambiaron todos los callers: `analytics/filing_summary.py`, `application/instrument_filings.py`, `market/tests/test_filing_store_f2b.py`.

## 5. Batería (aplicada)

- **P0.6:** `ruff` ✓ (todos los ficheros tocados) · `mypy` ✓ (domain/market/analytics toucheados, incl. 2 fixes preexistentes en news_snapshot) · `pytest` market+analytics **431✓** · application **222✓**.
- **ruff gates:** `ruff check packages/py apps/api-python --config pyproject.toml` → **`All checks passed!` (7 → 0)** · `pytest test_daily_ops_digest_pdf.py` **3✓**.
- **P1.6 gate scoped:** comando mypy exacto del CI sobre los 13 ficheros → **`Success: no issues found in 13 source files`** (exit 0).
- **Batería ampliada:** infra+domain **57✓** · api-python **30✓** (contra `bolsa_v1`) · ai+analytics **337✓ (1 skip)**.

## 6. Deuda / fuera de alcance (registrado, NO resuelto)

- **P1.9 (API thin)** — hilo propio pendiente (decidido por el usuario en el arranque de F3a).
- **P1.6 — resto del árbol** (~451 errores mypy preexistentes en `domain/market/infrastructure/apps`, fuera de los 13 ficheros de F4): se resuelven por fases futuras (el gate scoped de F4 solo cubre lo F4; el paso global sigue `continue-on-error`).
- **`application` → mypy debt preexistente** (13 errores en 4 ficheros tocados: `dict` type-args, `arg-type`, `no-untyped-def`, `unused-ignore`) no relacionados con el cambio de import; `application` no está en el target mypy de CI → fuera del gate scoped.
- **P0.6 `application` → `ai` (dynamic `get_default_proxy`)** — imports lazy, se mantienen.
- **D4 auth** → F5b. **Deuda F5a §6** (fidelidad DTOs campo-a-campo, `openapi-fetch`) → fase posterior.

## 7. Registro

| Fecha      | Acción                                                                                                                                                                                                                                                                     |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-08-12 | Arranque F4: rama `stage/f4-arquitectura-python-2026-08-12` desde `stage/f1-*` (HEAD `0690834`, tras merge PR #33). Alcance pactado con el usuario: P0.6 ciclo (mover MarketEvent + prefer_summary_excerpt a domain), 7 ruff gates, P1.6 mypy gate por fases (files_only). |
| 2026-08-12 | P0.6: `market_event.py` + `excerpt.py` en domain; eliminado `analytics/cognitive/market_events.py`; 8+ callers actualizados; ciclo roto (market & analytics → solo domain). Battery: ruff✓ · mypy✓ · pytest market+analytics 431 + application 222.                        |
| 2026-08-12 | ruff gates: `--fix` I001 en 6 ficheros + fix B007 en test_daily_ops_digest_pdf. `ruff check packages/py apps/api-python` → 0 errores. Battery: pytest infra digest 3✓.                                                                                                     |
| 2026-08-12 | P1.6: paso `Mypy — gate scoped F4 (bloqueante)` en CI sobre 13 ficheros (exit 0). Battery ampliada: infra+domain 57✓· api-python 30✓ (bolsa_v1) · ai+analytics 337✓.                                                                                                       |
| 2026-08-12 | Cierre F4: traspaso + engineering-index + texto exacto siguiente hilo.                                                                                                                                                                                                     |

## 8. Protocolo recurrente (obligatorio en TODOS los hilos)

> Norma permanente del proyecto. Al cerrar: preparar el siguiente con su `traspaso-*`, entrada única en `engineering-index`, y entregar en el chat el **texto exacto** para pegar en el próximo.

## 9. Texto exacto de traspaso — siguiente hilo

```text
Texto de traspaso → nuevo chat (F4 completado — siguiente fase tras F4)

CONTEXTO INMEDIATO: F4 (Arquitectura Python) COMPLETADO. Rápidas en rama
  stage/f4-arquitectura-python-2026-08-12 (desde stage/f1-* tras merge PR #33):
  - P0.6 ciclo analytics↔market ROTO: MarketEvent+MarketEventCalendar+
    EventBlackoutContext+build_market_event+event_decay_weight movidos a
    bolsa_domain/entities/market_event.py; prefer_summary_excerpt a
    bolsa_domain/value_objects/excerpt.py. analytics y market quedan como
    pares que solo dependen de domain (0 imports cruzados src↔src). Re-export
    de compatibilidad mantenido en bolsa_analytics.cognitive. +2 fixes mypy
    preexistentes en market/news_snapshot.py (guard raw None + rename cached_events).
  - 7 ruff gates CERRADOS (I001 en portfolio.py/env.py/001_timescaledb_extension/
    account_migration/migrations/portfolio_repository + B007 en
    test_daily_ops_digest_pdf): ruff check packages/py apps/api-python → 0 errores.
  - P1.6 mypy gate POR FASES (files_only, decisión usuario): add paso CI bloqueante
    "Mypy — gate scoped F4" sobre 13 ficheros F4 (nuevos/tocados, mypy-limpios);
    el paso global sigue continue-on-error (~451 errores preexistentes).

BATERÍA (verde): ruff 0 (todo el scope py) · mypy gate scoped 13 files exit 0 ·
  pytest market+analytics 431✓ + application 222✓ + infra+domain 57✓ +
  api-python 30✓ (bolsa_v1) + ai+analytics 337✓ (1 skip) · test_daily_ops_digest 3✓.

DEUDA REGISTRADA → fases posteriores: P1.9 API thin (hilo propio) · mypy resto del
  árbol ~451 preexistentes (por fases) · application→ai dynamic imports (lazy) ·
  D4 auth → F5b · F5a §6 fidelidad DTOs/openapi-fetch → posterior.

Lee PRIMERO: docs/engineering/traspaso-f4-arquitectura-python-2026-08-12.md (§4-§7) y su
  fuente audit-consolidado-internas-externas-2026-08-11.md (P0.6/P1.6/P1.9 + D0-D5).
  Para la fase siguiente usa engineering-index-2026-08-03.md y el plan de la fase
  declarada. NO toques código fuera del alcance de la fase que se declare.
```
