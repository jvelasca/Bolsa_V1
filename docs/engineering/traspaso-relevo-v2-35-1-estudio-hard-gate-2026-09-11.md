# RELEVO — v2.35.1 · ESTUDIO hard gate (P1-01) — 2026-09-11

> **Para el agente entrante (con sus subagentes).** Este documento es autocontenido: asume
> **cero contexto previo** más allá de lo que aquí se dice. Léelo entero antes de tocar nada.
> Respeta el estilo del repo: español, fail-closed, sin LLM en hot path, LIVE congelado.
>
> **AsOf:** 2026-09-11 · **Base:** `main` · padre `f47e0ceb` (sello A15) → `4fdf108d` (sello A14)
> → `e6fbab83` (fase A14) → `61e613b1` (hardening H1+H2) → `5fcd0224` (cierre A13).
> **Alembic head:** `035_paper_forward_evidence` (SIN migración nueva en v2.35.1).
> **Veredicto:** P1-01 **CERRADO** (hard gate ESTUDIO + tests obligatorios). Pendiente de
> commit de fase, bump `1.60.1-beta`, y —si el owner lo decide— tag `v2.35.1-beta`.

---

## 0. Estado en una frase

El AUTO deja de poder **abandonar ESTUDIO**: sin universo canónico `ok` y no vacío **no se
opera**, y la allowlist CSV pasa a ser **solo intersección**. Se cierra el único hallazgo P1 de
la auditoría externa de v2.35-beta, sin tocar ninguna otra fase ni añadir migración.

---

## 1. El hallazgo (auditoría externa de v2.35-beta, P1-01)

`_instruments_for_cycle()` convertía la allowlist `AUTO_ORCHESTRATOR_INSTRUMENTS` en el
**universo efectivo** en cinco situaciones:

| Camino | Condición                                            | Comportamiento anterior |
| ------ | ---------------------------------------------------- | ----------------------- |
| 1      | orquestador sin `resolve_universe`                   | `return allowlist`      |
| 2      | el resolver lanza excepción                          | `return allowlist`      |
| 3      | `resolution is None`                                 | `return allowlist`      |
| 4      | `status != "ok"` (`unavailable`/`empty`/desconocido) | `return allowlist`      |
| 5      | `instrument_ids` vacío                               | `return allowlist`      |

Riesgo: con `ESTUDIO = unavailable` y `AUTO_ORCHESTRATOR_INSTRUMENTS=XYZ`, el AUTO operaba
`XYZ` aunque no estuviera en ESTUDIO ⇒ rompía la propiedad "AUTO solo opera el universo
supervisado/canónico". No afectaba a dinero real (AUTO es SIM), pero sí a la corrección del
motor autónomo. Además, el docstring decía "`empty`/`unavailable` nunca inventa candidatas"
mientras el código devolvía la allowlist (falsa sensación de seguridad).

---

## 2. El cambio (V2.35.1)

Contrato nuevo, literal: **ESTUDIO es obligatorio para AUTO; la allowlist solo intersecta;
nunca lo sustituye.**

- Los **cinco** caminos devuelven ahora `()`. El bucle no muere: registra el motivo y
  **reintenta** el ciclo siguiente (fail-closed, no fail-stop).
- Se conserva la intersección cuando ESTUDIO es `ok` y hay allowlist:
  `ESTUDIO ∩ allowlist`.
- **Sin vía de escape hermética**: el gate es estricto también cuando el orquestador no expone
  `resolve_universe`. Los dobles de test se migraron a un universo ESTUDIO real.

### Archivos tocados

- `apps/api-python/src/bolsa_api/background/auto_orchestrator_worker.py`
  - `_instruments_for_cycle`: cinco `return allowlist` → `return ()`, docstring reescrito.
  - Docstring de módulo (`AUTO_ORCHESTRATOR_INSTRUMENTS` = intersección).
  - `logger.warning` del bucle: refleja el nuevo contrato.
- `apps/api-python/tests/test_auto_orchestrator_worker.py`
  - Nuevos: `test_unavailable_estudio_never_falls_back_to_allowlist`,
    `test_estudio_empty_never_falls_back_to_allowlist`,
    `test_estudio_error_never_falls_back_to_allowlist`,
    `test_loop_does_not_operate_when_estudio_unavailable_with_allowlist`.
  - Retirado: `test_unavailable_universe_falls_back_to_allowlist` (certificaba el bug).
  - Migrados a `_OrchWithUniverse`: `test_loop_runs_cycle_and_watch`,
    `test_loop_survives_per_instrument_failure`, `test_loop_does_not_pass_shadow_override`,
    `test_loop_logs_cycle_summary`, `test_loop_runs_forward_between_cycle_and_watch`.
  - `_OrchWithUniverse` gana `watches` y `fail_on`.
