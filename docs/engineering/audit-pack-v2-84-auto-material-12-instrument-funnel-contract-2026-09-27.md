# Audit-pack — `AUTO-MATERIAL-12` / `V2.84` — INSTRUMENT FUNNEL CONTRACT

> **Objeto a auditar:** tag anotado **`v2.84-beta`** · **Versión:** `2.09.0-beta` · **Base del diff:**
> `v2.83.1-beta` (`2.08.1-beta`) · **AsOf:** 2026-09-27 · **Alembic head:** `046_fill_reference_mid`
> (**SIN migración**).

## 1. Qué es esta fase

Fase de **INSTRUMENTO READ-ONLY** que cierra `OBS-6` (MEDIUM), `OBS-7` (LOW) y `OBS-8` (LOW) de la
auditoría externa de `v2.83.1-beta`. **No** cambia el motor (`auto_simulation_worker.py`), el gobernador
(`aggregate_trial_regime`), `operability_window.py`, `TOP_N`, umbrales, allocation, pesos A/B ni la UI.

## 2. Diff esperado (acotado)

- `package.json` (`2.08.1-beta → 2.09.0-beta`).
- `packages/py/application/src/bolsa_application/operability_audit.py` (instrumento puro).
- `packages/py/application/tests/test_operability_audit.py` (+2 tests).
- `apps/api-python/scripts/v2_83_window_audit.py` (docstring de códigos de salida).
- `apps/api-python/scripts/v2_44_mutation_audit.py` (marcadores + `M231`/`M232`).
- `docs/engineering/*` (plan, audit-pack, arranque del auditor, arranque del agente, relevo, evidencia de
  matriz, `PROJECT_STATE`, índice, deuda P3) + `CHANGELOG.md`.

### 2.1 Anexo operativo (DECLARADO, fuera del instrumento)

Los tres ficheros siguientes **no** son parte del instrumento read-only: son el **anexo de operación de
la ventana PAPER** que se preparó en la misma sesión y viaja en el mismo sello para no dejar material sin
versionar. **No** tocan motor, gobernador, `operability_window.py`, `TOP_N`, umbrales, allocation, pesos
A/B, UI ni migraciones, y **no** forman parte de las tesis falsables de §3.

- `apps/api-python/scripts/ops_seed_window_pair.py` — **script OPS** (lo ejecuta el operador, no el CI)
  que siembra la cuenta fija de la ventana, la versión B **ACTIVE** (`shadow_validated=false`, declarada
  como semilla **no gate-certificada**), su localizador de promoción y los `EdgeReport` de A/B. Escribe
  **sólo** filas propias en `investment_accounts`/`strategy_versions`/`strategy_promotions`/`edge_reports`
  y `operability_runs/window-setup.json` (gitignoreado). Sin `--account-id` crea cuenta ⇒ **no** es
  idempotente por defecto; con cuenta fija sí lo es.
- `docs/engineering/arranque-ventana-paper-operativa-2026-09-27.md` — protocolo de arranque de la ventana.
- `docs/engineering/runbook-ventana-forward-v2.78-2026-09-27.md` — cierra por semilla las **brechas 1 y 2**
  del runbook (deja 3 y 4 vigentes); cambio docs-only.

**Ficheros PROHIBIDOS en el diff** (si aparecen, la fase se sale de alcance): `auto_simulation_worker.py`,
`aggregate_trial_regime`/gobernador, `operability_window.py`, `v2_80_market_window.py`, cualquier
`alembic/` o migración, `apps/web/**`, y cualquier cambio de `TOP_N`/umbrales/allocation/pesos.

## 3. Tesis falsables (lo que el auditor debe intentar **romper**)

1. **`OBS-6` cerrado:** `enrich_rows_with_evidence` **no** sobrescribe un escalón del funnel ya medido, con
   evidencia **distinta** para el mismo día; sí rellena los `None`. (Regresión: `M231`.)
2. **`OBS-7` cerrado:** el funnel agregado de `window_totals` suma **sólo** días `measured != False`; una
   fila `measured=False` con evidencia **no** engorda el `TOTAL`. (Regresión: `M232`.)
3. **`OBS-8` cerrado:** el docstring del CLI describe el comportamiento real de `argparse` (`2` en uso
   incorrecto) y no promete un código `1` inalcanzable.
4. **Sin deriva semántica:** `window_rates` sigue devolviendo `rate=None` (nunca `0.0`) sin días medidos o
   con denominador `0`; `render_window_audit` sigue determinista y con `n/d` en los huecos.
5. **Read-only intacto:** sin `--out`, el CLI no escribe nada; `git status` del árbol no cambia tras una
   corrida de auditoría.
6. **Matriz honesta:** **232/232** fragmentos medidos, restauración **byte a byte**; `M231`/`M232` muerden
   **exactamente** los dos tests nuevos.
7. **Compuertas verdes y reproducibles** (§4).
8. **Sin cierre de deuda por documentación:** `P3-2`/`P3-3`/`H-4` siguen **ABIERTOS** y así se declara.

## 4. Compuertas a reproducir

