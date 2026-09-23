# Arranque del auditor — `v2.55-beta` (AUTO-14 · Reparto por CELDA de régimen)

**Fecha:** 2026-09-23 · **Ref a atacar:** tag **`v2.55-beta`** (`1.80.0-beta`) ·
**Pack que manda:** [`audit-pack-v2-55-auto-14-reparto-por-celda-de-regimen-2026-09-23.md`](./audit-pack-v2-55-auto-14-reparto-por-celda-de-regimen-2026-09-23.md).
Si algo de este arranque contradice al pack, **manda el pack**. El plan de fase (ratificado) es
[`plan-v2-55-auto-14-reparto-por-celda-de-regimen-2026-09-23.md`](./plan-v2-55-auto-14-reparto-por-celda-de-regimen-2026-09-23.md)
y el relevo cerrado
[`traspaso-relevo-post-v2.55-auto-14-reparto-por-celda-de-regimen-2026-09-23.md`](./traspaso-relevo-post-v2.55-auto-14-reparto-por-celda-de-regimen-2026-09-23.md).

Las `ruta:línea` de este documento están **verificadas en el árbol el 2026-09-23**. Cada afirmación trae
**el comando exacto** para medirla. Este documento existe para que no gastes presupuesto redisculpiendo lo
ya medido.

**Contexto del sello:** la fase entera viaja en **fast-forward** sobre `6fad572d` (los arranques de
`v2.54` en `main`, que contiene `54a3b86a` —el commit sellado de `AUTO-13`—), **sin merge commit** y sin
rama de fase. **Sin migración** (Alembic head sigue en `044_auto_cycle_trace`).

---

## 0. Si solo tienes una hora

1. **§2 — el guard de celda** (es *el* diseño de la fase: qué celda puede afinar y cuál **no**).
2. **§3 — el peso vs la composición** (¿la celda puede añadir o quitar competidores? **no debe**).
3. **§4/§5 — el shrink con la banda de la celda y la declaración** (¿se declara el hueco? ¿el frame
   sellado y el journal quedan igual?).
4. **§1 — el invariante**: el reparto no puede mejorar su peso con una celda que **no** se ha medido.

---

## 1. El invariante (ataca contra él, no contra el estilo)

**El reparto no puede mejorar su peso con una celda que no se ha medido.** Una celda sin muestra
suficiente, una celda ausente, un R **neto** no medido, una celda medida **no positiva** o un régimen
**ilegible** **no mueven el peso**: esa versión cae al **global** de su fila y el hueco se **declara**.

| Punto | `ruta:línea` |
| --- | --- |
| Helper puro de selección | `packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive.py:871` (`regime_cell_for`) |
| Normalización **única** (caja + espacios, **sin** traducir) | `auto_adaptive.py:860` (`_cell_key`) |
| Guard: régimen ilegible | `auto_adaptive.py:888` (`cell_regime_absent`) |
| Guard: celda ausente / no decisiva / net no medido / no positiva | `auto_adaptive.py:899` / `:900` / `:901` / `:903` |
| Vocabulario de motivos (propio del reparto) | `auto_adaptive.py:242-256` |
| Sello de política | `auto_adaptive.py:168` (`auto14-v1`) |

**Preguntas incómodas.**

- ¿Puede `regime_cell_for` devolver una celda **sin** haber comprobado **todos** los guards? Lee el orden
  y busca un camino que devuelva `(celda, None)` con un guard saltado.
- La normalización es **solo de forma**: `TREND_UP` ≠ `RANGE`. ¿Puede un régimen **operativo**
  (`BULL_TREND`) llegar aquí sin traducir y casar con una celda guardada en el eje canónico? Si casa,
  ¿es correcto o es una celda **de otro eje**?
- **Los umbrales están declarados, no calibrados** (`min_trades`, `confidence_prior = 20`,
  `severe_decay_factor = 0.5`): pregunta abierta (§9), no defecto.

---

## 2. La selección de celda: un helper puro y declarativo

`regime_cell_for(cells, strategy_version, regime) -> (celda | None, motivo | None)` es el **único** sitio
donde se elige celda y devuelve **siempre** el par. Los cinco huecos, en orden:

| Hueco | Motivo | Línea |
| --- | --- | --- |
| régimen `None`/`""`/`UNKNOWN` | `cell_regime_absent` | `auto_adaptive.py:888` |
| no hay celda para `(versión, régimen)` | `cell_not_found` | `auto_adaptive.py:899` |
| la celda existe pero no es `decisive` | `cell_not_decisive` | `auto_adaptive.py:900` |
| R neto no `COMPLETE` (`PARTIAL`) | `cell_net_unmeasured` | `auto_adaptive.py:901` |
| R neto medido **no positivo** | `cell_not_positive` | `auto_adaptive.py:903` |

**Preguntas incómodas.**

- ¿Se elige **otra** celda cuando la del régimen no vale? (No debe: la lección del §20/`M81`.) Búscalo en
  el `next(...)` y en la mutación `M103`/`M104`.
- ¿Se **hereda** la celda de otro ciclo o de otra versión? El helper filtra por `strategy_version` **y**
  régimen en la **misma** condición: si quitas una, ¿muerde algún test?
- `decisive` **no** cubre el R neto (depende de un coste **estimado**): ¿hay algún camino que trate una
  celda `PARTIAL` como medida? (`M105` es exactamente eso.)

---

## 3. El reparto: la celda afina el **peso**, nunca la **composición**

`_allocation_weights(...)` (`auto_adaptive.py:923`) elige **eje** y **grupo** con la **fila**:

- El **eje es del grupo**, nunca de la fila: el R neto solo se adopta si cubre a **todo** el grupo que
  compite (`net_r.keys() == currency.keys()`, `:979`). Mezclar moneda y R dentro del grupo es aritmética
  sin sentido (**M102**).
- La celda se consulta **solo para quien YA competía** (`:965-976`): cambia el **número**, nunca la
  pertenencia al numerador.
- Con el eje de **moneda** no se aplica celda y **todas** las que compiten declaran
  `cell_axis_without_cell` (`:986-993`).
- Sigue **suma-preservado**, acotado a `[0, 1]` y **sin ceros** (`:1126-1141`), y la rampa de `AUTO-13`
  sigue siendo **techo** (`min`, `:1141-1148`), después del reparto.

**Preguntas incómodas.**

- ¿Puede una celda **meter** a una versión que la fila no admitía (o **sacar** a una que sí)? Es el fallo
  más caro de la fase: la composición debe ser **byte-idéntica** con y sin celdas. Los tests y `M99`/
  `M101` lo atacan, pero **una forma nueva es un hallazgo legítimo**.
- Con el eje de moneda, ¿el reparto sigue siendo **exactamente** el de `v2.54`? Compáralo con
  `by_regime=()`.
- ¿La rampa puede **ensanchar** con una celda presente? (`M107` esquiva el `min` cuando el peso vino de
  celda: si pasa, el techo de `AUTO-13` deja de valer.)

---

## 4. El encogimiento (`AUTO-12`) se mide con la banda de la **celda**

`_cell_confidence(...)` (`auto_adaptive.py:999`) busca el `RegimeConfidence` de la celda en
`StrategyConfidence.by_regime` y el factor de encogimiento se calcula con **su** `effective_n`/`decay`
cuando el peso salió de la celda (`:1113-1119`).

**Preguntas incómodas.**

- ¿Qué pasa si **no** hay banda de celda pero el peso **sí** salió de ella? ¿Cae al global (declarado) o
  se inventa un factor?
- ¿Un `effective_n = 0` en la celda puede producir un peso **fabricado**? (Debería caer al hueco: el
  encogimiento **redistribuye**, nunca elimina.)
- `_cell_confidence` casa por `_cell_key` **solo** con el régimen: ¿puede elegir la banda de **otra**
  celda de la misma estrategia? (Compáralo con `regime_cell_for`: el reparto filtra por versión **y**
  régimen.) **Este es el punto más fino de la fase** y el que más se parece a una celda de otro eje.

---

## 5. La declaración y el sello (medir ≠ publicar de más)

- `AllocationPlan` (`auto_adaptive.py:504`) gana `cell_axis`, `cell_used`, `cell_fallback` (`:525-534`)
  con lecturas propias (`cell_for` `:539`, `cell_note_for` `:542`) y **`as_dict()` intacto** (`:544-552`):
  el frame sellado por `AUTO-13` sigue publicando **solo** `riskMultipliers` + `evidenceAxis`.