- `packages/py/application/src/bolsa_application/orchestrator_universe.py` (comentario).
- `CHANGELOG.md` (`1.60.1-beta`), `docs/engineering/PROJECT_STATE.md`,
  `docs/engineering/engineering-index-2026-08-03.md` (entrada 106).

---

## 3. Invariantes intactas

- `AUTO ⇒ SIMULATED`; LIVE bloqueado por `LIVE_EXECUTION_AUTHORIZED` + `LIVE_EXECUTION_UNLOCKED`.
- Fail-closed (ausencia de evidencia ≠ aprobación). H1 (`require_holdout=True`), H2
  (fingerprint de dataset) sin cambios.
- Sin LLM en hot path. Long-only. Gates CPCV/PBO/DSR/WFE/OOS + coach sin cambios.
- Sin migración: Alembic head sigue en `035_paper_forward_evidence`.
- La gramática A14 sigue tras `AUTO_ORCHESTRATOR_GRAMMAR` (OFF por defecto).

---

## 4. Verificación

```bash
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src \
           packages/py/infrastructure/src packages/py/application/src \
           apps/api-python/src --follow-imports=silent
uv run pytest apps/api-python/tests/test_auto_orchestrator_worker.py -q
# offline: comando del job `quality` de python-ci.yml (con sus --ignore)
# PG: jobs lifecycle-pg / paper-forward-pg / grammar-discovery-pg con *_PG_REQUIRED=1
```

---

## 5. Deuda P2 (RESUELTA en la misma v2.35.1)

Los tres hallazgos P2 de la auditoría v2.35-beta se cerraron en la misma versión, cada uno
en su rama aislada y luego integrados (commits `7eba50a8` P2-02, `884430c3` P2-03,
`4299a650` P2-01, `645c9215` integración):

- **P2-01** — Promotion Gate automática (`decide_promotion`/`evaluate_promotion`, sin
  override) separada de la admin/manual (`decide_admin_promotion`/`evaluate_admin_promotion`,
  única con `shadow_validated`). Eliminado `OrchestratorDeps.shadow_override` y el parámetro
  `shadow_validated` de `run_cycle`. H1 intacto.
- **P2-02** — `CycleGrammarCounters` (por ciclo, reiniciado cada iteración) separado de
  `GrammarObservabilityCounters` (proceso). `cycle_summary` reporta el ciclo; nuevo
  `process_summary` conserva los acumulados.
- **P2-03** — `DiscoveryBudgetAllocator` explícito por carriles (catálogo / gramática simple /
  compuesta / adaptive placeholder) con reparto determinista por resto mayor, sustituye el
  sesgo de orden de `_grammar_reserve`. Gramática OFF byte-idéntica a A13.
- **Integración (hallazgo nuevo)**: al dar cupo real a la gramática se destapó que
  `RunSmaGridOptimizeAndSave.execute` no reenviaba `grammar_variants` (gap de A14); corregido
  en `optimization_runs.py`. Tests A14 PG admiten `sin_evidencia_top3` como corte honesto.

---

## 6. Siguiente paso sugerido (v2.36)

Strategy Intelligence **adaptativa**: cerrar el bucle
`evidence → aprender → ajustar probabilidades de búsqueda → siguiente Discovery`, en vez de
enumerar más combinaciones. Empezar por **PLAN**, no por código.

---

## 7. Freeze (copiar en cualquier sesión)

`AUTO ⇒ SIMULATED` · LIVE bloqueado (`LIVE_EXECUTION_AUTHORIZED` + `LIVE_EXECUTION_UNLOCKED`
false) · `PAPER_D_EXECUTE` off · sin LLM en hot path · fail-closed · migraciones aditivas sin
backfill · long-only · Alembic head `035_paper_forward_evidence` · gramática A14 tras
`AUTO_ORCHESTRATOR_GRAMMAR` (OFF por defecto) · **ESTUDIO obligatorio para AUTO** (v2.35.1):
sin universo `ok` no se opera y la allowlist solo intersecta.
