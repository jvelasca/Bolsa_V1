# Arranque del auditor — `v2.83-beta` / `AUTO-MATERIAL-11`: AUDITORÍA READ-ONLY de la ventana PAPER

> **Objeto:** tag anotado `v2.83-beta` (`2.08.0-beta`) · **Base:** `v2.82-beta` (`2.07.0-beta`) ·
> **AsOf:** 2026-09-27 · **Alembic head:** `046_fill_reference_mid` (**SIN migración**).

## 0. Antes de empezar: qué clase de objeto es

`v2.83` **sí** entrega código, pero es **READ-ONLY**: un módulo **puro** (`operability_audit.py`) y un
**CLI** (`v2_83_window_audit.py`) que **agregan** un `operability_runs/` ya producido y publican la fila
`TOTAL` y las **tasas** que el instrumento de `v2.81` no tenía. El auditor **no** debe buscar un cambio
de motor: debe verificar que **no lo hay**, que el instrumento **no fabrica medición** (`n/d` ≠ `0`) y que
el CLI **no escribe** nada.

## 1. Puntos de entrada (por este orden)

1. **Identidad.** `package.json` = `2.08.0-beta`; tag **anotado** al commit del sello;
   `git status --porcelain` vacío antes/después de cualquier sonda.
2. **Diff acotado.** `git diff v2.82-beta..v2.83-beta --stat` = los dos ficheros nuevos del instrumento,
   el test nuevo, **una línea** de registro en cada workflow, `package.json`, `CHANGELOG.md` y
   `docs/engineering/*`. **Ningún** fichero de motor, gobernador, `TOP_N`, umbrales o migración.
3. **Compuertas medidas.** `ruff` limpio · `lint-imports` `4 kept, 0 broken` · `mypy` `0 issues`
   (**507** fuentes, `506 → 507`) · `alembic heads` = `046_fill_reference_mid`.
   Tests: `test_operability_audit.py` **16 passed** · `packages/py/application/tests` **2087 passed**
   (`2071 + 16`) · los tres ficheros del instrumento juntos **97 passed**.
4. **Semántica del instrumento nuevo** (el núcleo a intentar romper):
   - `window_totals`: suma **sólo** días medidos, publica `coverage[*].partial`, **no** suma huecos como
     `0`; la clave `measured` ausente se lee como **medida** (misma convención que `operability_state`).
   - `window_rates`: `rate=None` sin días medidos o con denominador `0` (**nunca** `0.0`); cada tasa lleva
     `numerator`/`denominator`/`coveredDays`/`source`.
   - `render_window_audit`: determinista (sin reloj), `n/d` para `None`.
   - `enrich_rows_with_evidence`: rellena **sólo** huecos declarados y **no** sobrescribe lo medido;
     reconstruye el funnel con la **misma** función del instrumento (`build_operability_funnel`).
5. **Read-only de verdad.** Ejecuta el CLI: `--render`/`--json` sin `--out` **no** crea ficheros; con
   `--out` escribe **sólo** el JSON pedido; **nunca** toca el journal durable, `evidence_runs/` ni
   `evidence_validations/`. `exit 0` con ≥1 día; `exit 2` sin material legible.
6. **Freeze / reparto / migración.** El diff no toca `auto_simulation_worker.py`,
   `portfolio_decision_engine.py`, `opportunity_ranker.py`, `market_regime_gate.py`,
   `paper_material_readiness.py` ni `auto_reason_codes.py`; `TOP_N=5`; `32/3/8/4/2`;
   `auto15-v1`/`auto18-v1`; `ALLOCATION = none`; head `046_fill_reference_mid`.
7. **Sin mutaciones nuevas.** Matriz **230/230**; `M226`–`M230` siguen mordiendo y restaurando **byte a
   byte** si se re-ejecuta.
8. **CI del tag** `v2.83-beta` verde en la primera pasada.

## 2. Qué NO se puede reproducir sin material real

La **ventana ≥4 días** (`P3-2`/`P3-3`) **no** se certifica con fixtures: `operability_runs/` está
gitignoreado y la tabla/`TOTAL`/tasas se re-derivan con fixtures deterministas. El auditor debe **declarar**
esa limitación, no leerla como cierre. **`H-4` (LOW)** sigue **ABIERTO** (esta fase lo hace **visible** en
`warnings: reason_contract`, no lo cierra).

## 3. Verificación pre-D1 (declarada, no forzada)

- Preflight 2026-09-27: **exit 2** · `{range:8, trend_down:9, trend_up:3}` ⇒ `BEAR_TREND` ⇒ **LONG VETADAS**
  (`regime_invalid`).
- Barras del loader: **20/20** ⇒ el scheduler responde hoy.
- Par A/B y cuenta fija: **NO VERIFICABLES** (`PAPER_D_ACCOUNT_ID` está **comentado** en `.env`) ⇒ brechas
  **ABIERTAS**; **no** se declaran resueltas por documentación.

## 4. Cita del CI del tag (ACREDITADO)

El workflow `Release tag CI` sólo corre al **empujar** el tag: la cita de su resultado vive en
`evidencia-ci-tag-v2.83-2026-09-27.txt` (commit POST-TAG `80b18061` en `main`). Dentro del tag, el auditor
lo reproduce con los comandos de §1.

**Cita concreta (`v2.83-beta`):**

- **tag anotado** `v2.83-beta` (objeto `8cfe7f6f`) → commit del sello `0ebf6630`.
- **`Release tag CI`** run [`36329460515`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36329460515) ·
  HEAD `0ebf6630` · `event=push` · branch `v2.83-beta` · **conclusion `SUCCESS`** · `attempt 1` ·
  15:24:56Z → 15:34:11Z · **10 jobs `success` + `certify` `success`** (`playwright (integrated E2E, opt-in)`
  `skipped` por diseño).
- Job `python` del tag: `3020 passed / 37 skipped` (= `3004 + 16`), `ruff All checks passed`,
  `Contracts: 4 kept, 0 broken`, `mypy 0 issues (507 files)`.
- **Sobre el mismo commit y tag:** `Python CI` `36329460471` con `quality` `3009 passed / 40 skipped`
  (= `2993 + 16`) y los cuatro jobs PG (A12/A13/A14/`auto-v2-durable-pg`) en `success`.
- **Cadena verificada:** tag `v2.83-beta` → `Release tag CI` `36329460515` → **SUCCESS**.

**Nota de patrón (falso positivo a evitar).** La instancia de
`evidencia-ci-tag-v2.83-2026-09-27.txt` **dentro del tag** es el **placeholder pre-tag**
("PENDIENTE DE TAG"), porque la cita del CI **no puede** existir antes de empujar el tag (patrón
OBS-3/OBS-4, `v2.74`–`v2.82`). La cita **acreditada** es el commit **POST-TAG** `80b18061` en `main`: un
auditor que trabaje **estrictamente** sobre el objeto sellado leerá el placeholder y **no** debe concluir
"CI no acreditado" — debe citar `80b18061` (ver `evidencia-ci-tag-v2.83-2026-09-27.txt` en `main`).
