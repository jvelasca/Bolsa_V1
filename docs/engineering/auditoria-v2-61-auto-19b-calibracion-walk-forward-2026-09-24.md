# Auditoría — `v2.61-beta` (`AUTO-19B`, calibración del intervalo + walk-forward) · 2026-09-24

**Objeto auditado:** tag anotado **`v2.61-beta`** (objeto `2f64dc1c` → commit `f9f64799`), `1.86.0-beta`.
**Superficie de revisión:** PR [#70](https://github.com/jvelasca/Bolsa_V1/pull/70) (`OPEN`, `MERGEABLE`,
**9/9 checks `pass`**), base `audit-base-v2.60-beta` (`63a02e34`).

**Método:** verificación **independiente** contra el tag —no contra el resumen del autor—: compuertas
del CI reales, matriz de mutaciones del tramo, diff de congelados, byte-identidad del CLI, y **sondas
adversarias propias** (oráculos por propiedades, no ejemplos del test del autor).

**Veredicto: 🟢 APROBADO.** Sin hallazgos bloqueantes. Dos observaciones **P3** declaradas abajo
(ninguna produce un `supported` falso ni mueve el reparto).

---

## §1 — Lo que se comprobó (con su evidencia)

| # | Afirmación del sello | Verificación del auditor | Resultado |
|---|---|---|---|
| 1 | El árbol auditado **es** el tag (no hay deriva) | `git diff v2.61-beta -- <ficheros de fase>` | **vacío** (idéntico) |
| 2 | `1.86.0-beta` declarado en el tag | `git show v2.61-beta:package.json` | `1.86.0-beta` |
| 3 | El walk-forward **no se contamina** y **crece** | sonda S1: propiedades sobre **todos** los `total ∈ [0,60]` × `n_folds ∈ {2,3,4,5}` (IS=prefijo, OOS=contiguo, disjuntos, crecientes, mínimos) | **0 fallos** |
| 4 | La cobertura **se mide**, no se afirma | sonda S2: **400** casos aleatorios contra un oráculo independiente | **0 fallos** |
| 5 | El signo del EDGE se calibra con muestra | sonda S3: **300** casos aleatorios contra oráculo | **0 fallos** |
| 6 | Sin intervalo no hay cobertura | sonda S2 (celdas sin intervalo excluidas de `usable`) | **0 fallos** |
| 7 | `folds < 2` es imposible | sonda S4: `resolve_calibration_folds` sobre `[-10, 10]` | **0 fallos** |
| 8 | Determinismo y **orden-invariancia** | sonda S5: 3 permutaciones con semilla distinta | **0 fallos** |
| 9 | Sin material ⇒ `inconclusive` y `sample = 0` | sonda S6 | **0 fallos** |
| 10 | Ninguna pregunta con veredicto y `sample < 2` | sonda S8 sobre el fixture | **0 fallos** |
| 11 | La lectura es **aditiva** (19A no cambia) | CLI sin `--walk-forward` vs `build_replay_report`, byte a byte | **idéntico** (`True`) |
| 12 | El descarte de estrategias sin pliegues se **declara** | `insufficient_folds` / `skipped_strategy` sobre el fixture | **declarado** |
| 13 | **Freeze** respetado | `git diff v2.60-beta v2.61-beta` de los 7 congelados | **vacío** |
| 14 | El sello del reparto no se mueve | `auto_adaptive.py` / `auto_adaptive_data_gate.py` | `auto18-v1` / `auto15-v1` |
| 15 | Sin migración nueva | diff de `alembic/versions`; guardia `_ALEMBIC_HEAD` | **vacío**; `046_fill_reference_mid` |
| 16 | Compuertas del CI | `ruff` (All checks passed), `lint-imports` (4 kept / 0 broken), `mypy` (499 ficheros, 0 errores) | **verde** |
| 17 | Mutaciones del tramo | `M159 … M164` | **6/6** muerden, árbol intacto |
| 18 | Matriz completa | `M1 … M164` (en el sello) | **164/164**, cero fragmentos ausentes |