```powershell
uv run --no-sync pytest packages/py/application/tests/test_operability_audit.py -q          # 18 passed
uv run --no-sync pytest packages/py/application/tests -q                                    # 2089 passed
uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml             # All checks passed!
uv run --no-sync lint-imports --config packages/py/.importlinter                            # 4 kept, 0 broken
uv run --no-sync mypy packages/py/domain/src packages/py/market/src \
    packages/py/infrastructure/src packages/py/application/src apps/api-python/src \
    --follow-imports=silent                                                                 # 0 issues (507 files)
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py                     # medidas: 232/232
```

## 5. Límites declarados (honestidad)

- **CI del tag — patrón `OBS-3`/`OBS-4` (LÉEME):** `Release tag CI` **solo corre al empujar** el tag, así
  que su resultado **no puede** estar dentro del propio tag. Dentro de `v2.84-beta`, el fichero
  `evidencia-ci-tag-v2.84-2026-09-27.txt` es un **PLACEHOLDER pre-tag** y su predicción contiene un
  **error aritmético declarado** (`3040`/`3029` en vez de `3022/37` y `3011/40`). La cita **acreditada**
  vive en los commits **POST-TAG** de `main` **`1f2638aa`** y **`434f058d`**:
  `Release tag CI` **`36353503867`** = **SUCCESS** (`attempt 1`, 8m54s, `headSha` `fd3859e3`), job
  `python` del tag **`3022 passed / 37 skipped`**, job `quality` **`3011 passed / 40 skipped`**,
  `mypy 0 issues (507 files)`, `ruff All checks passed!`, `Contracts: 4 kept, 0 broken`; en `main`
  `Python CI 36353481118` (`quality` `3011/40`), `Frontend CI 36353481072`, `Optimize lab 36353481116`,
  `Fase 2 scientific 36353481110`, `Gitleaks 36353481089`. **Ninguna cifra observada se corrigió**: se
  corrigió la **fórmula** (verificado: `git show v2.84-beta:docs/engineering/evidencia-ci-tag-v2.84-2026-09-27.txt`
  muestra el placeholder; la versión de `main` muestra las cifras reales).
- **Sin material PAPER real**: `operability_runs/` está gitignoreado ⇒ la ventana se re-deriva con
  fixtures deterministas; **no** se certifica `P3-2`/`P3-3`.
- **5 huecos locales preexistentes** de la matriz (`M117`/`M118`/`M170`/`M176`/`M197`): idénticos a la
  evidencia de `v2.81-230`, **no** introducidos por esta fase.
  > **Reconciliación post-tag (auditoría externa de `v2.84-beta`, 2026-09-28 — H-1):** «no muerden en este
  > entorno» es **observacional y dependiente del entorno** y **no reproduce** en un clon fresco (el
  > auditor midió **5/5** mordiendo). Los cinco labels son **PREEXISTENTES**; si muerden o no **depende del
  > entorno** ⇒ no se declara como propiedad del código. Ver
  > [`auditoria-v2-84-…`](./auditoria-v2-84-auto-material-12-instrument-funnel-contract-2026-09-28.md) §3 (H-1).
- **`OBS-9`** (nuevo, doc-only) queda **declarado**, no barrido.
- **`OBS-10`** (nuevo, LOW, de la auditoría de `v2.84-beta`): `stateCounts` del `TOTAL` recorre todas las
  filas mientras `counts`/`coverage`/`rSum`/`funnel` usan `measured_rows`. **Declarado y aplazado** a la
  fase de código `v2.85`/`AUTO-MATERIAL-13` (semántica de cierre ya decidida: `measured_rows`); **no** se
  corrige en la entrega docs-only porque **no debe tocarse `packages` con la ventana PAPER en curso**. Ver
  [deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md) y el
  [protocolo de comportamiento](./protocolo-auditoria-comportamiento-auto-2026-09-28.md).
- **Anexo operativo (§2.1) declarado, no certificado:** la semilla del par A/B (`ops_seed_window_pair.py`)
  **no** está gate-certificada (`shadow_validated=false`) ⇒ `pairActive=true` significa «par sembrado», no
  «promoción certificada»; **no** cierra `P3-3`. Y `PAPER_D_ACCOUNT_ID`/`BROKER_VENUE` viven en el `.env`
  **local** (no versionado): sin ellos, ese script queda **bloqueado** (`exit 2`).
- **Placeholder pre-tag con error aritmético declarado:** la copia de `evidencia-ci-tag-v2.84-2026-09-27.txt`
  **dentro** del tag predice `3040`/`3029` por un fallo de fórmula (`+18` sobre una base que ya incluía los
  2 tests nuevos). Lo correcto es **`3022/37`** y **`3011/40`**, que es lo que midió el CI del tag. Ninguna
  cifra observada se corrigió; se corrigió la fórmula (ver §5 del
  [relevo](./traspaso-relevo-post-v2-84-auto-material-12-instrument-funnel-contract-2026-09-27.md)).

Referencias: [plan](./plan-v2-84-auto-material-12-instrument-funnel-contract-2026-09-27.md) ·
[arranque del auditor](./arranque-auditor-v2-84-auto-material-12-instrument-funnel-contract-2026-09-27.md) ·
[deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md) ·
[auditoría que originó la fase](./auditoria-v2-83-1-auto-material-11-reseal-2026-09-27.md).
