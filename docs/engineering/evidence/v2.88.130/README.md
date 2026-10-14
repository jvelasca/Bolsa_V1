# Evidencia `v2.88.130-beta` — `v2.88.130` subsume a `v2.88.129` (tag CI rojo por `scrollable-region-focusable` en `/backtests`) + barrido `axe` INTEGRADO opt-in

> **Bump:** `2.11.129-beta` → **`2.11.130-beta`** (`package.json` + `meta.bump` del CLI OOS `v2_87`, de los 9 CLIs `v2_89`…`v2_97` y del certificador `v2_98`; guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) verde).
>
> **Naturaleza:** incremento **solo de `apps/web/**` + workflow opt-in + docs** (a11y del contenedor de resultados de backtests + spec E2E `axe` integrado opt-in + documentación) — **`Δ motor = 0`**, **`Δ decisión = 0`**, **`Δ contrato HTTP = 0`** · **SIN migración** (head `053_dia_d_cycle_verifications`). Cambio solo de `apps/web/**` + `.github/workflows/release-tag-ci.yml` + docs. Tag **unsigned**.
>
> **Base:** `v2.88.129-beta`.

---

## 1. Supersesión de `v2.88.129-beta` (su `Release tag CI` falló)

El sello `v2.88.129-beta` **se publicó** (tag anotado, objeto `b30e6bb0` → commit `51b368bf`) pero su `Release tag CI` [run **`38574943655`**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38574943655) **FALLÓ**: el job **`playwright (mock E2E)`** quedó **rojo** con el test literal

```
[/backtests @móvil 390×844] · scrollable-region-focusable [serious] ×1 — Scrollable region must have keyboard access
```

sobre el nodo `.p-3.overflow-auto.pt-0`. El resto de jobs del run quedaron **verde** (incl. `playwright (integrated AUTO S5)`), y `certify` falló **por agregar el job rojo**. Este sello **`v2.88.130`** lo **subsume**: corrige la causa y deja el árbol con CI verde.

- **Causa.** El `CardContent` de resultados de backtests aplica `overflow-auto pt-0` cuando **no** está en foco de análisis ⇒ es una **región scrolleable sin acceso por teclado** (`scrollable-region-focusable`), que axe marca como `serious` a **390×844** (móvil).
- **Fix.** [`backtests-page-run-tab.tsx`](../../../../apps/web/src/features/backtests/backtests-page-run-tab.tsx): ese `CardContent` gana `role="region"` + `aria-label="Resultados del backtest"` + `tabIndex={0}` **solo cuando es la rama scrolleable** (const `resultsRegionScrollable`, es decir **fuera** del foco de análisis; en foco de análisis es `overflow-hidden` y **no** aplica). Mismo criterio que los `div.overflow-x-auto` de las tablas fiscales corregidos en `v2.88.129`.
- **Falsabilidad demostrada.** Con viewport **390×380** el fallo **se reproduce sin el fix**; con el fix **pasa**.

---

## 2. Barrido `axe` INTEGRADO opt-in NUEVO (deuda «`axe` solo con mocks», mitigada en parte)

Nuevo spec [`gp-e2e-ui5-0-axe-integrated.spec.ts`](../../../../apps/web/e2e/gp-e2e-ui5-0-axe-integrated.spec.ts): hermano **INTEGRADO** del barrido mock. Barre **5 rutas L1 deterministas** contra el **stack real** (FastAPI + PostgreSQL, **sin** mocks de `/api/*`), con `E2E_INTEGRATION=1`:

- `/operational-console`, `/decision-journal`, `/mesa`, `/trading`, `/auto-monitor?mode=current`.

Cada ruta exige: **0 violaciones `critical`/`serious`** (WCAG 2.0/2.1 A+AA), `heading-order` **sin saltos**, y **exactamente un `main` + un `h1`**.

Se **cablea al job opt-in** `playwright (integrated)` de [`release-tag-ci.yml`](../../../../.github/workflows/release-tag-ci.yml) — **NO** al gate duro del tag. Con esto se **mitiga** la deuda declarada «la certificación `axe` es **con mocks**» **sin** volverla gate duro.

---

## 3. Herencia: `heading-order` sigue CERRADO (de `v2.88.129`)

Este sello **subsume** el cierre de `heading-order` de `v2.88.129` (`CardTitle` con `level` opcional + **gate unitario durable** [`heading-order.test.tsx`](../../../../apps/web/src/test/heading-order.test.tsx) + barrido **mock** ampliado a las 8 rutas heredadas) y lo acompaña del **CI verde** de `v2.88.130`.

---

