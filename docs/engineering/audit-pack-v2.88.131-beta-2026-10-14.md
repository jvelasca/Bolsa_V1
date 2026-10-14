# Audit pack — `v2.88.131-beta` (auditable desde GitHub)

> **AsOf:** 2026-10-14 · **Repo:** [`jvelasca/Bolsa_V1`](https://github.com/jvelasca/Bolsa_V1) (**público**) · **Tag:** `v2.88.131-beta`
> **Propósito:** reunir en un solo sitio **todo lo necesario para auditar esta versión desde GitHub sin credenciales**: identidad inmutable, cómo obtenerla, dónde está la evidencia, qué **certifica**, qué **NO**, y cómo **falsarlo**.
> **Naturaleza:** documento de **evidencia/enlace**, no de producto. **`Δ motor = 0` · `Δ decisión = 0` · `Δ contrato HTTP = 0`** (dominio puro read-only + CLI + gate PG + UI/shared + docs). Tag **unsigned** (anotado, sin firma GPG).
>
> **⚠️ Estado:** el tag `v2.88.131-beta` y su `Release tag CI` **aún no existen** en el momento de escribir este pack (el contenido está en el árbol de trabajo). Las secciones **1** (identidad: objeto/commit SHA) y **4** (run de CI) se **completan en el commit POST-TAG** tras empujar el tag, **sin** placeholders fabricados. Mismo patrón que `v2.88.130`/`v2.88.127`.

---

## 0. TL;DR — auditar en dos comandos

```bash
git clone --branch v2.88.131-beta --depth 1 https://github.com/jvelasca/Bolsa_V1.git
```

O, más estricto (fija el **commit** exacto, no el tag):

```bash
git clone https://github.com/jvelasca/Bolsa_V1.git && cd Bolsa_V1 && git checkout <SHA_DEL_SELLO>
```

> El `<SHA_DEL_SELLO>` y el objeto de tag se anotan en la §1 en el commit POST-TAG.

---

## 1. Identidad inmutable del sello

| Elemento | Valor |
| --- | --- |
| **Tag (anotado)** | `v2.88.131-beta` — **PENDIENTE de crear/empujar** |
| **Objeto de tag** | **PENDIENTE** (POST-TAG) |
| **Commit apuntado** | **PENDIENTE** (POST-TAG) |
| **Base (tag anterior)** | `v2.88.130-beta` → commit `f28bfb98` (objeto `1a91470c`) |
| **Versión monorepo** | `2.11.131-beta` ([`package.json`](../../package.json)) |
| **Alembic head** | `053_dia_d_cycle_verifications` (**sin migración**) |
| **Firma** | **unsigned** (anotado, sin GPG) |

---

## 2. Cómo obtener la versión

| Forma | Comando / enlace |
| --- | --- |
| Clonar el tag (recomendado) | `git clone --branch v2.88.131-beta --depth 1 https://github.com/jvelasca/Bolsa_V1.git` |
| Fijar el commit SHA | `git checkout <SHA_DEL_SELLO>` (POST-TAG) |
| Ver el árbol en la web | [tree/v2.88.131-beta](https://github.com/jvelasca/Bolsa_V1/tree/v2.88.131-beta) |

---

## 3. Evidencia — qué leer, en orden

| # | Documento | Qué responde |
| --- | --- | --- |
| 1 | [`evidence/v2.88.131/README.md`](./evidence/v2.88.131/README.md) | Evidencia del sello: cadena de 9 etapas desde hecho durable, CLI read-only, gate PG, UI «mejor puntuada vs ejecutada», verificación y **límites declarados** |
| 2 | [`CHANGELOG.md` §`2.11.131-beta`](../../CHANGELOG.md) | Nota de release: alcance, deltas, límites y verificación local |
| 3 | [`PROJECT_STATE.md`](./PROJECT_STATE.md) (AsOf `V2.88.131-beta`) | Estado vivo + **agenda funcional** (qué sigue abierto) |
| 4 | [`auto_chain_durable_reader.py`](../../packages/py/application/src/bolsa_application/auto_chain_durable_reader.py) | Lector durable ÚNICO de las 9 etapas por ciclo (dominio puro, read-only) |
| 5 | [`v2_99_auto_estudio_chain_evidence.py`](../../apps/api-python/scripts/v2_99_auto_estudio_chain_evidence.py) | CLI de evidencia por valor de ESTUDIO (JSON determinista, `readOnly=true`) |
| 6 | [`test_auto_estudio_chain_evidence_pg.py`](../../apps/api-python/tests/test_auto_estudio_chain_evidence_pg.py) | Gate PG fail-if-skipped: worker real sobre ESTUDIO sembrado + 9 etapas + P&L conciliado |

---

## 4. CI público (citable)

**`Release tag CI` del tag:** **PENDIENTE** (se cita en el commit POST-TAG).

Referencia de la **base** `v2.88.130-beta`: [run **`38578003227`**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38578003227) — `success` (~14m22s, `2026-10-14T14:09:26Z` → `14:23:48Z`).

**Lo que este sello ejercita en CI (declarado de antemano):** el nuevo test de cadena entra al paso DEDICADO de `lifecycle-pg` con `AUTO_ESTUDIO_CHAIN_PG_REQUIRED=1` y guard **anti-skip** (log no vacío + `grep` de `skipped` ⇒ `::error`); el censo de selección debe cerrar en **0 sin declarar**.

---

## 5. Qué **certifica** esta versión

Cierra la evidencia funcional de AUTO **por valor de ESTUDIO** desde **hechos durables**, sin tocar motor de decisión ni contrato HTTP:

- **Cadena de 9 etapas medible por ciclo.** Nuevo lector durable ÚNICO ([`auto_chain_durable_reader.py`](../../packages/py/application/src/bolsa_application/auto_chain_durable_reader.py)) que reutiliza `read_operational_monitor` (sin un segundo FIFO de P&L) y proyecta `SIGNAL → TOP_N → RISK → RESERVATION → ORDER → FILL → PROTECTION → SETTLEMENT → CYCLE_CLOSED`, + la verificación DÍA-D por `cycle_id`. Regla dura **`UNKNOWN ≠ 0`**.
- **Identidad ejecutada sin segunda verdad.** Con los resolutores **canónicos REUTILIZADOS** de [`estudio_audit`](../../packages/py/application/src/bolsa_application/estudio_audit.py) (`_cycles_for_symbol`/`_strategy_for_symbol`) el valor declara identidad **única o AMBIGUA** (jamás una «ganadora»); la foto `top3_opportunities` **no** sella identidad ⇒ `bestScoredPresetKey`/`presetMatch` son **huecos declarados**.
- **Eslabón DÍA-D contrastado con fuente INDEPENDIENTE.** `dia_d_link` reutiliza [`build_dia_d_cycle_verification_draft`](../../packages/py/application/src/bolsa_application/dia_d_cycle_verification.py); `executed_vs_dia_d` exige **ambas** partes (`None` + `UNKNOWN` con una sola).
- **Cierre de los 5 huecos del artefacto DÍA-D.** [`v2_89`](../../apps/api-python/scripts/v2_89_dia_d_auto_replay.py) deja de declarar huecos `SIGNAL`/`TOP_N`/`RISK`/`ORDER`/`SETTLEMENT`: ahora se cuentan desde fuente durable (`day_durable_chain_counts`); fuente ilegible ⇒ `None`.
- **Instrumento read-only NUEVO.** [`v2_99`](../../apps/api-python/scripts/v2_99_auto_estudio_chain_evidence.py) emite por valor de ESTUDIO y por `cycle_id` la cadena, la identidad **EJECUTADA** vs la **mejor puntuada**, el **P&L conciliado** y el DÍA-D.
- **Gate CI obligatorio (fail-if-skipped).** [`test_auto_estudio_chain_evidence_pg.py`](../../apps/api-python/tests/test_auto_estudio_chain_evidence_pg.py) conduce el **worker real** sobre ESTUDIO sembrado y asserta 9 etapas, identidad ejecutada (sin caer al `#1`), el resolutor canónico del valor (única/**AMBIGUA** + clasificación completa de ciclos), el eslabón DÍA-D (`linkable`/`matches`, sin fabricar veredicto), la conciliación `CYCLE_CLOSED == SETTLEMENT == libro aplicado` y control negativo por `cycleId` ajeno (que tampoco hereda DÍA-D); cableado a [`release-tag-ci.yml`](../../.github/workflows/release-tag-ci.yml) con guard anti-skip.
- **UI sin ambigüedad.** Rótulos `Mejor puntuada (Finalistas)` vs `Ejecutada (identidad del ciclo)` en 5 superficies + JSDoc en `@bolsa/shared`; **no** cambia la lógica de decisión.

**Deltas:** `Δ motor de decisión = 0` · `Δ decisión = 0` · **sin migración** (`053`) · **`Δ contrato HTTP = 0`** (no se amplía `/auto/estudio-audit`) · **`Δ CI ≠ 0`** (test PG nuevo cableado a `lifecycle-pg`). Cambio de `packages/py/application/**` + `apps/api-python/scripts`+`tests` + `.github/workflows/release-tag-ci.yml` + `apps/web/**` + `packages/shared/**` + docs.

---

## 6. Límites / huecos **declarados** (lo que NO certifica)

1. **NO cierra la ventana PAPER real** (`P3-2`/`P3-3`, ADR-046) ni la **rentabilidad/magnitud** del P&L: son **OPERACIÓN** + medición longitudinal (≥4 días de calendario, ≥2 regímenes, ≥32 ciclos medibles con `cycle_id`).
2. **El gate CI ejerce el worker real sobre ESTUDIO sembrado en PG:** es evidencia de la **cadena funcional**, **no** de mercado real.
3. **La foto TOP3 es cross-asset del MOTOR y best-effort:** sin foto durable, la «mejor puntuada» es un **hueco declarado** (no se inventa); y **aunque haya foto**, esa foto **no** sella identidad de estrategia ⇒ `bestScoredPresetKey`/`presetMatch` son `None` (nunca se rellenan con el preset de la ejecutada).
4. **La verificación DÍA-D es opcional por ciclo:** sin ella, el ciclo declara `diaD = None`, `executedVsDiaD.matches = None` (+`UNKNOWN`) y `diaDLink.linkable = False` (el borrador canónico no se rellena).
5. **Identidad ejecutada:** en el sandbox la estrategia es **sin versión**, así que `preset`/`version` viajan `None` (hueco **explícito**); el `rank` durable sí viaja. Con identidades dispares en un valor, la evidencia declara **AMBIGUO** en vez de elegir «ganadora».
6. **El eslabón externo** (bridge XTB, `XTB_BRIDGE_FILL_ORDERS`) queda **fuera** de lo verificable dentro del repo.
7. **Aislamiento XTB — residuos `P3`:** `G4` y `G6` siguen **CONFIRMADOS/declarados** (readonly, **no** cerrados) y `G3` residual (nombres no literales fuera del alcance del AST); `G2`/`G3`/`G5` **CERRADOS** en `v2.88.128`.
8. **Habilitación real:** `AUTO_ORCHESTRATOR_ENABLED`/`AUTO_SIMULATION_WORKER_ENABLED` nacen **OFF** (SIM-only).

---

## 7. Falsabilidad — cómo un auditor **rompe** cada afirmación

| # | Afirmación | Cómo se falsa |
| --- | --- | --- |
| 1 | Las 9 etapas se encienden desde durable en cada valor de ESTUDIO | `test_auto_estudio_chain_evidence_pg.py` falla en `steps[etapa] != 1` |
| 2 | La identidad ejecutada se sella sin caer al `#1` | falla la aserción de `rank` durable + `preset` honesto |
| 3 | El P&L concilia (`CYCLE_CLOSED == SETTLEMENT == libro aplicado`) | falla la comparación al quantum del dinero / la suma contra `realized_notional_from_applied_fills` |
| 4 | Un `cycleId` ajeno no hereda hechos | falla `chain.complete is False` / `steps["SIGNAL"] is None` |
| 5 | Sin PostgreSQL + gate ON no hay skip silencioso | el guard anti-skip de `lifecycle-pg` emite `::error` |
| 6 | Sin migración: head `053_dia_d_cycle_verifications` | `alembic heads` (desde `packages/py/infrastructure`) da otro head |
| 7 | `Δ contrato HTTP = 0` | `pnpm --filter @bolsa/web contract:check` falla (OpenAPI desincronizado) |
| 8 | Bump coherente | guardián [`test_dia_d_bump_guard`](../../apps/api-python/tests/test_dia_d_bump_guard.py) falla si un CLI difiere de `package.json` |

---

## 8. Reproducir la verificación (local, sin credenciales)

```bash
uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml
uv run --no-sync lint-imports --config packages/py/.importlinter
uv run --no-sync mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
  packages/py/application/src apps/api-python/src --follow-imports=silent
uv run --no-sync python -m pytest packages/py/application/tests -q
uv run --no-sync python -m pytest packages/py/application/tests/test_auto_chain_durable_reader.py \
  apps/api-python/tests/test_auto_estudio_chain_evidence_pg.py -q
uv run --no-sync python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
uv run --no-sync python scripts/ci/test_selection.py --report
pnpm --filter @bolsa/web test && pnpm --filter @bolsa/web typecheck && pnpm --filter @bolsa/web lint \
  && pnpm --filter @bolsa/web contract:check
```

**Resultados medidos de referencia (local):** lector durable + gate PG **14 passed** (13 unitarios + 1 PG real, `AUTO_ESTUDIO_CHAIN_PG_REQUIRED=1`) · `pytest packages/py/application/tests` **2744 passed** · `ruff` **All checks passed** · `import-linter` **4 kept / 0 broken** · `mypy` **no issues in 555 source files** · censo **623/623 · 0 sin declarar · 0 obsoletas** · guardián de bump **1 passed** (`2.11.131-beta`) · `pnpm --filter @bolsa/web test` **299 ficheros / 2195 passed** · `typecheck` **OK** · `lint` **0 errores / 23 warnings** (preexistentes) · `contract:check` **OK** · `alembic heads` `053_dia_d_cycle_verifications` (**sin migración**).
