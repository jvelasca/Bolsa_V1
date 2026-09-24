# Auditoría — `v2.62-beta` (`AUTO-20`, material PAPER real + cierre de O1/O2) · 2026-09-24

**Objeto auditado:** tag anotado **`v2.62-beta`** (objeto `25d79b40` → commit `18a4b707`), `1.87.0-beta`
(tagger `jvelasca`; el commit sellado también es el tip de `main`).
**Superficie de revisión:** PR [#71](https://github.com/jvelasca/Bolsa_V1/pull/71) (`OPEN`,
`MERGEABLE`, **30 `pass` + 1 `skipping`**), rama `auto-20-material-paper-real`.
**Rama de auditoría:** `audit-base-v2.62-beta` (creada desde el tag; el árbol auditado **es** el tag).

**Método:** verificación **independiente** contra el tag —no contra el resumen del autor—: compuertas
del CI reales, matriz de mutaciones completa, diff de congelados, byte-identidad del CLI y del replay,
**sondas adversarias propias** (oráculos por propiedades y recomputación independiente, no los
ejemplos del test del autor) y **búsqueda activa de alcanzabilidad** de los defectos declarados.

**Veredicto: 🟢 APROBADO.** Sin hallazgos bloqueantes. Cinco observaciones **P3** declaradas abajo
(ninguna produce un número falso, mueve el reparto ni rompe un contrato sellado).

---

## §1 — Lo que se comprobó (con su evidencia)

