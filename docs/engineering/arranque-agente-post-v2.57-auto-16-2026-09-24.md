# Arranque del agente — post `v2.57-beta` (`AUTO-16` cerrada) · 2026-09-24

**Rama `main`** en fast-forward · **Tag `v2.57-beta`** · **`1.82.0-beta`** · **Fase anterior cerrada:**
`V2.57` / `AUTO-16` «Coste REAL por ciclo: el neto declara su base».

---

## 0. El prompt para arrancar (cópialo tal cual)

> Trabajas en `Bolsa_V1` (repo del propietario). **No improvises el método**: el repo tiene un
> protocolo y se sigue. Antes de tocar nada:
>
> 1. Lee `docs/engineering/traspaso-relevo-post-v2.57-auto-16-coste-real-por-ciclo-2026-09-24.md`
>    (estado medido y anclas) y el `audit-pack-v2-57-auto-16-coste-real-por-ciclo-2026-09-24.md`
>    (qué se midió, qué no y por qué).
> 2. Comprueba el estado real del árbol (`git status`, `git log --oneline -5`, la head de Alembic y
>    `_ALEMBIC_HEAD`) **antes** de proponer nada. No des por hecho el estado de este documento.
> 3. Ejecuta las compuertas con **el comando de CI** (`ruff check packages/py apps/api-python --config
>    pyproject.toml`; el `mypy` exacto del YAML; `lint-imports --config packages/py/.importlinter`).
>    En esta máquina los tests se corren con `uv run --no-sync python -m pytest` (`uv run pytest` lo
>    bloquea la directiva de Control de aplicaciones).
> 4. Propón **una** opción de `AUTO-17` con su invariante, su superficie, su migración (¿sí o no?) y su
>    gate; **no la implementes** hasta que el propietario la ratifique.
> 5. Respeta el freeze del §4. Nada de UI, SHORT ni backfill sin ratificación explícita.

---

## 1. Estado en una tabla

| Qué | Dónde / valor |
| --- | --- |
| Árbol | limpio salvo los cambios de la fase (o `main` ya en el tag) |
| Alembic head | `046_fill_reference_mid` |
| Guardia de head | `apps/api-python/tests/test_discovery_evidence_snapshot_pg.py:43` |
| Sello del reparto | `ADAPTIVE_POLICY_VERSION = "auto16-v1"` (`auto_adaptive.py:175`) |
| Sello del gate | `DATA_GATE_POLICY_VERSION = "auto15-v1"` (intacto) |
| Tramo de la fase | `105 passed` (+5 PG) |
| Matriz | `M1…M128` (audit-pack §7) |
| Flag Adaptive | **OFF** |

---

## 2. Dónde está cada cosa (anclas re-medidas sobre el árbol sellado)

- **Migración:** `packages/py/infrastructure/alembic/versions/046_fill_reference_mid.py:38`.
- **Columna ORM:** `tables.py:2248` (`SimFillFinanceContextRow.reference_mid`).
- **Contexto del fill (validación):** `sim_durable_store.py:64` (`usable_reference_mid`) y `:106`.
- **Persistencia:** `simulated_settlement.py:331` → `sim_finance_context.py:61`/`:78`.
- **Lector por ciclo (verificación):** `sim_durable_store.py:300` (memoria) / `:581` (PG).
- **Fricción aplicada (puro):** `applied_cost.py:157` / `:200` / `:244` / `:274`.
- **Evidencia de ciclo:** `cycle_risk.py:145`/`:157` (campos), `:161` (`to_cycle_fields`), `:348`
  (`attach_applied_cost`).
- **Punto único de la alimentación:** `auto_self_evaluation_feed.py:214`.
- **Neto y base:** `auto_self_evaluation.py:130`/`:132` (bases), `:195` (comisión del modelo), `:435`
  (`cycle_r`), `:416`/`:420` (`CycleR`), `:1124` (`_net_r_basis`), `:768`/`:839` (`netRBasis`).
- **Sonda de mutaciones:** `apps/api-python/scripts/v2_44_mutation_audit.py` (bloque `AUTO-16`).

---

## 3. El método (no se improvisa)