## §2 — Hallazgos

Ninguno **bloqueante**. Dos observaciones **P3** (divulgación/robustez), ambas **heredadas o latentes**,
ninguna capaz de publicar un `supported` falso:

### O1 (P3, **heredada de AUTO-19A**) — una estrategia sin R medido desaparece sin declararse

Si TODOS los ciclos de una `strategyVersion` existen pero **ninguno** tiene R medible, la estrategia no
entra en el agrupado y **no deja nota**. Evidencia:

```text
30 ciclos de "ghost" con pnl sin risk_amount  ->  folds: 0 | notes: ()
```

`AUTO-19B` **replica** el comportamiento de `build_replay_report` (línea 606 del replay sellado en
`v2.60-beta`), así que **no es una regresión de esta fase**: es una limitación compartida. Choca con la
filosofía del repo («lo que no se midió se declara»), pero solo muerde cuando hay material presente que
no es medible —y, en ese caso, el informe sale **vacío y honesto**, no con un veredicto inventado—.

### O2 (P3, **latente**) — `aggregate.foldCount` cuenta pliegues que no aportan a la media OOS

`foldCount` cuenta TODOS los pliegues, mientras `meanOosExpectancyR` promedia solo los que tienen OOS.
Un pliegue con filas OOS pero **sin R medible** deja `oosExpectancyR = None` y descuadra el conteo.
Evidencia:

```text
folds = [fold1(OOS=1.0, IS=2.0), fold2(OOS=None, IS=2.0)]
foldCount: 2 | meanOosExpectancyR: 1.0 | meanIsExpectancyR: 2.0   -> foldCount (2) != pliegues con OOS (1)
```

Es el hallazgo que **arreglaría primero**: `walkForwardEfficiency` (= media OOS / media IS) podría
mezclar dos conjuntos de pliegues distintos. En el fixture del sello **no ocurre** (`foldCount = 9 =
pliegues con OOS`), pero es alcanzable con material real. No altera ningún otro veredicto.

### O3 (P3, cosmético) — la `note` del fixture mezcla español e inglés

`"SYNTHETIC deterministic fixture for AUTO-19B ...: mide el instrumento, not durable production
material"`. Sin efecto funcional.

## §3 — Flake del tag (declarado, verificado como ajeno)

`test_simulated_finance_pg.py::test_finance_auto_day_materializes_executetrade_exactly_once` falló con
`AssertionError: RETRY` en la **primera** pasada del `Release tag CI` y **pasó al re-ejecutar los jobs
fallidos**. Es un test de integración **PG** (el `RETRY` es un timeout de un bucle de concurrencia),
**ajeno** a esta fase: `AUTO-19B` solo añade un módulo puro read-only, su test, el fixture, el CLI y las
mutaciones, y **ninguno** de esos ficheros participa en ese test.

## §4 — Lo que esta auditoría NO cubre

- **No** valida que la estrategia tenga edge ni que el intervalo esté bien calibrado **en datos
  reales**: el fixture es **sintético**. La cobertura publicada es la del material que se le dé.
- **No** ejecuta el `Release tag CI` desde cero: se apoya en el run
  [`36039143456`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36039143456) (GREEN) y en las
  compuertas locales con los comandos del YAML.
- **No** revisa `P(R > 0)`, correlación entre estrategias ni current-regime gating: están **fuera** de
  alcance de `v2.61`.

## §5 — Recomendación

1. **Mergear el PR #70** (checks verdes; la auditoría no bloquea).
2. **Cerrar O2** —y, de paso, declarar O1— en la siguiente fase de medición, preferiblemente **al
   cablear el material PAPER real**, que es cuando O1 y O2 dejan de ser latentes. No requiere re-sello
   de `v2.61-beta`: es aditivo y read-only.
3. Mantener el orden del repo: la siguiente fase (`PAPER` real) arranca sobre el commit sellado.