| # | Afirmación del sello | Verificación del auditor | Resultado |
|---|---|---|---|
| 1 | El árbol auditado **es** el tag (no hay deriva) | `git rev-parse v2.62-beta^{commit}` == `HEAD` == `18a4b707` | **idéntico** |
| 2 | El tag es **anotado** y de quién | `git for-each-ref` → `tag 25d79b40 tagger=jvelasca` | **anotado** |
| 3 | `1.87.0-beta` declarado en el tag | `git show v2.62-beta:package.json` | `1.87.0-beta` |
| 4 | **O1 cerrado**: la estrategia sin R medible se declara | sonda **S2a**: 40 montajes aleatorios, conjunto declarado vs **oráculo independiente** | **0 mentiras** |
| 5 | Una versión declarada **no** aporta pliegues | sonda S2a (`declared ∩ fold_versions == ∅`) | **0 fallos** |
| 6 | El hueco **parcial** no se declara como hueco | sonda **S2b** | **0 fallos** |
| 7 | Declarar **no** altera lo medido (aditividad de O1) | sonda **S2e**: mismas `folds` con y sin la estrategia fantasma | **idéntico** |
| 8 | Filas sin versión se declaran | sonda **S2c** → `unversioned_cycles` | **declarado** |
| 9 | Estrategia fina ⇒ `skipped`, **nunca** `unmeasured_r` | sonda **S2d** | **0 fallos** |
| 10 | **O2 cerrado**: WFE solo sobre pliegues **emparejados** | sonda **S3a**: **600** montajes contra oráculo independiente | **0 fallos** |
| 11 | Los **cuatro conteos** son exactos y distintos | sonda S3a (`foldCount`/`isFoldCount`/`oosFoldCount`/`pairedFoldCount`) | **0 fallos** |
| 12 | Sin denominador honesto no hay ratio | sonda **S3b**: media emparejada `0` → `None`, `< 0` → `None`, `> 0` → número | **0 fallos** |
| 13 | **Alcanzabilidad de O2** (pregunta del auditor) | sonda **S3c** + sondas dirigidas (`total` 6…90, `min_is=1`, 2 versiones opuestas) | **inalcanzable** (ver H1) |
| 14 | El sello del instrumento sube | sonda **S8b** → `walk_forward_calibration_v2` | **subido** |
| 15 | El walk-forward es **creciente, contiguo, disjunto** | sonda **S1** exhaustiva: todo `total ∈ [0,60]` × `n_folds ∈ {2,3,4,5}` × `min_is ∈ {1,4,8}` × `min_oos ∈ {1,2,4}` | **0 fallos** (3 528 casos) |
| 16 | `folds < 2` es imposible | sonda **S4** sobre `[-10, 10]` | **0 fallos** |
| 17 | La cobertura se **mide** contra un oráculo | sonda **S5**: **400** casos aleatorios (conjunto `usable`, `covered`, `rate`, veredicto, ancho) | **0 fallos** |
| 18 | Determinismo y **orden-invariancia** | sonda **S6**: 3 permutaciones con semilla distinta | **0 fallos** |
| 19 | Sin material ⇒ seis `inconclusive` con `sample = 0` | sonda **S7** | **0 fallos** |
| 20 | Ninguna pregunta con veredicto y `sample < 2` | sonda **S8** | **0 fallos** |
| 21 | El módulo es **puro y read-only** | sonda **S9**: sin imports de I/O + `builtins.open` instrumentado durante la medida | **0 aperturas** |
| 22 | La costura pública es el **MISMO** productor | sonda **S10a/S10b**: `adaptive_instrument_cycles` == `_cycles_with_risk` en 20 montajes; en `__all__` | **idéntico** |
| 23 | El exportador existe, guarda y **declara** | sonda **S10c/S10d** (`--strategy-version` en blanco → `exit 1`; nota de material REAL) | **correcto** |
| 24 | Las 5 costuras del exportador existen con la aridad correcta | revisión estática: `read_cycle_regimes`↔`list_by_decision_ids` (`RegimeFetch`), `cycle_risk_from_reservations`, `list_by_cycle_ids`, `list_for_strategy_version`, `regime_by_cycle` | **casan** |
| 25 | **Aditividad de `AUTO-19A`** | CLI sin `--walk-forward` vs `build_replay_report`, **byte a byte** (**en proceso**, sin la traducción `\n`→`\r\n` de Windows) | **idéntico** |
| 26 | El CLI no cambió en la fase | `auto_replay_battery.py` == `git show v2.61-beta:…`, byte a byte | **idéntico** |
| 27 | El replay conserva **su** contrato sellado | payload sin `--walk-forward` → `method = statistical_oos_v1`, **4** preguntas | **intacto** |
| 28 | **Freeze** respetado | `git diff v2.61-beta v2.62-beta` de `auto_adaptive.py`, `auto_adaptive_data_gate.py`, el worker y el journal | **vacío** |
| 29 | El sello del reparto no se mueve | `ADAPTIVE_POLICY_VERSION = "auto18-v1"` (y `auto15-v1` en el gate) | **quieto** |
| 30 | Sin migración nueva | `git diff` de `apps/api-python/alembic`; head `046_fill_reference_mid` | **vacío** |
| 31 | Los cambios de CI **no** retiran ninguna compuerta | diff de `.github/workflows/**`: **todas** las líneas añadidas empiezan por `#` | **solo comentarios** |
| 32 | Compuertas del CI (locales, comandos del YAML) | `ruff` `All checks passed!`; `lint-imports` **4 kept / 0 broken**; `mypy` **499 ficheros, 0 errores**; `pytest` offline **2799 passed** | **verde** |
| 33 | Mutaciones del tramo | `M165 … M168` | **4/4** muerden, árbol intacto |
| 34 | Matriz completa | `M1 … M168` | **168/168**, cero fragmentos ausentes |
| 35 | CI del sello | `Release tag CI` [`36051082875`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36051082875) → `success` (job `python` del tag **`2772 passed / 35 skipped`**, **+6** sobre `v2.61`; único no-verde: el E2E integrado **opt-in**, `skipped`) | **GREEN a la primera** |
| 36 | El flake del tag anterior no se repite | no hubo re-run ni job rojo | **sin flakes** |

### Evidencia cruda de las sondas