- La base de celda se declara en el **nivel del plan**: `AdaptivePlan.as_dict()['allocationCells']`
  (`:750-754`), junto a `regimeUndetermined` y `shrinkage`.
- El **contrato durable** no cambia: `_ALLOCATION_KEYS = ("riskMultipliers", "evidenceAxis")`
  (`packages/py/application/src/bolsa_application/auto_adaptive_journal.py:58`), así que
  `allocationCells` **nunca** llega al journal.
- El worker lo declara en el log (`apps/api-python/src/bolsa_api/background/auto_simulation_worker.py:3167`),
  **sin cambio de firma**.
- **Sello `auto14-v1`** (`auto_adaptive.py:168`) y su **consecuencia declarada**: el mismatch de política
  marca las filas `auto13-v1` como `STALE` **un tick**, se cura con la primera escritura, **no** resetea
  el contador y **no** se ejecuta con el flag OFF. Se relaja **nada** de `AUTO-11`.

**Preguntas incómodas.**

- ¿El `STALE` de un tick puede **tumbar** una decisión de riesgo? (No debe: es un gate de **evidencia**;
  el gobernador y el kill switch no lo miran.)
- ¿La declaración de celda es **completa**? Si una versión compite por celda pero **no** aparece en
  `cell_used` **ni** en `cell_fallback`, hay un hueco **silenciado**. Búscalo con un caso donde la celda
  no se encuentre.

---

## 6. Mutaciones que YA se midieron (no las redisculpas)

`M99`…`M107` (**9**), todas mordiendo, con la matriz **completa** (`M1…M107`) en **`107/107`**, `0` en
`NADA` y el árbol intacto. El detalle, en el pack (§7). Las que más se acercan a un hallazgo real son:

| # | Qué rompe | Dónde mira el auditor |
| --- | --- | --- |
| `M99` | el guard `decisive` de la celda | una celda **fina** movería el peso |
| `M102` | la cobertura del grupo en el eje R | **ejes mezclados** por fila |
| `M106` | el shrink usa la banda de la **fila** | la base que la celda **no** tiene |
| `M107` | la rampa deja de topar el peso de celda | `AUTO-13` **anulada** por la puerta de atrás |

---

## 7. Comandos exactos (no los reinventes)

```bash
# Estático (los de CI, no rutas sueltas)
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
             packages/py/application/src apps/api-python/src --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter

# El gobernador NO se movió: diff VACÍO y el script exit 0
git diff -- apps/api-python/scripts/v2_43_governor_evidence.py
uv run --no-sync python apps/api-python/scripts/v2_43_governor_evidence.py; echo "exit=$?"

# El contrato durable NO se movió: diff VACÍO
git diff -- packages/py/application/src/bolsa_application/auto_adaptive_journal.py

# Sin migración: el head no se movió
uv run alembic -c packages/py/infrastructure/alembic.ini heads      # 044_auto_cycle_trace

# El tramo de la fase (unit + las tres costuras): 119 passed
# (con DATABASE_URL a un puerto cerrado y PGCONNECT_TIMEOUT=5 tarda segundos)
uv run pytest packages/py/analytics/tests/test_auto_adaptive.py \
              apps/api-python/tests/test_auto_v53_auto12_confidence_seam.py \
              apps/api-python/tests/test_auto_v54_auto13_recovery_seam.py \
              apps/api-python/tests/test_auto_v55_auto14_regime_cell_allocation_seam.py -q

# La matriz de mutaciones (mide, restaura byte a byte y verifica la huella del árbol)
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py M99 M100 M101
```

**Al correr la matriz:** interrumpir la tarea **no mata** al hijo en Python, y el script reescribe ficheros
en bucle. Comprueba procesos y `git status` **antes** de dar la corrida por cerrada; si queda un mutante,
restaura con `git checkout -- <fichero>` y verifica `git hash-object` contra `HEAD:<fichero>`.

---

## 8. Qué NO es un hallazgo (declarado de antemano)

