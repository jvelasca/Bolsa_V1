# Audit pack — `v2.88.134-beta` (auditable desde GitHub)

> **AsOf:** 2026-10-15 · **Repo:** [`jvelasca/Bolsa_V1`](https://github.com/jvelasca/Bolsa_V1) (**público**) · **Tag:** `v2.88.134-beta`
> **Propósito:** reunir en un solo sitio **todo lo necesario para auditar esta versión desde GitHub sin credenciales**: identidad inmutable, cómo obtenerla, dónde está la evidencia, qué **certifica**, qué **NO**, y cómo **falsarlo**.
> **Naturaleza:** documento de **evidencia/enlace**, no de producto. Incremento **solo documentación** (respuesta a la auditoría externa del `v2.88.133`). **`Δ motor = 0` · `Δ decisión = 0` · `Δ contrato HTTP = 0` · sin migración**. Tag **unsigned**.
>
> **Base:** `v2.88.133-beta` → commit `530fa674290e23b0a23f074dc160f5f7c0681bf2`.

> **✅ Estado (POST-TAG):** la **identidad inmutable** del tag (§1: `lightweight` ⇒ commit `7cef7fcce0befbae54bd2e6062e357f116c0c3f4`) y el **run de CI del sello** (§4: `38708375980`, **VERDE**) ya están **citados**; el **re-anclaje del pin** (§7) está aplicado en el commit POST-TAG. Este pack queda **completo**.

---

## 0. TL;DR — auditar en un comando

```bash
git clone --branch v2.88.134-beta --depth 1 https://github.com/jvelasca/Bolsa_V1.git
```

> El `<SHA_DEL_SELLO>` es el commit `POST-TAG`/sello correspondiente (ver §1).

---

## 1. Identidad inmutable del sello

| Elemento | Valor |
| --- | --- |
| **Tag** | `v2.88.134-beta` — **lightweight** (**unsigned**) (el nombre apunta **directo** al commit) |
| **Objeto de tag** | **no hay objeto de tag** (lightweight) |
| **Commit apuntado** | `7cef7fcce0befbae54bd2e6062e357f116c0c3f4` (`v2.88.134 sello: …`) |
| **Base (tag anterior)** | `v2.88.133-beta` → `530fa674290e23b0a23f074dc160f5f7c0681bf2` |
| **Versión monorepo** | `2.11.134-beta` ([`package.json`](../../package.json)) |
| **Alembic head** | `053_dia_d_cycle_verifications` (**sin migración**) |
| **Firma** | **unsigned** |

> **Nota (flujo del repo).** El run del `Release tag CI` se cita en el commit **POST-TAG** (push del tag + re-anclaje del pin + este audit pack). Aquí la identidad del tag es **`lightweight`** y el SHA apuntado es el commit del sello `7cef7fcc…`.

---

## 2. Cómo obtener la versión

| Forma | Comando / enlace |
| --- | --- |
| Clonar el tag (recomendado) | `git clone --branch v2.88.134-beta --depth 1 https://github.com/jvelasca/Bolsa_V1.git` |
| Fijar el commit SHA | `git checkout 7cef7fcce0befbae54bd2e6062e357f116c0c3f4` |
| Ver el árbol en la web | [tree/v2.88.134-beta](https://github.com/jvelasca/Bolsa_V1/tree/v2.88.134-beta) |

---

## 3. Evidencia — qué leer, en orden

| # | Documento | Qué responde |
| --- | --- | --- |
| 1 | [`respuesta-auditoria-v2.88.133-beta-2026-10-15.md`](./respuesta-auditoria-v2.88.133-beta-2026-10-15.md) | **Documento central**: identidad del sello `v2.88.133`, qué certifica / qué NO, respuesta **punto por punto** al veredicto externo, **verificación propia del sello** (§4, 6/7 sostenidas), **hallazgo del pin** (§5) y **pendientes `P1`-`P4`** con criterio falsable (§6) |
| 2 | [`evidence/v2.88.134/README.md`](./evidence/v2.88.134/README.md) | Evidencia del sello docs-only: contenido, verificación propia y límites declarados |
| 3 | [`CHANGELOG.md` §`2.11.134-beta`](../../CHANGELOG.md) | Nota de release: alcance, deltas, límites y verificación local |
| 4 | [`PROJECT_STATE.md`](./PROJECT_STATE.md) (AsOf `V2.88.134-beta`) | Estado vivo + **agenda funcional** (qué sigue abierto) |
| 5 | [`evidence/v2.88.133/README.md`](./evidence/v2.88.133/README.md) + [`audit-pack-v2.88.133-beta-2026-10-15.md`](./audit-pack-v2.88.133-beta-2026-10-15.md) | Sello auditado: `G6` a nivel de handler, panel FA, goldens win32, helper del sello de ciclo |
| 6 | [`evidencia-readonly-auto-paper-2026-10-14.md`](./evidencia-readonly-auto-paper-2026-10-14.md) | Medición read-only de AUTO/PAPER (35 ESTUDIO, `0/35` ciclos, `0` fills con `cycle_id`, ventana `INCONCLUSIVE`) |
| 7 | [`plan-ventana-paper-arranque-operativo-2026-10-14.md`](./plan-ventana-paper-arranque-operativo-2026-10-14.md) | Runbook de la ventana PAPER (umbrales 4/2/32, freeze/`TREE_MOVED`, comandos) |
| 8 | [`adr/046-protocolo-longitudinal-paper.md`](../adr/046-protocolo-longitudinal-paper.md) | Criterio longitudinal PAPER (snapshots durables; `CONFIRMED` es humano) |

---

## 4. CI público (citable)

**Run del `Release tag CI` del sello:** [`38708375980`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38708375980) — **VERDE** (~14m30s, `2026-10-15T08:49:03Z` → `09:03:33Z`; **todos los jobs `success`**, incluido el agregado `certify`, y con `playwright (integrated E2E, opt-in)` = `skipped` **por diseño**). El **gate duro** `playwright (integrated axe)` queda **`success`** y `replay-repro` **REPRODUCIDO** ⇒ `Δ decisión = 0` confirmado por CI; `decision-spine`, `shared`, `python (ruff/imports/mypy/pytest offline)`, `frontend (typecheck/lint/test/build + contract:check)`, `lifecycle-pg`, `dr-verify`, `a7-gate`, `playwright (mock E2E)` y `playwright (integrated AUTO S5)` **`success`**. **Sello CERRADO.**

**Referencia de la base** `v2.88.133-beta`: `Release tag CI` [run `38704219628`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38704219628) — `success` (~13m23s).

---

## 5. Qué **certifica** esta versión

Incremento **solo documentación** — cierra la **trazabilidad de la respuesta a la auditoría externa** del sello anterior, sin tocar motor, decisión ni contrato HTTP:

- **Documento de respuesta a la revisión externa del `v2.88.133-beta`.** [`respuesta-auditoria-v2.88.133-beta-2026-10-15.md`](./respuesta-auditoria-v2.88.133-beta-2026-10-15.md): acepta el veredicto externo (sello técnico **VERDE**; certificación **operativa ABIERTA** por falta de operación), lo confirma con `file:line` y **no refuta ningún punto**.
- **Verificación propia del sello (frente B):** **6 de 7 afirmaciones SOSTENIDAS** con evidencia `file:line` (`G6` a nivel de handler, panel FA ante DTO violado, helper del sello de ciclo con fill COMPLETO, UI AUTO/verificación DÍA-D fail-closed, CI, tag lightweight). La 7ª (`pin`) es **PARCIAL**.
- **Hallazgo del pin:** en el commit del tag `530fa674` el `WINDOW_CONFIG` aún apuntaba al árbol de `v2.88.132`; el re-anclaje vive en el commit **POST-TAG** `fcfc57f0`. El sello **no era autocontenido** respecto del pin (`scripts/` no participa del freeze del motor).
- **Pendientes `P1`-`P4`** (ventana PAPER real, evidencia por valor de ESTUDIO, DÍA-D ligado al ciclo, barreras fail-closed) con **criterio falsable** y comandos reales.

**Deltas:** `Δ motor de decisión = 0` · `Δ decisión = 0` · **`Δ contrato HTTP = 0`** · **sin migración** (`053_dia_d_cycle_verifications`). Cambio de `package.json` + `meta.bump` de los 12 CLIs + `docs/` + `CHANGELOG.md`.

---

## 6. Límites / huecos **declarados** (lo que NO certifica)

1. **Ventana PAPER real (`P3-2`/`P3-3`, ADR-046): `0/4 días`, `0/2 regímenes`, `0/32 ciclos` ⇒ `INCONCLUSIVE`.** Lo que falta es **OPERACIÓN** (≥4 días de calendario sellando hechos durables, ≥2 regímenes y ≥32 ciclos medibles con `cycle_id`), **no** software.
2. **Bloqueo de mercado medido (2026-10-15).** El preflight de hoy declara **`BEAR_TREND` con LONG vetadas** (`entriesAllowedLong:false`) ⇒ `window:run-day` **no** produciría un día medible (idéntico al 2026-10-14). El ledger está en `medidos=0 veto=1 declarados=0 duros=0`, gate `NO_MEDIDO`.
3. **Este sello es docs-only.** No reclama ningún cambio de producto; su valor es la **trazabilidad** de la respuesta a la auditoría externa. El árbol `apps` del sello mueve **solo** por el `meta.bump` de los 12 CLIs.
4. **Bridge XTB externo.** Frontera de confianza **EXTERNA** al repo (residual `G6`).
5. **`G3` residual.** `getattr(<objeto-local>, <variable>)` sobre objeto de datos sigue fuera del invariante (límite declarado).
6. **No ejecutado en local (declarado).** `replay-repro` no es ejecutable en Windows (CRLF/entorno); `dr-verify` y `security` no se pudieron correr en local (faltan binarios). Se cubren en CI.
7. **Habilitación real:** `AUTO_ORCHESTRATOR_ENABLED`/`AUTO_SIMULATION_WORKER_ENABLED` nacen **OFF** (SIM-only).

> **Trazabilidad de los pendientes `P1`-`P4` (OPERACIÓN):** ver §6 de [`respuesta-auditoria-v2.88.133-beta-2026-10-15.md`](./respuesta-auditoria-v2.88.133-beta-2026-10-15.md). Discrepancias documentales declaradas allí: `dias=42/4` vs `0/4`; `verdict` es `READY`/`INCONCLUSIVE` (no `CERTIFIED`); el campo real es `PAPER_EVIDENCE_SNAPSHOT_ENABLED`.

---

## 7. Falsabilidad — cómo un auditor **rompe** cada afirmación

| # | Afirmación | Cómo se falsa |
| --- | --- | --- |
| 1 | Verificación propia del sello: 6/7 SOSTENIDAS | leer las líneas citadas en §4 del documento de respuesta y comprobar que el código hace lo que dice |
| 2 | El pin se re-ancló POST-TAG (PARCIAL) | `git show 530fa674:scripts/lib/window-forward.mjs` vs `HEAD` (pin del tag apuntaba a `05dc2d5b`/`5696698e…`) |
| 3 | Freeze OK tras el re-anclaje | `git rev-parse HEAD:apps HEAD:packages` == `appsHash`/`packagesHash` de `WINDOW_CONFIG` (`apps 86052343…` / `packages d48ac37b…`) |
| 4 | `Δ contrato HTTP = 0` | `pnpm --filter @bolsa/web contract:check` falla (OpenAPI desincronizado) |
| 5 | Bump coherente | guardián [`test_dia_d_bump_guard`](../../apps/api-python/tests/test_dia_d_bump_guard.py) falla si un CLI difiere de `package.json` |
| 6 | Sin migración: head `053_dia_d_cycle_verifications` | `alembic heads` (desde `packages/py/infrastructure`) da otro head |
| 7 | La ventana sigue `INCONCLUSIVE` | `pnpm run window:status` (gate `NO_MEDIDO`) o `v2_98` > 0 lo falsaría |

---

## 8. Reproducir la verificación (local, sin credenciales)

```bash
uv run --no-sync python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
pnpm run window:status
git rev-parse HEAD:apps HEAD:packages
pnpm --filter @bolsa/web contract:check
```

**Resultados medidos de referencia (local):** guardián de bump **1 passed** (`2.11.134-beta`) · `window:status` gate `NO_MEDIDO` (`medidos=0 veto=1`) · `Δ motor = 0` · `Δ decisión = 0` · `Δ contrato HTTP = 0` · `alembic heads` `053_dia_d_cycle_verifications` (**sin migración**).
