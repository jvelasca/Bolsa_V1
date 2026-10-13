# Audit pack — `v2.88.125-beta` (auditable desde GitHub)

> **AsOf:** 2026-10-13 · **Repo:** [`jvelasca/Bolsa_V1`](https://github.com/jvelasca/Bolsa_V1) (**público**) · **Tag:** `v2.88.125-beta`
> **Propósito:** reunir en un solo sitio **todo lo necesario para auditar esta versión desde GitHub sin credenciales**: identidad inmutable, cómo obtenerla, dónde está la evidencia, qué **certifica**, qué **NO**, y cómo **falsarlo**.
> **Naturaleza:** documento de **evidencia/enlace**, no de producto. **`Δ motor = 0` · `Δ decisión = 0`** (no toca código). Tag **unsigned** (anotado, sin firma GPG).

---

## 0. TL;DR — auditar en dos comandos

```bash
git clone --branch v2.88.125-beta --depth 1 https://github.com/jvelasca/Bolsa_V1.git
```

O, más estricto (fija el **commit** exacto, no el tag):

```bash
git clone https://github.com/jvelasca/Bolsa_V1.git && cd Bolsa_V1 && git checkout 9be55ed7937661cce7d6a2e1df48af124732429b
```

---

## 1. Identidad inmutable del sello

| Elemento | Valor |
| --- | --- |
| **Tag (anotado)** | `v2.88.125-beta` |
| **Objeto de tag** | `74c161e0065e277d88113af4591207ae1e3b28a6` |
| **Commit apuntado** | `9be55ed7937661cce7d6a2e1df48af124732429b` |
| **Padre del commit** | `897de009114759b9bd469f323e6bbd8f3e708c6e` (contenido del sello) |
| **Commit POST-TAG (= `origin/main`)** | `c42a87cfc0a9b5b31d3b3e189b5df4d5fbd40228` |
| **Versión monorepo** | `2.11.125-beta` ([`package.json`](../../package.json)) |
| **Alembic head** | `053_dia_d_cycle_verifications` (**sin migración**) |
| **Firma** | **unsigned** (anotado, sin GPG) |

**Cadena entregada por este tag** (un commit, tres sellos documentados por separado):

```
2a4a3d49  v2.88.122 POST-TAG
  └─ 897de009  v2.88.123-125: contenido del sello (contenido de los tres frentes)
       └─ 9be55ed7  v2.88.125 FIX CI (bug asyncio)   ← v2.88.125-beta apunta AQUÍ
            └─ c42a87cf  v2.88.125 POST-TAG (documentación)  ← origin/main
```

> El tag apunta al commit **con el fix** (`9be55ed7`), no al commit inicial, para que el sello sea **verde** (ver §7).

---

## 2. Cómo obtener la versión

| Forma | Comando / enlace |
| --- | --- |
| Clonar el tag (recomendado) | `git clone --branch v2.88.125-beta --depth 1 https://github.com/jvelasca/Bolsa_V1.git` |
| Fijar el commit SHA | `git checkout 9be55ed7` |
| Ver el árbol en la web | [tree/v2.88.125-beta](https://github.com/jvelasca/Bolsa_V1/tree/v2.88.125-beta) |
| Ver el commit del sello | [commit/9be55ed7](https://github.com/jvelasca/Bolsa_V1/commit/9be55ed7) |

---

## 3. Evidencia — qué leer, en orden

| # | Documento | Qué responde |
| --- | --- | --- |
| 1 | [`evidence/v2.88.125/README.md`](./evidence/v2.88.125/README.md) | Evidencia del sello: qué certifica cada frente, verificación y **huecos declarados** |
| 2 | [`CHANGELOG.md` §`2.11.125-beta`](../../CHANGELOG.md) | Nota de release: alcance, deltas, límites, CI y corrección declarada |
| 3 | [`PROJECT_STATE.md`](./PROJECT_STATE.md) (AsOf `V2.88.125-beta`) | Estado vivo + **agenda funcional** (qué sigue abierto) |
| 4 | [`deuda-cierre-dia-d-h3-h5-h6-2026-10-13.md`](./deuda-cierre-dia-d-h3-h5-h6-2026-10-13.md) | Huecos `H3`/`H5`/`H6` con criterio **falsable** |
| 5 | [`auditoria-ui-olas-2-6-2026-10-13.md`](./auditoria-ui-olas-2-6-2026-10-13.md) | Auditoría de olas UI 2..6 (veredicto por ola) |
| 6 | [`evidence/v2.88.123/README.md`](./evidence/v2.88.123/README.md) · [`v2.88.124`](./evidence/v2.88.124/README.md) | Evidencia de los dos sellos previos de la cadena |

---

## 4. CI público (citable)

**`Release tag CI` del tag (VERDE):** [run **38422158624**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38422158624) — `success` en **11m55s** (2026-10-13T15:27:02Z → 15:38:57Z).

| Job | Conclusión |
| --- | --- |
| `python (ruff/imports/mypy/pytest offline)` | success |
| `lifecycle-pg (Alembic + auth + golden restart)` | success |
| `frontend (typecheck/lint/test/build + contract:check)` | success |
| `shared (build/typecheck/test)` | success |
| `decision-spine` | success |
| `dr-verify (battery DB_DR / TCP CI)` | success |
| `replay-repro (regenera el artefacto del sello desde el fixture)` | success |
| `a7-gate (A7 C3 chaos live_a7 · dedicated real-PG)` | success |
| `playwright (mock E2E)` · `playwright (integrated AUTO S5)` | success |
| `security (gitleaks)` | success |
| `certify (aggregate + artifact)` | success |
| `playwright (integrated E2E, opt-in)` | **skipped** (opt-in por diseño) |

**Lo decisivo:** el paso `Pytest AUTO universe coverage + DÍA-D trace + daily watch ESTUDIO + PAPER window (PG, fail if skipped)` y su **guard anti-skip** salieron `success` (gates ON), y **`replay-repro`** = `success` ⇒ el artefacto congelado **se reproduce**, coherente con **`Δ decisión = 0`**.

**Artefactos descargables** (pestaña *Artifacts* del run):

| Artefacto | Tamaño | Id | Qué es |
| --- | --- | --- | --- |
| `release-tag-ci-summary` | 429 B | `11827392485` | Resumen agregado de la certificación |
| `replay-oos-durable-v2.88.7` | 306 720 B | `11826919276` | **Sello congelado** del replay OOS (reproducible) |

**CI de `main` del fix** (`9be55ed7`): `Python CI` [38422153690](https://github.com/jvelasca/Bolsa_V1/actions/runs/38422153690) · `Gitleaks` [38422153630](https://github.com/jvelasca/Bolsa_V1/actions/runs/38422153630) — `success`.

---

## 5. Qué **certifica** esta versión

Cierra los **tres frentes restantes** del veredicto de auditoría:

- **`paso 3` — DÍA-D por valor y ciclo.** `CYCLE_CLOSED` **deja de afirmar `"flat"`**: el motivo se lee del hecho durable `settlement.exitReason` del MISMO ciclo o viaja `null`/`UNKNOWN` (**`UNKNOWN ≠ 0`**). Traza DÍA-D conciliada **por valor y ciclo** (PG real, ≥2 instrumentos, sin herencia) y la etapa `DECISION` del relato consume `reasonCodes`.
- **`paso 4a` — certificador de la ventana PAPER (`P3-2`/`P3-3`, ADR-046).** Función **pura** `certify_paper_window` (umbrales de **fuente única**, no re-declarados) + CLI `v2_98` + test PG **cableado** en `lifecycle-pg`. **`None ≠ 0`**; si no se alcanza la ventana ⇒ `INCONCLUSIVE` **sin fabricar**.
- **`paso 4b` — auditoría olas UI 2..6.** Veredicto itemizado: **olas 2..5 `DONE`** (P2 declarados) y **ola 6 `ABIERTA`**; censo falsable **+17 superficies**.

**Deltas:** `Δ decisión = 0` · **sin migración** (`053`) · **sin cambio de contrato HTTP**.

---

## 6. Límites / huecos **declarados** (lo que NO certifica)

1. **`H3`** — la «señal de salida» sigue plegada en `SETTLEMENT` (no hay etapa `EXIT` propia).
2. **`H5`** — el monitor sigue **sin** consulta por instrumento.
3. **`H6`** — el CTA manual verifica el **#1 de Finalistas**, no la estrategia **ejecutada**.
4. **Ventana PAPER longitudinal (`P3-2`/`P3-3`)** — el certificador **existe**, pero la ventana **real sigue `NO MEDIDO`** (OPERACIÓN: ≥4 días de **calendario** / ≥2 episodios / ≥32 ciclos). **No** se emite `CONFIRMED`.
5. **Ola 6 (Consola avanzada)** — sigue abierta (nivel 3 explícito pendiente); `heading-order` (11 rutas L1) y `axe` (solo con mocks) siguen como deuda preexistente.
6. **P&L** — el DÍA-D certifica **identidad de fuentes y motivos**, **no** rentabilidad ni magnitud.
7. **Habilitación real** — `AUTO_ORCHESTRATOR_ENABLED`/`AUTO_SIMULATION_WORKER_ENABLED` nacen **OFF** (SIM-only).

---

## 7. Incidente **declarado** del sello (honestidad)

El **primer** `Release tag CI` de la cadena ([38409994837](https://github.com/jvelasca/Bolsa_V1/actions/runs/38409994837)) salió **rojo** por un **bug real del propio sello**: [`_estudio_pg_helpers.py`](../../apps/api-python/tests/_estudio_pg_helpers.py) importaba `asyncio` **solo** dentro del bloque `if sys.platform == "win32"` pero usa `asyncio.to_thread` de forma **incondicional** ⇒ en Windows pasaba y en **Linux** (job `lifecycle-pg`) el nombre no existía (`NameError`), que el gate fail-if-skipped convertía en ERROR de setup en los **5** ficheros PG.

- **Corrección:** commit `9be55ed7` (`import asyncio` a nivel de módulo; verificado con **simulación Linux** + lote PG dedicado **18 passed**).
- **Re-sello:** el tag se **movió** de `897de009` a `9be55ed7`; `Release tag CI` [38422158624](https://github.com/jvelasca/Bolsa_V1/actions/runs/38422158624) **verde**.

---

## 8. Falsabilidad — cómo un auditor **rompe** cada afirmación

| # | Afirmación | Cómo se rompe |
| --- | --- | --- |
| 1 | El tag `v2.88.125-beta` apunta al commit `9be55ed7` y este tiene por padre `897de009`. | `git rev-parse` / `git cat-file -p` del tag da otro commit o padre. |
| 2 | `2.11.125-beta` es la versión del árbol. | `package.json` muestra otra versión. |
| 3 | `CYCLE_CLOSED` no afirma `"flat"` cuando falta hecho durable. | `auto_operational_monitor._cycle_closed_step` publica `"flat"` sin `settlement.exitReason`. |
| 4 | El certificador **no fabrica** (ventana no alcanzada ⇒ `INCONCLUSIVE`, no `READY`). | `certify_paper_window` devuelve `READY` con criterios faltantes, o `0` donde no midió. |
| 5 | El censo de tests no tiene ficheros invisibles. | `uv run python scripts/ci/test_selection.py --report` muestra `SIN DECLARAR > 0`. |
| 6 | El `Release tag CI` del tag es **verde** con el paso PG y el guard anti-skip en `success`. | El run citado tiene algún job en `failure`, o el paso PG en `skipped`. |
| 7 | `replay-repro` reproduce el sello congelado (`Δ decisión = 0`). | El job `replay-repro` falla o el artefacto no coincide. |
| 8 | Sin migración: head `053_dia_d_cycle_verifications`. | `alembic heads` (desde `packages/py/infrastructure`) da otro head. |

---

## 9. Reproducir la verificación (local, opcional)

```bash
# Lint / tipos / contratos / import-linter (comando de CI)
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
            packages/py/application/src apps/api-python/src --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter

# Suites
uv run pytest packages/py/application/tests -q
pnpm --filter @bolsa/shared test
pnpm --filter @bolsa/web test

# Censo de selección (agujero declarado)
uv run python scripts/ci/test_selection.py --report
```

**Resultados medidos de referencia (local):** `ruff` *All checks passed* · `mypy` *554 files, no issues* · `import-linter` *4 kept / 0 broken* · `pytest packages/py/application/tests` **2727 passed** · lote PG dedicado (5 ficheros / 5 gates) **18 passed** · `@bolsa/shared` **829 passed** · `@bolsa/web` **2159 passed** · censo **0 sin declarar**.