```text
pass S1 walk-forward exhaustivo            (3 528 casos)
pass S2a O1 exacto y sin mentir            (40 montajes vs oráculo)
pass S2b O1 hueco parcial no se declara
pass S2c filas sin version declaradas
pass S2d fina declara skipped y no unmeasured
pass S2e declarar no altera lo medido
pass S3a O2 conteos y WFE emparejado       (600 montajes; 216/600 donde 19B daba otra ratio)
pass S3b WFE sin denominador honesto es None
pass S3c O2 era inalcanzable por el camino publico
pass S4 resolve_calibration_folds acotado
pass S5 cobertura del intervalo (oraculo)  (400 casos)
pass S6 deterministico y orden-invariante
pass S7 sin material: seis inconclusive con muestra 0
pass S8 ningun veredicto sin muestra
pass S8b sello del instrumento
pass S9 modulo puro read-only
pass S10a la costura es publica / S10b es el MISMO productor
pass S10c exportador rechaza version en blanco / S10d declara material real

checks=20 fallos=0
```

---

## §2 — Hallazgos

Ninguno **bloqueante**. Cinco observaciones **P3**, ninguna capaz de publicar un número falso ni de
mover el reparto.

### H1 (P3, **precisión de la narración**) — O2 era **inalcanzable** por el camino público

Los documentos de la fase (y la auditoría de `v2.61-beta` que la originó) presentan O2 como un defecto
**latente alcanzable con material real**. Las sondas dicen algo más preciso: **por el camino público no
se alcanza**. Evidencia:

```text
S3c: O2 era inalcanzable por el camino publico — pass (30 montajes aleatorios)
total 24 -> folds [(1, is=0.8, oos=0.8), (2, is=0.8, oos=0.8)]   agg: 2/2/2/2
total 90 -> folds [(1, is=0.8, oos=0.8), (2, is=0.8, oos=0.8)]   agg: 2/2/2/2
min_is=1, total 6 -> folds [(1, is=0.8, oos=0.8), (2, is=0.8, oos=0.8)]
```

La razón es estructural: (a) `by_version[version]` solo recibe filas con **R medible**; (b) el split
exige `len(test) >= min_oos >= 1`, así que el tramo OOS nunca queda vacío; y (c) la confianza publica
expectancy **incluso con 2 filas de IS**, así que el tramo IS tampoco queda sin medir. Por tanto
`foldCount == isFoldCount == oosFoldCount == pairedFoldCount` **siempre**, y ni el WFE mezclaba dos
muestras ni `foldCount` contaba pliegues que no aportaban. La aritmética **vieja** y la **nueva**
coinciden en todo el material que el instrumento puede producir hoy (el desacuerdo que S3a encuentra —
216/600 — solo aparece en montajes que el camino público **no genera**).

**Consecuencia:** el cierre de O2 es una **defensa por construcción** (correcta y deseable: hace la
mezcla imposible aunque mañana cambie el llamante) y **no** la reparación de un sesgo que el informe
pudiera estar publicando. No hay nada que arreglar en el código; lo que conviene corregir es la
**fuerza de la afirmación** en el relevo y en el `PROJECT_STATE`, para que un lector futuro no crea que
hubo un informe sesgado en circulación.

**Nota relacionada:** `foldCount` **sigue significando algo distinto** que en el espejo
`aggregate_walk_forward_metrics` de `optimize` (que cuenta **solo** los pliegues con OOS). Los conteos
nuevos lo desambiguan, pero un lector que compare los dos informes leerá `foldCount` con dos sentidos.

### H2 (P3, cosmético) — el CLI sigue anunciando el sello `_v1`

`scripts/research/auto_replay_battery.py:3` documenta `walk_forward_calibration_v1`, pero
`CALIBRATION_METHOD` es **`…_v2`** desde esta fase. Es la **única** referencia viva obsoleta (el
`CHANGELOG` y el plan de `v2.61` lo citan como histórico, y eso es correcto). No es inocuo del todo:
el docstring es el `description` del `argparse`, así que **`--help` imprime el sello viejo**.

### H3 (P3, cosmético) — dos sentidos de «positivo» en el mismo payload

`aggregate.positiveOosFoldShare` cuenta `valor >= 0` (fiel al espejo de `optimize`), mientras
`questions[…].metrics.bands[…].positiveShare` cuenta `valor > 0`. Un pliegue exactamente en `0.0`
cuenta como positivo en un sitio y no en el otro. Sin efecto numérico sobre veredictos.

