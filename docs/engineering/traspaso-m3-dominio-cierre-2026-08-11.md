# CIERRE M3 — Capa de dominio (`py/domain` + `application`)

> **Fecha:** 2026-08-11 · **Rama:** `stage/estudio-membership-operativa-2026-08-04`
> **HEAD:** `2c41b41` (árbol limpio y sincronizado con `origin`)
> **Estado del hilo: CERRADO** (objetivos de coherencia de negocio, docstrings y código muerto de M3 ejecutados).
> **Entrada original:** `traspaso-m3-dominio-2026-08-10.md` (protocolo sagrado + frentes a resolver).

---

## 1. Qué se ejecutó (4 lotes atómicos, cada uno con batería verde + push)

| Lote | Commit | Alcance | Resultado |
|------|--------|---------|-----------|
| A | `ce0cdab` | **Fix coherencia ADR-024:** 2 tests rotos en `test_list_unsubscribe_index.py` (mocks no preparaban `ensure_estudio_list` añadido en `ListInstrumentLists.execute`) | +4 ins · application 222 passed |
| B | `f13b09d` | **Código muerto:** retirados 5 `Protocol` de repositorio enteramente huérfanos en `bolsa_domain/repositories/` (`Portfolio`, `Hypothesis`, `HypothesisBelief`, `ResearchEvidence`, `KnowledgeNode`) — sin ningún consumidor en packages/py ni api (la infra usa `SqlAlchemy*` concretos) | −184 líneas · 231 passed |
| C | `03472dc` | **Docstrings:** añadidos docstrings de módulo a los **33** módulos de `bolsa_domain` que carecían de uno (solo texto, sin lógica) | 33 files, +33 ins |
| D | `2c41b41` | **Coherencia de negocio (constantes):** centralizados `MIN_SCAN_BARS` y `ALLOWED_STAGES`/`KnowledgeStage` desde `bolsa_domain` | 4 files, +11/−10 · 222 passed |

### Detalle del Lote D (coherencia de constantes)
- `backtests.py:154` y `optimize.py:576`: el umbral literal `50` de barras mínimas se sustituyó por `MIN_SCAN_BARS` (dominio `platform_kernel.py`).
- `signal_alerts.py:13`: `MIN_SCAN_BARS` ahora se importa de `bolsa_domain.platform_kernel` (antes vía re-export de `bolsa_application.scans`, que además causaba un error de tipado `attr-defined` en mypy). **El refactor eliminó ese error.**
- `knowledge_consolidation.py`: `ALLOWED_STAGES = frozenset(get_args(KnowledgeStage))` — una única fuente de verdad en dominio (antes duplicaba los 5 literales).

---

## 2. Batería de referencia (estado base, verificada antes de tocar nada)

| Comando | Estado base | Estado final |
|---------|-------------|--------------|
| `ruff packages/py/domain packages/py/application` | ✅ 0 errores | ✅ 0 errores |
| `ruff packages/py apps/api-python` (global) | 1× `B007` en `infrastructure/tests/test_daily_ops_digest_pdf.py:54` (**M4, fuera de M3**) | igual (sin tocar) |
| `mypy domain+application` | 115 errores pre-existentes en 39 files (deuda, `continue-on-error` CI) | sin empeorar + **un error menos** (el de `MIN_SCAN_BARS`/scans) |
| `pytest` alcance CI (market/analytics/api-python) | **434 passed** | sin cambios (M3 no toca esos) |
| `pytest domain+application` | 229 passed + **2 FAILED** (ADR-024) | **222 passed** (tras fix Lote A) |

---

## 3. Hallazgos M3 registrados (no alterados por riesgo / fuera de alcance atómico)

Coherencia de negocio evaluada en FASE 1 y **no modificada** por preservación funcional absoluta:

1. **`EXECUTION_MODES` (dominio) vs `ALARM_SAFE_MODES`/literal `"inform_only"`** (`tracker_alarms.py:21`, `execution_router.py:69`): son **subconjuntos intencionados** de negocio (modos seguros de alarma), no contradicción. No se alteran (riesgo medio en lógica de ejecución, sin bug real).
2. **Timeframes `"1d"`/`"1wk"`: decenas de literales** en application vs `TimeFrame.D1/W1` del dominio. Refactor masivo (~40 puntos, muchos módulos). Se deja como **deuda M3 remanente documentada**, no atómico/suficiente riesgo para este hilo.
3. **`get_instrument_composite.py:61`** usa el umbral `50` sobre `indicator_bars` (barras de indicador derivadas) — semánticamente distinto de `MIN_SCAN_BARS` (barras OHLCV crudas). **No se toca.**
4. **Deuda mypy** (115 errores en domain+application): fuera de alcance M3 salvo decisión explícita (se marco como frente aparte, igual que el `B007` de ruff en `infrastructure`).

---

## 4. Docs de registro

1. **`docs/engineering/traspaso-m3-dominio-cierre-2026-08-11.md`** (este documento) — ancla de cierre.
2. **`docs/engineering/traspaso-m3-dominio-2026-08-10.md`** — entrada original (sin modificar; este cierre es su resultado).
3. **`docs/engineering/dev-continuation-plan-2026-08-09.md`** — sección 7.x nueva de cierre M3.
4. **`docs/engineering/engineering-index-2026-08-03.md`** — entrada M3 actualizada a CIERRE real con commits.

---

## 5. Siguiente módulo del plan 08-10

Con M3 **CERRADO**, el orden del plan 08-10 avanza: M0→M1→M2→**M3 (hecho)**→M4 (infraestructura/modelo datos, CERRADO 08-10 según índice, revisar)→M6 (ai/analytics, CERRADO 08-10)→M5 (frontend, pausa). Fronts pendientes conocidos: la **deuda mypy**, el **`B007` de ruff** (mini-cierre M0, `test_daily_ops_digest_pdf.py:54`), y la **centralización de timeframes** (deuda M3 remanente).
