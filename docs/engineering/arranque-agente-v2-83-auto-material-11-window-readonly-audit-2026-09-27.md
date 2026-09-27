# Arranque del agente — `v2.83` / `AUTO-MATERIAL-11`: AUDITORÍA READ-ONLY de la ventana PAPER

> **Para:** el agente que retome tras el sello `v2.83-beta`. **AsOf:** 2026-09-27.
> **Estado:** fase **CERRADA** (`2.08.0-beta`, tag `v2.83-beta`), a la espera de la **auditoría externa**.

## 1. Qué es esta fase (y qué NO)

- **Es** el **instrumento de lectura** de la ventana: un módulo **puro** (`operability_audit.py`) y un
  **CLI read-only** (`v2_83_window_audit.py`) que **agregan** un `operability_runs/` ya producido y
  publican la **fila `TOTAL`** acumulada y las **tasas de operabilidad** (`topNExclusionRate`,
  `riskRejectionRate`, `reservationFailureRate`, `fillRate`, `cycleRate`, `unresolvedRate`).
- **NO** cambia el motor, el gobernador (`aggregate_trial_regime`), `TOP_N`, los umbrales, la allocation,
  los pesos de estrategia ni la lógica A/B. **NO** añade migración (`046_fill_reference_mid` sigue).
- **NO** fabrica medición: `n/d` (`None`) ≠ `0`; sin ventana, el veredicto sigue siendo `INCONCLUSIVE`.
- **NO** cierra `H-4` ni `P3-2`/`P3-3` ni `P3-5`/`OBS-5`: eso exige datos de mercado, no documentación.

## 2. Qué comprobar primero (5 min)

1. `git diff v2.82-beta..v2.83-beta --stat` → los 3 ficheros nuevos + 1 línea por workflow + `package.json`
   + docs.
2. `uv run --no-sync pytest packages/py/application/tests/test_operability_audit.py -q` → **16 passed**;
   `uv run --no-sync pytest packages/py/application/tests -q` → **2087 passed**.
3. `uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml` y
   `uv run --no-sync lint-imports --config packages/py/.importlinter` → `4 kept, 0 broken`.
4. `uv run --no-sync mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent` → `0 issues` (**507** fuentes).
5. `uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py` → **230/230**.

## 3. La siguiente fase (candidata): OPERAR y AUDITAR, no construir

El siguiente hito **ya no es arquitectura**: es **mercado real**. El instrumento de lectura está listo;
falta la ventana. Cadencia (runbook):
[`runbook-ventana-forward-v2.78-2026-09-27.md`](./runbook-ventana-forward-v2.78-2026-09-27.md).

```powershell
$env:BROKER_VENUE="paper"
# 1) preflight (read-only; exit 2 = LONG vetadas hoy)
uv run --no-sync python apps/api-python/scripts/v2_76_forward_market_material.py --preflight-only --watch-size 20
# 2) forward del dia y 3) journal (ver runbook)
# 4) ventana: serie + funnel + HTML (read-only)
uv run --no-sync python apps/api-python/scripts/v2_80_market_window.py `
    --account-id "$ACCOUNT" --strategy-version "$VERSION_A" --days 4 --render `
    --forward 'operability_runs/forward-market-*.json' `
    --out operability_runs/operability-window.json `
    --html operability_runs/operability-window.html
# 5) AUDITORIA: TOTAL + tasas + avisos (read-only; el instrumento de esta fase)
uv run --no-sync python apps/api-python/scripts/v2_83_window_audit.py `
    --window operability_runs/operability-window.json `
    --forward 'operability_runs/forward-market-*.json' --render `
    --out operability_runs/operability-audit.json
```

Sólo con **≥4 días distintos**, **≥2 episodios** y **≥32 ciclos medibles** el gate pasará a `READY` y
`P3-2`/`P3-3` podrán cerrarse (`AUTO-22`/`AUTO-23`). Entonces las **tasas** dirán si el cuello de botella
es de MERCADO, de GOBERNADOR, de `TOP_N` o de RIESGO — **sin** haber tocado `TOP_N` por intuición.

## 4. Brechas operativas declaradas (ABIERTAS antes de D1)

- **Régimen (preflight 2026-09-27):** **exit 2** · `{range:8, trend_down:9, trend_up:3}` ⇒ `BEAR_TREND` ⇒
  **LONG VETADAS**. No se fuerza el régimen ni se elige un watch «que pase».
- **Par A/B (`pairActive=true`) y cuenta fija:** **NO VERIFICABLES** hoy — `PAPER_D_ACCOUNT_ID` está
  **comentado** en `.env`. Requiere estrategia B **ACTIVE** con `EdgeReport` y una cuenta fija desde D2.
- **Glob `operability_runs/forward-market-*.json`:** debe **excluir** los fixtures (aún no hay bundle real).
- **Barras:** **20/20** servidas ⇒ el scheduler de barras responde hoy.

## 5. Reglas duras

Freeze del worker y del gobernador intactos; `TOP_N` y umbrales intactos; sin migración
(`046_fill_reference_mid`); reparto `auto18-v1`/`auto15-v1`; **forward, no replay**; el capturador y el
auditor son **read-only**; veredicto honesto `INCONCLUSIVE`/`NO MEDIDO` si la ventana está degenerada;
**no** se cierra deuda por documentación: primero datos, después evidencia.
