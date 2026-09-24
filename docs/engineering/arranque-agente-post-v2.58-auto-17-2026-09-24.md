# Arranque del agente — post `v2.58-beta` (`AUTO-17` cerrada) · 2026-09-24

**Rama `main`** en fast-forward · **Tag `v2.58-beta`** · **`1.83.0-beta`** · **Fase anterior cerrada:**
`V2.58` / `AUTO-17` «Integridad de la población de medida».

---

## 0. El prompt para arrancar (cópialo tal cual)

> Trabajas en `Bolsa_V1` (repo del propietario). **No improvises el método**: el repo tiene un
> protocolo y se sigue. Antes de tocar nada:
>
> 1. Lee `docs/engineering/traspaso-relevo-post-v2.58-auto-17-integridad-poblacion-medida-2026-09-24.md`
>    (estado medido y anclas) y el `audit-pack-v2-58-auto-17-integridad-poblacion-medida-2026-09-24.md`
>    (qué se midió, qué no y por qué).
> 2. Comprueba el estado real del árbol (`git status`, `git log --oneline -5`, la head de Alembic y
>    `_ALEMBIC_HEAD`) **antes** de proponer nada. No des por hecho el estado de este documento.
> 3. Ejecuta las compuertas con **el comando de CI** (`ruff check packages/py apps/api-python --config
>    pyproject.toml`; el `mypy` exacto del YAML; `lint-imports --config packages/py/.importlinter`).
>    En esta máquina los tests se corren con `uv run --no-sync python -m pytest` (`uv run pytest` lo
>    bloquea la directiva de Control de aplicaciones).
> 4. Propón **una** opción de `AUTO-18` con su invariante, su superficie, su migración (¿sí o no?) y su
>    gate; **no la implementes** hasta que el propietario la ratifique.
> 5. Respeta el freeze del §4. Nada de UI, SHORT ni backfill sin ratificación explícita.

---

## 1. Estado en una tabla

| Qué | Dónde / valor |
| --- | --- |
| Árbol | limpio salvo los cambios de la fase (o `main` ya en el tag) |
| Alembic head | `046_fill_reference_mid` (sin cambio: AUTO-17 no migra) |
| Guardia de head | `apps/api-python/tests/test_discovery_evidence_snapshot_pg.py:43` |
| Sello del reparto | `ADAPTIVE_POLICY_VERSION = "auto17-v1"` (`auto_adaptive.py:188`) |
| Sello del gate | `DATA_GATE_POLICY_VERSION = "auto15-v1"` (intacto) |
| Tramo de la fase | `245 passed` |
| Matriz | `M1…M138` (audit-pack §6) |
| Flag Adaptive | **OFF** |

---

## 2. Dónde está cada cosa (anclas re-medidas sobre el árbol sellado)

- **Round-trip cuantitativo:** `applied_cost.py:121` (cantidad), `:175` (`applied_leg`), `:222`
  (`_quantity_balanced`), `:266`/`:267` (agregado), `:340` (cierre).
- **Cierre una sola vez:** `auto_self_evaluation_feed.py:246` (`_cycles_with_risk`).
- **Series por base:** `auto_self_evaluation.py:689` (`NetRBasisSeries`), `:755`/`:853` (campo),
  `:1156` (`_net_r_series`), `:1180` (`_basis_of`), `:1192` (`_pooled_net_expectancy`).
- **Confianza:** `auto_adaptive_confidence.py:268` (`_basis_transition`), `:290`/`:313` (`_decay` gated),
  `:355`/`:358`, `:403`/`:407` (campos).
- **Reparto:** `auto_adaptive.py:967` (`_net_basis_comparable`), `:281` (nota), `:422`/`:423` (health),
  `:188` (sello).
- **Migración (intacta):** `packages/py/infrastructure/alembic/versions/046_fill_reference_mid.py:38`.
- **Sonda de mutaciones:** `apps/api-python/scripts/v2_44_mutation_audit.py` (bloque `AUTO-17`).

---

## 3. El método (no se improvisa)

- **Ratificación antes de implementar.** El propietario ratifica la opción y el plan; el agente no decide
  alcance.