- Que el **flag Adaptive siga OFF por defecto**: con OFF el camino de producción es **byte-idéntico** a
  `v2.54` y el reparto por celda **no se ejecuta**. Es una decisión, no un olvido.
- Que el reparto por celda **solo** actúe sobre el eje del **R neto medido**: con el eje de moneda el
  reparto es global y lo **declara**. No hay moneda medida por régimen y **no se inventa** (una fase
  futura podría añadir el productor; hoy es un límite declarado).
- Que la celda **nunca** cambie quién compite: es el **diseño**, no una carencia. Añadir o quitar
  competidores por celda sería el fallo, no la mejora.
- Que los **tres campos** de celda vivan en `AllocationPlan` pero se **declaren** en el nivel del plan:
  la desviación respecto al plan (§5 del pack) es **más** estricta, y el frame sellado de `allocation`
  queda **byte-idéntico** a `AUTO-13`.
- El **`STALE` de un tick por el sello**: es una **consecuencia medida y declarada** del cambio de
  política, se cura con la primera fila `auto14-v1`, no resetea el contador y no ocurre con el flag OFF.
- Los **rojos del delta simétrico** (`5` nodos, `2` causas: el contrato de celdas y el sello): son los
  tests de `HEAD` que afirmaban el contrato viejo. **Ninguna** regresión de comportamiento.
- Los rojos de las suites **PG** en local (sin `asyncpg` ni PostgreSQL): están en el `--ignore` de la CI
  por diseño.
- **Sin UI** para `AUTO-7`…`AUTO-14`: todo esto es observable por el journal y los logs del tick.

---

## 9. Preguntas abiertas que el autor NO cierra

1. **El Data Gate no se persiste** (el contador de fallos es **de proceso**): entre un reinicio y el
   primer fallo propio, un journal muerto no bloquea. ¿Ventana aceptable, o exige persistir la racha?
   (Candidato declarado para `AUTO-15`.)
2. **El coste es estimado**: por eso el R neto cae a `PARTIAL` y con él la celda a `cell_net_unmeasured`.
   Mientras el coste no sea **medido**, el eje del R neto y las celdas solo actúan donde la medición
   alcanza. ¿Es suficiente, o el productor de coste real es la fase que falta?
3. **Los umbrales están declarados, no calibrados** (`min_trades`, `confidence_prior = 20`,
   `severe_decay_factor = 0.5`, `recovery_step_cycles = 3`). ¿Con qué evidencia se sostienen?
4. **¿La celda debería poder *castigar*?** Hoy una celda medida y **negativa** cae al **global**
   (`cell_not_positive`): el reparto **afina**, no penaliza. Es una decisión de producto declarada, no
   un olvido. ¿Debería una celda negativa **reducir** el peso?
5. **§20: ¿el fallback al global es la política correcta?** Con la celda no utilizable, la versión pesa
   con su fila. Es lo declarado y lo medido; la pregunta de producto (¿abstenerse?) no se cierra aquí.

---

## 10. Lo que **no** debes asumir

- Que un test verde proteja nada: esta línea ya destapó un control **mudo** (un test adverso que pasaba
  un régimen que el tick nunca sirve). Si un test dice «la celda no mueve», exige **el control que sí
  mueve** —y está: `test_a_measured_cell_moves_the_weight_and_a_thin_one_never_does`.
- Que `107/107` y `0` en `NADA` signifiquen cobertura: significan que **esas 107** mordieron. Una
  **nueva** forma de romper el invariante es un hallazgo legítimo.
- Que el filtro de la sonda sea `--only`: se le pasan los rótulos **como argumentos** (`… M99 M100`).
- Que `git show HEAD:<f> > <f>` sea seguro en PowerShell: **fabrica bytes nulos**. Escribe con Python
  **como bytes** y **verifica la restauración**.
- Que las cifras del `CHANGELOG` sean la CI: son la selección local; las del tag citan su run.

---

## 11. Formato del hallazgo

```
P0/P1/P2 · afirmación · ruta:línea · comando exacto · salida · ¿ya declarado en §8/§9 o en el §10 del pack?
```

Las cifras del **tag** citan el run de `Release tag CI` que las produjo (tabla en el §12 del pack); las
locales citan el comando y su salida. **Ninguna cifra se atribuye a un artefacto que no la produjo.**