## 4. Verificación (local)

| Comprobación | Resultado |
|--------------|-----------|
| Spec axe **mock** COMPLETO (`gp-e2e-ui5-0-axe-touched-routes-mock.spec.ts`, 14 rutas L1 × desktop+móvil + command palette) | **29 passed** (`heading-order` **0**) |
| Spec axe **integrado** ([`gp-e2e-ui5-0-axe-integrated.spec.ts`](../../../../apps/web/e2e/gp-e2e-ui5-0-axe-integrated.spec.ts), stack real local) | **5 passed** (desktop 1366×768) |
| Gate unitario ([`heading-order.test.tsx`](../../../../apps/web/src/test/heading-order.test.tsx)) | **10 passed** |
| `pnpm --filter @bolsa/web test` | **299 ficheros / 2194 passed** |
| `pnpm --filter @bolsa/web typecheck` | **OK** |
| `pnpm --filter @bolsa/web lint` | **0 errors / 23 warnings** (preexistentes) |
| Guardián de bump (`uv run --no-sync python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q`) | **1 passed** (`2.11.130-beta`) |
| `Δ motor` / `Δ decisión` / `Δ contrato HTTP` | **0 / 0 / 0** |
| `alembic heads` | `053_dia_d_cycle_verifications` (**sin migración**) |
| Diff | Solo `apps/web/**` + `.github/workflows/release-tag-ci.yml` + docs |

---

## 5. Límites declarados (sin fabricar) + falsabilidad

- **El barrido `axe` integrado es `desktop-only`:** mide a **1366×768**, **no** cubre **móvil** (el fallo que tumbó a `129` apareció a **390×844**).
- **Subconjunto acotado y opt-in:** **5 rutas L1** (no todas) y **skip-by-default** (`E2E_RUN=1 E2E_INTEGRATION=1 E2E_ALLOW_DEV_DB=1`); **no** es gate duro del tag. El resto de la certificación `axe` sigue **mock-only**.
- **Deuda «`axe` solo con mocks»: MITIGADA EN PARTE, NO cerrada.** Queda abierta como «no es gate duro / no cubre móvil ni todas las rutas».
- **Cambio solo de `apps/web/**`:** a11y del contenedor de resultados + spec integrado; sin tocar motor, decisión, contrato HTTP ni migración.

**Falsabilidad.**

- Si el `CardContent` de resultados de backtests perdiera el `role`/`aria-label`/`tabIndex` en su rama scrolleable, el sondeo axe a **390×380** (o el barrido mock a móvil) volvería a marcar `scrollable-region-focusable`.
- Si una de las 5 rutas L1 integradas presentara una violación `critical`/`serious` (o un salto `heading-order`), [`gp-e2e-ui5-0-axe-integrated.spec.ts`](../../../../apps/web/e2e/gp-e2e-ui5-0-axe-integrated.spec.ts) **rompe**.

---

## 6. `Release tag CI` del sello — **VERDE**

**Tag** `v2.88.130-beta` (anotado, unsigned) ⇒ objeto `1a91470c` ⇒ commit `f28bfb98b7d8d7d065b878cd93c6321f3b775947`. **Base:** `v2.88.129-beta`.

**`Release tag CI`:** [run **`38578003227`**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38578003227) — **`SUCCESS`** en **~14 min** (`2026-10-14T14:09:26Z` → `14:23:48Z`), **todos los jobs verdes**:

| Job | Conclusión |
| --- | --- |
| `playwright (mock E2E)` | success |
| `playwright (integrated AUTO S5)` | success |
| `shared (build/typecheck/test)` | success |
| `frontend (typecheck/lint/test/build + contract:check)` | success |
| `python (ruff/imports/mypy/pytest offline)` | success |
| `lifecycle-pg (Alembic + auth + golden restart)` | success |
| `dr-verify (battery DB_DR / TCP CI)` | success |
| `replay-repro (regenera el artefacto del sello desde el fixture)` | success |
| `a7-gate (A7 C3 chaos live_a7 · dedicated real-PG)` | success |
| `decision-spine` | success |
| `security (gitleaks)` | success |
| `certify (aggregate + artifact)` | success |
| `playwright (integrated E2E, opt-in)` | **skipped** (opt-in por diseño) |

**Lo decisivo:** el job `playwright (mock E2E)` —el que **rompió** a `v2.88.129` a móvil 390×844— queda **`success`** aquí; `certify` agrega y **certifica** con todos los obligatorios verdes. Con este run **VERDE**, el sello **subsume** definitivamente a `v2.88.129` (cuyo run `38574943655` quedó rojo).
