# Audit pack — `v2.88.130-beta` (auditable desde GitHub)

> **AsOf:** 2026-10-14 · **Repo:** [`jvelasca/Bolsa_V1`](https://github.com/jvelasca/Bolsa_V1) (**público**) · **Tag:** `v2.88.130-beta`
> **Propósito:** reunir en un solo sitio **todo lo necesario para auditar esta versión desde GitHub sin credenciales**: identidad inmutable, cómo obtenerla, dónde está la evidencia, qué **certifica**, qué **NO**, y cómo **falsarlo**.
> **Naturaleza:** documento de **evidencia/enlace**, no de producto. **`Δ producto = 0` · `Δ decisión = 0` · `Δ motor = 0`** (solo **`apps/web/**` + workflow opt-in + docs**). Este sello **SUPERA/CORRIGE** a `v2.88.129-beta` (cuyo `Release tag CI` falló). Tag **unsigned** (anotado, sin firma GPG).

---

## 0. TL;DR — auditar en dos comandos

```bash
git clone --branch v2.88.130-beta --depth 1 https://github.com/jvelasca/Bolsa_V1.git
```

O, más estricto (fija el **commit** exacto, no el tag):

```bash
git clone https://github.com/jvelasca/Bolsa_V1.git && cd Bolsa_V1 && git checkout f28bfb98b7d8d7d065b878cd93c6321f3b775947
```

---

## 1. Identidad inmutable del sello

| Elemento | Valor |
| --- | --- |
| **Tag (anotado)** | `v2.88.130-beta` |
| **Objeto de tag** | `1a91470ce3660d33af53d10466ddfd81a9540440` |
| **Commit apuntado** | `f28bfb98b7d8d7d065b878cd93c6321f3b775947` (contenido del sello: fix a11y de `/backtests` + barrido `axe` integrado opt-in) |
| **Padre del commit** | `51b368bf` (commit de sello de `v2.88.129-beta`) |
| **Base (tag anterior)** | `v2.88.129-beta` → `51b368bf` (objeto `b30e6bb0`) |
| **Versión monorepo** | `2.11.130-beta` ([`package.json`](../../package.json)) |
| **Alembic head** | `053_dia_d_cycle_verifications` (**sin migración**) |
| **Firma** | **unsigned** (anotado, sin GPG) |

> **Nota:** el tag anotado sella el **contenido** del sello (`f28bfb98`). Este audit pack es un artefacto **POST-TAG** que vive en `main`, **por delante** del tag (mismo patrón que `v2.88.125`/`v2.88.127`/`v2.88.128`). Se escribe **después** de que exista el run de CI, para **no** dejar placeholders en ningún árbol.

---

## 2. Cómo obtener la versión

| Forma | Comando / enlace |
| --- | --- |
| Clonar el tag (recomendado) | `git clone --branch v2.88.130-beta --depth 1 https://github.com/jvelasca/Bolsa_V1.git` |
| Fijar el commit SHA | `git checkout f28bfb98` |
| Ver el árbol en la web | [tree/v2.88.130-beta](https://github.com/jvelasca/Bolsa_V1/tree/v2.88.130-beta) |
| Ver el commit del sello | [commit/f28bfb98](https://github.com/jvelasca/Bolsa_V1/commit/f28bfb98) |

---

## 3. Evidencia — qué leer, en orden

| # | Documento | Qué responde |
| --- | --- | --- |
| 1 | [`evidence/v2.88.130/README.md`](./evidence/v2.88.130/README.md) | Evidencia del sello: qué cierra cada cambio (supersesión de 129 + barrido `axe` integrado), verificación y **límites declarados** |
| 2 | [`CHANGELOG.md` §`2.11.130-beta`](../../CHANGELOG.md) | Nota de release: alcance, deltas, límites, verificación local y **cita POST-TAG** |
| 3 | [`PROJECT_STATE.md`](./PROJECT_STATE.md) (AsOf `V2.88.130-beta`) | Estado vivo + **agenda funcional** (qué sigue abierto) |
| 4 | [`evidence/v2.88.129/README.md`](./evidence/v2.88.129/README.md) | Evidencia de `v2.88.129` — su `Release tag CI` **FALLIDO** ([run `38574943655`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38574943655)), causa y fix que **subsume** este sello |
| 5 | [`gp-e2e-ui5-0-axe-integrated.spec.ts`](../../apps/web/e2e/gp-e2e-ui5-0-axe-integrated.spec.ts) | Barrido `axe` **INTEGRADO** opt-in (stack real) que **mitiga** la deuda «`axe` solo con mocks» |

---

## 4. CI público (citable)

**`Release tag CI` del tag (VERDE):** [run **38578003227**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38578003227) — `success` en **~14m22s** (2026-10-14T14:09:26Z → 14:23:48Z), sobre `f28bfb98b7d8d7d065b878cd93c6321f3b775947`.

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

**Lo decisivo:** el job `playwright (mock E2E)` —el que **rompió** a `v2.88.129` a móvil 390×844— queda **`success`** aquí; `certify` agrega y **certifica** con todos los obligatorios verdes; `replay-repro` = `success` ⇒ el artefacto congelado **se reproduce** (coherente con **`Δ decisión = 0`**).

**Artefactos descargables** (pestaña *Artifacts* del run):

| Artefacto | Tamaño | Id | Qué es |
| --- | --- | --- | --- |
| `release-tag-ci-summary` | 430 B | `11903050610` | Resumen agregado de la certificación |
| `replay-oos-durable-v2.88.7` | 306 720 B | `11902131994` | **Sello congelado** del replay OOS (reproducible) |

---

## 5. Qué **certifica** esta versión

Corrige el fallo de CI que tumbó a `v2.88.129-beta` y añade un barrido `axe` **integrado** opt-in, sin tocar motor, decisión ni contrato HTTP:

- **SUPERACIÓN de `v2.88.129-beta` (su `Release tag CI` falló).** El run [`38574943655`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38574943655) quedó **rojo** en el job `playwright (mock E2E)`, test `[/backtests @móvil 390×844] · scrollable-region-focusable [serious] ×1` sobre el nodo `.p-3.overflow-auto.pt-0`. El **fix** añade `role="region"` + `aria-label="Resultados del backtest"` + `tabIndex={0}` al [`CardContent` de resultados](../../apps/web/src/features/backtests/backtests-page-run-tab.tsx) **solo cuando es la rama scrolleable** (const `resultsRegionScrollable`, es decir fuera del foco de análisis). **Falsabilidad demostrada:** con viewport **390×380** el fallo **se reproduce sin el fix**; con el fix **pasa**.
- **Barrido `axe` INTEGRADO opt-in NUEVO.** [`gp-e2e-ui5-0-axe-integrated.spec.ts`](../../apps/web/e2e/gp-e2e-ui5-0-axe-integrated.spec.ts) barre **5 rutas L1** (`/operational-console`, `/decision-journal`, `/mesa`, `/trading`, `/auto-monitor?mode=current`) contra **stack real** (FastAPI + PostgreSQL, sin mocks de `/api/*`) con `E2E_INTEGRATION=1`, exigiendo **0 violaciones `critical`/`serious`** (WCAG 2.0/2.1 A+AA), `heading-order` **sin saltos** y **exactamente un `main` + un `h1`**. Se **cablea al job opt-in** `playwright (integrated)` de [`release-tag-ci.yml`](../../.github/workflows/release-tag-ci.yml) — **NO** al gate duro del tag.
- **HERENCIA de `heading-order` (de `v2.88.129`).** Este sello **subsume** el cierre de `heading-order` de 129 (`CardTitle.level` + **gate unitario durable** [`heading-order.test.tsx`](../../apps/web/src/test/heading-order.test.tsx) + barrido **mock** ampliado a las 8 rutas heredadas) y lo acompaña del **CI verde** de `v2.88.130`.

**Deltas:** `Δ producto = 0` · `Δ decisión = 0` · `Δ motor = 0` · **sin migración** (`053`) · **`Δ contrato = 0`** · **`Δ CI ≠ 0`** (el workflow `release-tag-ci.yml` cambia: se **cablea** el spec integrado al job **opt-in** ya existente; **no** se vuelve gate duro). Cambio solo de **`apps/web/**` + `.github/workflows/release-tag-ci.yml` + docs**.

---

## 6. Límites / huecos **declarados** (lo que NO certifica)

1. **El barrido `axe` integrado es `desktop-only`:** mide a **1366×768**; **no** cubre **móvil** (el fallo que tumbó a `129` apareció a **390×844**, cubierto por el barrido **mock**).
2. **Subconjunto acotado y opt-in:** **5 rutas L1** (no todas) y **skip-by-default** (`E2E_RUN=1 E2E_INTEGRATION=1 E2E_ALLOW_DEV_DB=1`); **no** es gate duro del tag. El resto de la certificación `axe` sigue **mock-only**.
3. **Deuda UI restante (estado declarado):**
   - **`heading-order` — CERRADA** (heredada de `v2.88.129`; gate unitario durable + barrido mock ampliado), ahora con **CI verde**.
   - **«`axe` solo con mocks» — MITIGADA (en parte), NO cerrada**: el barrido **integrado opt-in** de **5 rutas L1 desktop** mitiga la deuda (ya se ejerce contra stack real) pero **no** la cierra — sigue abierta como «**no** es gate duro / **no** cubre móvil ni todas las rutas».
4. **El eslabón externo** (bridge XTB, `XTB_BRIDGE_FILL_ORDERS`) queda **fuera** de lo verificable dentro del repo.
5. **P&L** — el DÍA-D certifica **identidad de fuentes y motivos**, **no** rentabilidad ni magnitud.
6. **Habilitación real** — `AUTO_ORCHESTRATOR_ENABLED`/`AUTO_SIMULATION_WORKER_ENABLED` nacen **OFF** (SIM-only).
7. **Aislamiento XTB — residuos `P3`:** **`G4`** y **`G6`** siguen **CONFIRMADOS/declarados** (readonly, **no** cerrados) y **`G3` residual** (nombres no literales fuera del alcance del AST); **`G2`/`G3`/`G5` CERRADOS** en `v2.88.128`.

---

## 7. Falsabilidad — cómo un auditor **rompe** cada afirmación

| # | Afirmación | Cómo se rompe |
| --- | --- | --- |
| 1 | El tag `v2.88.130-beta` apunta al commit del sello y este desciende de `v2.88.129-beta` (`51b368bf`). | `git rev-parse` / `git cat-file -p` del tag da otro commit o linaje. |
| 2 | `2.11.130-beta` es la versión del árbol. | `package.json` muestra otra versión. |
| 3 | El `CardContent` de resultados de backtests es alcanzable por teclado cuando es la rama scrolleable. | Quitar `role`/`aria-label`/`tabIndex` ⇒ el sondeo axe a **390×380** (o el barrido mock a móvil) vuelve a marcar `scrollable-region-focusable`. |
| 4 | El barrido `axe` **integrado** pasa en las 5 rutas L1. | Una violación `critical`/`serious` (o un salto `heading-order`) en una de las 5 rutas rompe [`gp-e2e-ui5-0-axe-integrated.spec.ts`](../../apps/web/e2e/gp-e2e-ui5-0-axe-integrated.spec.ts). |
| 5 | El barrido integrado **no** es gate duro (opt-in). | El tag CI lo ejecuta en el run obligatorio (no `skipped`) o el job `playwright (integrated)` pasa a requerido. |
| 6 | `heading-order` sigue cerrado en las superficies L1. | Una página L1 con salto de nivel, 0 o 2 `h1` rompe el gate unitario [`heading-order.test.tsx`](../../apps/web/src/test/heading-order.test.tsx). |
| 7 | Sin migración: head `053_dia_d_cycle_verifications`. | `alembic heads` (desde `packages/py/infrastructure`) da otro head. |
| 8 | El `Release tag CI` del tag es **verde**. | El run citado tiene algún job (obligatorio) en `failure`. |
| 9 | El barrido integrado está **cableado al job opt-in** (no al gate duro). | Revisar [`release-tag-ci.yml`](../../.github/workflows/release-tag-ci.yml): el spec integrado no aparece en el job opt-in, o aparece en un job obligatorio. |

---

## 8. Reproducir la verificación (local, opcional)

```bash
# Barrido axe MOCK completo (14 rutas L1 × desktop+móvil + command palette)
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-e2e-ui5-0-axe-touched-routes-mock.spec.ts

# Barrido axe INTEGRADO opt-in (stack real; requiere FastAPI + PostgreSQL local)
E2E_RUN=1 E2E_INTEGRATION=1 E2E_ALLOW_DEV_DB=1 pnpm --filter @bolsa/web e2e -- gp-e2e-ui5-0-axe-integrated.spec.ts

# Gate unitario durable heading-order + suite web + typecheck/lint
pnpm --filter @bolsa/web test
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web lint

# Guardián de bump
uv run --no-sync python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
```

**Resultados medidos de referencia (local):** spec axe **mock** completo **29 passed** (`heading-order` **0**) · spec axe **integrado** **5 passed** (desktop 1366×768, stack real local) · gate unitario `heading-order.test.tsx` **10 passed** · `pnpm --filter @bolsa/web test` **299 ficheros / 2194 passed** · `typecheck` **OK** · `lint` **0 errores / 23 warnings** (preexistentes) · guardián de bump **1 passed** (`2.11.130-beta`) · `alembic heads` `053_dia_d_cycle_verifications` (**sin migración**).

> **Nota de alcance:** esta pasada fue de sellado de tests + docs (a11y de `apps/web/**` + spec E2E integrado + documentación), sin cambio de lógica de producto; las suites completas las cubre el `Release tag CI` del tag (arriba), y el `CHANGELOG`, el `PROJECT_STATE` y la evidencia lo **declaran** de forma explícita.