- **Un paso, un gate.** Cada paso se mide antes de pasar al siguiente.
- **Nada se afirma sin medirlo.** Los documentos citan cifras medidas y declaran lo que **no** se pudo
  medir (y qué límite lo cierra).
- **Los rojos se declaran.** Un delta simétrico con rojos previstos se publica tal cual; un rojo
  re-ejecutado sin declarar es una certificación a medias.
- **Los `*.md` no pasan por `prettier`** (el repo lo declara). `governor.json` sigue sin trackear.

---

## 4. Freeze que hereda `AUTO-18`

No se tocan: el sello de `V2.53`…`V2.58` (`auto13-v1`…`auto17-v1`), `auto_adaptive_journal.py` (**byte a
byte igual**), el contrato de `decision_journal_entries`, `yahoo_circuit_breaker.py`,
`ADAPTIVE_ADVERSE_REGIMES`, los umbrales de rotación, la tabla estado→efecto del gate ni el gobernador
(`v2_43_governor_evidence.py`). **Sin UI**, sin SHORT y sin backfill salvo ratificación explícita.

---

## 5. Candidatos para `AUTO-18` (declarados, **no decididos**)

Ninguno está elegido: el propietario decide. Todos salen de límites que las fases anteriores dejaron
**escritos**.

1. **`B1` · UI de lo que el journal YA publica.** Dibujar el plan Adaptive tal cual sale hoy
   (`riskMultipliers`, eje de evidencia, pausas, health, `policyVersion`, régimen, y desde `AUTO-16`/`17`
   el `costApplied` del ciclo con su medición, el `netRBasis` del agregado, las **series por base** y la
   `basisTransition`). **Sin migración** y sin tocar el contrato: es superficie de **lectura** de algo que
   ya existe y que hoy no tiene pantalla.
2. **`B2` · UI COMPLETA.** Añadir a `B1` las celdas de reparto, el estado del gate, la rampa y la racha
   durable. Exige **descongelar** una proyección (hoy por lista blanca) o una superficie durable nueva: es
   la opción con más superficie de contrato.
3. **`D` · Caducidad declarada de una racha vieja** (cola de `AUTO-15`). Hoy una racha durable de un
   proceso muerto mantiene el gate degradado hasta la primera publicación; no hay TTL y eso es un
   **límite declarado**.
4. **`E` · Comisión REAL en el neto aplicado** (cola de `AUTO-16`). El neto aplicado se completa con la
   comisión **del modelo** porque en SIM la comisión realizada es `0`. Con una tarifa por cuenta/venue
   disponible en el fill, la base pasaría a ser un coste realizado completo — y habría que declarar la
   transición de base (que `AUTO-17` ya sabe detectar).
5. **`F` · El `gap` fuera del neto, declarado.** El modelo declara que `gap_bps` **no** entra en `total`
   (es cola de pérdida, no fricción). Alinear el alcance de la fricción aplicada con el del estimado —o
   declarar la diferencia por ciclo— cerraría la última asimetría entre las dos bases.

**Preguntas abiertas que el autor NO cierra** (del arranque del auditor §9): si el pooled `None` de una
población mixta debería ser un **error de tipo** en vez de un valor; si la **tolerancia del balance** debe
publicarse en el informe; si un ciclo de **tres o más patas** debe publicar su composición; y la
**caducidad** de una racha durable vieja.

---

## 6. Trampas del entorno (Windows / este repo)

- `uv run pytest` → **bloqueado** por Control de aplicaciones (`os error 4551`): usa
  `uv run --no-sync python -m pytest`.
- Los `*.md` **no** pasan por `prettier` (el repo lo declara).
- Los tests PG necesitan PostgreSQL levantado; sin él la sonda usa un DSN *fast-fail*.
- `packages/py/application/tests` y `packages/py/analytics/tests` **no** tienen pase de directorio en CI:
  un fichero de test nuevo **hay que listarlo explícitamente** en `.github/workflows/python-ci.yml` y en
  `.github/workflows/release-tag-ci.yml` o **no corre en ninguna parte**.
