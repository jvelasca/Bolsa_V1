# Dictamen de auditoría C-4 — certificación PostgreSQL real

**Fecha:** 2026-10-26 · **Rama:** `audit/c1-c4-integrity-fold-2026-10-25` ·
**Naturaleza:** dictamen de auditoría **read-only** (no modifica ramas, PR, tags ni el pin PAPER;
no abre `main`).

Este documento registra el **cierre** de C-4 (coste ambiguo de una adopción) respecto a la
carencia de integración PostgreSQL identificada en la auditoría anterior del lote C-1–C-4.
La evidencia técnica cruda vive en
[`evidencia-c4-coste-ambiguo-pg-2026-10-26.md`](./evidencia-c4-coste-ambiguo-pg-2026-10-26.md);
aquí se fija el dictamen y, sobre todo, **qué SHA certifica el CI y qué SHA es sólo el commit
documental posterior**.

## 1. Dictamen

| Elemento | Valor |
| --- | --- |
| Rama | `audit/c1-c4-integrity-fold-2026-10-25` |
| SHA certificado por CI | **`b3456897`** |
| Evidencia documental posterior | **`6a9f7cab`** (no es el SHA que certifica el run) |
| Python CI | Run [`40287111793`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40287111793) — **5/5 jobs verdes** |
| Prueba PostgreSQL C-4 | **`3 passed in 1.79s`**, con guarda anti-skip ejecutada |
| Alcance | Los tres escenarios de coste ambiguo y la recuperación de plan durable |
| Cambios excluidos | Motor, migraciones, `package.json`, PR [#76](https://github.com/jvelasca/Bolsa_V1/pull/76) y tag `v2.88.161-beta` |

Los cinco jobs del run, todos en `success` sobre `headSha = b3456897`:

- `quality`
- `lifecycle-pg`
- `auto-v2-durable-pg`
- `paper-forward-pg`
- `grammar-discovery-pg`

Dentro de `auto-v2-durable-pg` aparecen como ejecutados y satisfactorios los dos pasos propios:

- `Pytest C-4 coste ambiguo PG (fail if skipped)` ⇒ `3 passed in 1.79s`.
- `Fail on skipped C-4 coste ambiguo PG (no skip silencioso)` ⇒ `success`.

## 2. Por qué esta prueba vale más que una prueba unitaria con dobles

La ambigüedad de coste **no existe** en un doble: existe porque hay más de una fila viva del
mismo símbolo en `sim_auto_positions` (dos motores) y el coste medio de la cuenta deja de
identificar a ESTA fila. La prueba siembra **estados persistidos** (dos filas vivas del mismo
símbolo, el fill `APPLIED` con su contexto financiero y, según el escenario, el espejo y/o el
`position_state`) y verifica los resultados a través del **almacén PostgreSQL** y del **lector
canónico de producción**, no de una proyección de prueba.

Escenarios cubiertos:

| Escenario | Hecho sembrado | Resultado exigido |
| --- | --- | --- |
| 1. Libro ambiguo **con** espejo | `entry_price=10.4`, libro `10.3335`, dos motores | `projection_ambiguous_ledger`; adopción declarada `RECONCILIATION_REQUIRED` con stop por debajo del mercado; journal con `entrySource` y `source=reconstructed` |
| 2. Libro ambiguo **sin** espejo | `entry_price=NULL`, libro `10.3335`, dos motores | `ledger_ambiguous`; no se adopta, hueco declarado con motivo propio (no `cost_basis_missing`); la fila durable queda con `entry_price NULL` y cantidad intacta |
| 3. Plan durable | `position_state` verificado + coste ambiguo | la geometría del plan prevalece (`PROTECTED`, mismo `tradePlanId`/stop); no se declara hueco de coste; el plan se consume una sola vez |

La **guarda anti-skip** aborda dos riesgos distintos, y por eso hay dos pasos y no uno:

1. Que el test se **omita** accidentalmente (fichero borrado o renombrado): el `--ignore` del job
   offline lo dejaría fuera en mudo; el paso propio hace que pytest salga con **exit 4** y rompa.
2. Que aparezca como **skipped** cuando la integración es obligatoria: sin PostgreSQL real el
   `pytest.skip` daría un verde sin medir nada; `C4_AMBIGUOUS_COST_PG_REQUIRED=1` convierte el
   skip en `AssertionError` y la guarda de log lo vuelve a comprobar.

## 3. Comprobación directa en GitHub

Consultados el commit `b3456897`, el run `40287111793` y el documento de evidencia de `6a9f7cab`.
La consulta de los jobs confirma los cinco resultados satisfactorios. En `auto-v2-durable-pg`
aparecen como ejecutados y satisfactorios tanto el paso específico de C-4 como la guarda
anti-skip. El documento de evidencia publicado en `6a9f7cab` conserva también la secuencia de
fallos de Ruff y sus correcciones, sin ocultarlos.

Genealogía del lote (cada SHA con su propio dictamen de CI):

| SHA | Contenido | Python CI |
| --- | --- | --- |
| `a1f8af71` | C-1..C-4 | **rojo** en `quality` por Ruff `I001` |
| `2b9d258d` | ordena imports con la config raíz | verde |
| `712c2529` | prueba PG de C-4 + cableado | **rojo** en `quality` por `I001` (`auto-v2-durable-pg` ya verde) |
| `b3456897` | ordena imports (sólo lint) | **verde 5/5** — run `40287111793` |
| `6a9f7cab` | evidencia documental (1 fichero) | **no** es el SHA certificado por ese run |

## 4. Cierre y estados diferenciados

C-4 queda **cerrado** respecto a la carencia de integración PostgreSQL identificada en la
auditoría anterior. Los tres escenarios tienen una prueba dedicada contra PostgreSQL real, y el
CI impide que la ausencia o el salto silencioso de esa prueba produzcan un resultado verde.

Quedan diferenciados estos estados:

- **C-1–C-4:** lote validado con la evidencia y las pruebas descritas.
- **C-4:** integración específica añadida y certificada en el SHA `b3456897`.
- **`6a9f7cab`:** documentación de la evidencia; **no** es el SHA que certifica ese run.
- **Rentabilidad y operativa AUTO:** **no** quedan certificadas por estas pruebas. La integración
  verifica integridad y comportamiento ante estados ambiguos, **no** que las estrategias sean
  rentables ni que la operativa esté lista para dinero real.

No se han modificado ramas, PR, tags ni archivos fuera de este registro documental. C-4 **no se
reabre** salvo que aparezca evidencia contradictoria.

## 5. Siguiente paso declarado (no ejecutado aquí)

Auditar el siguiente riesgo funcional: la **operativa PAPER real de AUTO multi-día** (readopción
de posiciones entre sesiones, parada dura durable y ventana de evidencia). Esta prueba **no**
acredita ese riesgo: certifica integridad ante estados ambiguos, con operativa PAPER virtual y
AUTO **OFF**. Se declara como siguiente objeto de auditoría, sin reabrir C-4.

## 6. Reproducción

```bash
gh run view 40287111793 --json headSha,conclusion,workflowName
gh run view --job <auto-v2-durable-pg job id> --log | grep -E "C-4|passed"
git log --oneline -5 b3456897
rg -n "C4_AMBIGUOUS|auto_v88_161_c4" .github/workflows/python-ci.yml .github/workflows/release-tag-ci.yml
```

Cableado verificado en el árbol de la rama:

- [`.github/workflows/python-ci.yml`](../../.github/workflows/python-ci.yml) — gate en el job
  `auto-v2-durable-pg`, `--ignore` del fichero en el job offline y paso propio + guarda
  (`Pytest C-4 ...` / `Fail on skipped C-4 ...`).
- [`.github/workflows/release-tag-ci.yml`](../../.github/workflows/release-tag-ci.yml) — mismo
  gate en `lifecycle-pg` del sello y `--ignore` correspondiente.
- [`apps/api-python/tests/test_auto_v88_161_c4_ambiguous_cost_pg.py`](../../apps/api-python/tests/test_auto_v88_161_c4_ambiguous_cost_pg.py)
  — los tres escenarios y `_require_or_skip`.