### H4 (P3, robustez) — una versión en blanco se mide como estrategia

El cierre de O1 clasifica con `str(...) or ""` sobre el valor **crudo**: una `strategyVersion` de solo
espacios es **verdadera**, así que no entra en `unversioned_cycles` y se mide como una estrategia sin
nombre. Evidencia:

```text
strategyVersion="   " x30 -> notes ('insufficient_folds:   ',) | folds 2
```

El resto del repo sí normaliza (`cycle_risk.py` usa `_clean`, que hace `strip()` y exige no-vacío). El
hueco **se declara** de todos modos (la nota nombra la fila), por eso es P3 y no más.

### H5 (P3, diagnóstico del exportador) — la saturación de la lectura de reservas no se declara

El worker declara la **saturación** del tope de lectura de reservas
(`len(reservations) >= _V2_CYCLE_RISK_READ_LIMIT` → `warning` explícito, "los ciclos que no cupieron
quedan declarados sin reserva"). El exportador lee con **el mismo tope** (`--limit`, por defecto 2000,
== `_V2_CYCLE_RISK_READ_LIMIT`) y **no** declara la saturación. No hay material que mienta —cada ciclo
sin reserva conserva su hueco por ciclo (`cycle_without_risk`, y `regime_not_found`) en el JSON— pero
se pierde el aviso de que la lectura pudo quedar corta. Añádase que el exportador **no tiene ningún
test** (deuda nº 1 declarada por la propia fase): lo auditado aquí es la **estática** (firmas, guardas,
read-only), no su comportamiento contra PostgreSQL.

### Nota sobre el freeze de `governor.json`

La regla de la casa exige comprobar `governor.json` **byte a byte**. Verificado, con un matiz que se
declara: **`governor.json` no está trackeado** (`git ls-files` vacío), así que es un artefacto de árbol
de trabajo que un tag **no puede** modificar; la comprobación es por tanto sobre el fichero local, no
sobre el contenido sellado.

---

## §3 — Lo que esta auditoría NO cubre

- **No** valida que la estrategia tenga edge ni que la calibración esté bien **en datos reales**: el
  fixture del instrumento es **sintético** (lo declara él mismo) y **no se ha ejecutado el exportador
  contra PostgreSQL**. El camino durable del exportador queda **no ejercitado end-to-end**, que es
  exactamente la deuda nº 1 que la fase declara.
- **No** ejecuta el `Release tag CI` desde cero: se apoya en el run
  [`36051082875`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36051082875) (GREEN) y en las
  compuertas locales con los comandos del YAML.
- **No** comprueba que las lecturas del exportador devuelvan **las mismas filas** que el turno en
  producción: la equivalencia se ha verificado **por construcción** (misma costura, mismos stores, mismo
  tope, mismos parámetros), no por observación con una base real.
- **No** revisa `P(R > 0)`, correlación entre estrategias ni current-regime gating: están **fuera** de
  alcance de `v2.62`.

---

## §4 — Recomendación

1. **Mergear el PR #71** — checks en verde y esta auditoría **no bloquea**.
2. **Corregir H2** (una línea): el `--help` del CLI no debería anunciar un sello que ya no rige. Es
   aditivo y no requiere re-sello.
3. **Atacar la deuda nº 1 de verdad**: ejercitar `paper_cycles_export.py` end-to-end con un fixture PG
   que siembre fills y reservas. Es lo único que hoy separa "cableado" de "probado".
4. **El paso operativo** que da sentido a la fase: correr `paper_cycles_export.py` →
   `auto_replay_battery.py --walk-forward` sobre material PAPER real y publicar el primer informe
   `walk_forward_calibration_v2` **no sintético**. Sin él, la calibración sigue midiendo el instrumento.
5. Si en esa fase se decide cerrar H1, basta con **ajustar la redacción** del relevo y del
   `PROJECT_STATE`: el código de O2 es correcto tal y como está.