- **Ratificación antes de implementar.** El propietario ratifica la opción y el plan; el agente no
  decide alcance.
- **Un paso, un gate.** Cada paso se mide antes de pasar al siguiente.
- **Nada se afirma sin medirlo.** Los documentos citan cifras medidas y declaran lo que **no** se pudo
  medir (y qué límite lo cierra).
- **Los rojos se declaran.** Un delta simétrico con rojos previstos se publica tal cual; un rojo
  re-ejecutado sin declarar es una certificación a medias.
- **Los `*.md` no pasan por `prettier`** (el repo lo declara). `governor.json` sigue sin trackear.

---

## 4. Freeze que hereda `AUTO-17`

No se tocan: el sello de `V2.53`…`V2.57` (`auto13-v1`/`auto14-v1`/`auto15-v1`/`auto16-v1`),
`auto_adaptive_journal.py` (**byte a byte igual**), el contrato de `decision_journal_entries`,
`yahoo_circuit_breaker.py`, `ADAPTIVE_ADVERSE_REGIMES`, los umbrales de rotación, la tabla estado→efecto
del gate ni el gobernador (`v2_43_governor_evidence.py`). **Sin UI**, sin SHORT y sin backfill salvo
ratificación explícita.

---

## 5. Candidatos para `AUTO-17` (declarados, **no decididos**)

Ninguno está elegido: el propietario decide. Todos salen de límites que las fases anteriores dejaron
**escritos**.

1. **`B1` · UI de lo que el journal YA publica.** Dibujar el plan Adaptive tal cual sale hoy
   (`riskMultipliers`, eje de evidencia, pausas, health, `policyVersion`, régimen, y desde `AUTO-16` el
   `costApplied` del ciclo con su medición y el `netRBasis` del agregado). **Sin migración** y sin tocar
   el contrato: es superficie de **lectura** de algo que ya existe y que hoy no tiene pantalla.
2. **`B2` · UI COMPLETA.** Añadir a `B1` las celdas de reparto, el estado del gate, la rampa y la racha
   durable. Exige **descongelar** una proyección (hoy por lista blanca) o una superficie durable nueva:
   es la opción con más superficie de contrato.
3. **`D` · Caducidad declarada de una racha vieja** (cola de `AUTO-15`). Hoy una racha durable de un
   proceso muerto mantiene el gate degradado hasta la primera publicación; no hay TTL y eso es un
   **límite declarado**. Añadir una caducidad **declarada** (no una heurística silenciosa) que reetiquete
   la racha vieja sin inventar salud.
4. **`E` · Comisión REAL en el neto aplicado** (cola de `AUTO-16`). El neto aplicado se completa con la
   comisión **del modelo** porque en SIM la comisión realizada es `0`. Con una tarifa por cuenta/venue
   disponible en el fill, la base pasaría a ser un coste realizado completo — y habría que declarar la
   transición de base.
5. **`F` · El `gap` fuera del neto, declarado.** El modelo declara que `gap_bps` **no** entra en `total`
   (es cola de pérdida, no fricción). Alinear el alcance de la fricción aplicada con el del estimado —o
   declarar la diferencia por ciclo— cerraría la última asimetría entre las dos bases.

**Preguntas abiertas que el autor NO cierra** (del arranque del auditor §9): si la base del neto
(`applied_friction+modelled_commission`) debe entrar en el sello del **gate** además del de reparto; si
un ciclo con **tres** patas debe declarar su composición; y si la fricción aplicada debe publicarse
también como métrica agregada del informe.

---

## 6. Trampas del entorno (Windows / este repo)

- `uv run pytest` → **bloqueado** por Control de aplicaciones (`os error 4551`): usa
  `uv run --no-sync python -m pytest`.
- Los `*.md` **no** pasan por `prettier` (el repo lo declara).
- Los tests PG necesitan PostgreSQL levantado; sin él la sonda usa un DSN *fast-fail*.
- `packages/py/application/tests` y `packages/py/analytics/tests` **no** tienen pase de directorio en
  CI: un fichero de test nuevo **hay que listarlo explícitamente** en `.github/workflows/python-ci.yml`
  y en `.github/workflows/release-tag-ci.yml` o **no corre en ninguna parte**.
