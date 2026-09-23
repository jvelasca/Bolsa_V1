# Traspaso de relevo — `AUTO-14` **CERRADA** (`V2.55` / `1.80.0-beta`)

**Fase:** `AUTO-14` (Reparto por CELDA de régimen) · **Fecha:** 2026-09-23 · **Fase
anterior:** `V2.54` / `AUTO-13` (sellada: tag `v2.54-beta` → `54a3b86a`, `Release tag CI`
`35857892968` **GREEN**, `1.79.0-beta`).
**Documentos de la fase:**
[plan](./plan-v2-55-auto-14-reparto-por-celda-de-regimen-2026-09-23.md) (ratificado) ·
[audit-pack](./audit-pack-v2-55-auto-14-reparto-por-celda-de-regimen-2026-09-23.md) ·
[arranque del auditor](./arranque-auditor-v2.55-auto-14-reparto-por-celda-de-regimen-2026-09-23.md) ·
[arranque del agente siguiente](./arranque-agente-post-v2.55-auto-14-2026-09-23.md) · este relevo.
**Estado:** **fase CERRADA** — Pasos 1–5 hechos y verificados, tag **`v2.55-beta`** con su CI (cifras
medidas en §6). **El runtime sigue siendo el de `v2.53-beta`** con el flag Adaptive **OFF**: el reparto
por celda **no se ejecuta** en producción hasta un flag explícito. `main` recibe la fase **al sellar**
(fast-forward lineal, como en `v2.50`–`v2.54`), sin merge commit.

> **Este documento es la fuente de verdad de la fase CERRADA.** Se lee **antes** que
> [`PROJECT_STATE.md`](./PROJECT_STATE.md), que ya publica esta fase como la última cerrada y apunta
> aquí como relevo vivo.

---

## 0. Qué está ratificado y qué se ejecutó

**Rótulo ratificado por el propietario:** `AUTO-14` sobre **`V2.55` / `1.80.0-beta`**, **Opción A** del
arranque anterior, con alcance **core backend**, **sin UI**, **sin migración** (Alembic head sigue en
`044_auto_cycle_trace`), **sin tocar el gobernador** y **sin clave nueva en el journal durable**.

**Los tres candidatos del §5 del arranque de `AUTO-13` y qué pasó con ellos:**

| # | Candidato | Decisión |
| --- | --- | --- |
| **A** | **Reparto por celda de régimen** (la matriz avanzada que el §20 dejó fuera) | **RATIFICADO y EJECUTADO** (esta fase) |
| B | Data Gate **persistido** (hoy el contador de fallos se pierde al reiniciar) | **Fuera de alcance**, declarado (§7) |
| C | **UI** de `AUTO-7`…`AUTO-13` | **Fuera de alcance**, declarado (§7) |

**Lo que la ejecución confirmó y conviene no perder:**

1. **La celda afina el PESO, nunca la composición.** El numerador lo decide la **fila**; la celda solo
   cambia el número con el que compite una versión **ya admitida**. Es lo que hace la fase **incapaz**
   de añadir o quitar competidores, y hay mutaciones (`M99`…`M107`) que mueren si alguien lo intenta.
2. **El frame sellado de `allocation` NO se toca.** El plan preveía declarar la celda dentro de
   `AllocationPlan.as_dict()`; la implementación la declara en el **nivel del plan**
   (`allocationCells`) para que el frame de `AUTO-13` quede **byte-idéntico**. Es **más** estricto que
   el plan y deja el test que fija el frame **sin tocar**.
3. **El contrato durable no cambió una coma.** `_ALLOCATION_KEYS` (`auto_adaptive_journal.py:58`)
   proyecta `riskMultipliers` + `evidenceAxis`: `allocationCells` vive en el plan y en la **traza del
   tick**, nunca en el journal.
4. **El sello sube a `auto14-v1` y su consecuencia se declara y se mide.** El mismatch de política
   marcará `STALE` **un tick** (hasta la primera fila `auto14-v1`); se cura con la primera escritura,
   **no** resetea el contador y **no se ejecuta con el flag OFF**. No se relaja nada de `AUTO-11`.

---

## 1. Estado medido del repo (2026-09-23)

- **Rama:** `main` (la fase viaja en fast-forward lineal; sin rama de fase y sin PR de fase —el
  [PR draft #63](https://github.com/jvelasca/Bolsa_V1/pull/63) de `AUTO-13` se queda como está—).
  Árbol limpio **salvo `governor.json`** (sin trackear, como estaba).
- **Base:** `6fad572d` (los arranques de `v2.54` en `main`), que incluye `54a3b86a` —el commit sellado de
  `AUTO-13`— y los dos commits de documentación de su sello.
- **Sin migración:** head `044_auto_cycle_trace`.
- **Tag anterior `v2.54-beta` → `54a3b86a`**: **no se reabre**. Sus cifras de CI (`10 success` +
  `1 skipped`, `check-runs` `38 success` + `1 skipped`, job `python` `2568 passed / 35 skipped`) son el
  **delta de referencia** de esta fase.

---

## 2. Lo ya HECHO y verificado (Pasos 1 a 5)

### Paso 1 — El helper puro de selección de celda

- **`regime_cell_for(cells, strategy_version, regime) -> (celda | None, motivo | None)`**
  (`auto_adaptive.py:871`) es el **único** sitio donde se elige celda, y devuelve **siempre** el par:
  el hueco nunca se silencia.
- **Normalización declarada y única** (`_cell_key`, `:860`): `strip().upper()` en los dos lados, **sin
  traducir** de nuevo el régimen (el plan recibe el **canónico**; un segundo mapa de alias podría
  divergir del que usó la rotación).
- **Guard por celda**: `decisive` (`:900`), `net_r_measurement == COMPLETE` (`:901`) y R neto
  **positivo** (`:903`). Cualquier otro caso devuelve motivo propio (`cell_regime_absent`,
  `cell_not_found`, `cell_not_decisive`, `cell_net_unmeasured`, `cell_not_positive`).
- **Nunca se hereda**: no se elige otra celda, ni la de otra versión, ni la de otro ciclo.

### Paso 2 — El cableado de la celda en el reparto

- `_AllocationSources` (`:910`) publica `axis`, `positive`, `cell_axis`, `cell_used` y `cell_fallback`;
  `_allocation_weights(...)` (`:923`) acepta `cells_by_version` y `regime` **keyword-only opcionales**.
- **El eje y el grupo siguen calculándose con la FILA** (`decisive` + expectancy positiva; R neto
  `COMPLETE` y **cubriendo a todo el grupo**, `:979`). La celda se consulta **solo para quien ya
  competía** (`:965-976`) y **solo** cuando el eje adoptado es el R neto.
- **Con el eje de moneda** el reparto es el histórico y **todas** las que compiten declaran
  `cell_axis_without_cell` (`:986-993`).
- `recommend_allocation(...)` (`:1040`) gana `by_regime=()` y `regime=None`: **sin ellos el reparto es
  byte-idéntico** al de `v2.54` (el patrón de `AUTO-12` con `confidence=None`).
- **Suma-preservado, acotado a `[0, 1]` y sin ceros** (`:1126-1141`) y la rampa de `AUTO-13` sigue
  siendo **techo** (`min`, `:1141-1148`), aplicada **después** del reparto.

### Paso 3 — El encogimiento de `AUTO-12` con la banda de la CELDA

- `_cell_confidence(...)` (`:999`) busca el `RegimeConfidence` de la celda en
  `StrategyConfidence.by_regime` (que `AUTO-12` **ya** publicaba): si el peso salió de la celda, el
  factor se calcula con la **muestra efectiva** y el **deterioro** de **esa** celda (`:1113-1119`); si
  salió del global, con la banda de la estrategia. Sin lectura de confianza, comportamiento histórico.
- Es la decisión que evita reintroducir el *winner chasing* por la puerta de la celda: encoger un peso
  de celda con la muestra **agregada** (que mezcla regímenes que no se parecen) es exactamente lo que
  `AUTO-12` cerró (**M106**).

### Paso 4 — El sello `auto14-v1` y la declaración

- `ADAPTIVE_POLICY_VERSION = "auto14-v1"` (`:168`), con el test del sello renombrado **con nombre**.
- `AllocationPlan` (`:504`) gana `cell_axis`, `cell_used` y `cell_fallback` (`:525-534`) con lecturas
  propias (`cell_for` `:539`, `cell_note_for` `:542`) y **`as_dict()` intacto** (`:544-552`).
- `AdaptivePlan.as_dict()` publica `allocationCells` **en campo propio** (`:750-754`), junto a
  `regimeUndetermined` y `shrinkage`.
- La **consecuencia del sello** (gate `STALE` un tick por `policy_version_mismatch`) se fija con un
  test **y con su control** (sin lectura **no** se inventa un mismatch).

### Paso 5 — La costura del worker, con control

- `test_auto_v55_auto14_regime_cell_allocation_seam.py` (**6 tests**) corre por el **camino real del
  worker** (tick + lector de régimen) y **con control**: una celda **sin muestra** no mueve el peso y
  una **decisiva** sí; la composición no cambia y la rampa sigue topando; el tick **declara** la base de
  celda en el log (`auto_simulation_worker.py:3167`, **sin cambio de firma**); la proyección del journal
  es **byte-idéntica** con una celda presente; y el sello declara `STALE` sin resetear el contador.
- **Nota de método:** el control del reparto se hizo **explícito** (mismo escenario con celda medida vs
  celda fina) porque en esta línea un control **mudo** ya destapó una vez una costura que "pasaba" sin
  medir nada.

---

## 3. Anclas de código (verificadas sobre el árbol que se sella)

| Superficie | Ruta | Ancla |
| --- | --- | --- |
| Sello de política | `packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive.py` | `:168` (`auto14-v1`) |
| Motivos de celda (`ADAPTIVE_CELL_NOTE_*`) | `auto_adaptive.py` | `:242-256` |
| `AllocationPlan` (+3 campos, lecturas) | `auto_adaptive.py` | `:504` · `cell_for` `:539` · `cell_note_for` `:542` · `as_dict` `:544` |
| `allocationCells` en el plan | `auto_adaptive.py` | `:750-754` |
| `_cell_key` (normalización única) | `auto_adaptive.py` | `:860` |
| `regime_cell_for` (helper puro) | `auto_adaptive.py` | `:871` |
| `_AllocationSources` | `auto_adaptive.py` | `:910` |
| `_allocation_weights` | `auto_adaptive.py` | `:923` |
| `_cell_confidence` / `_confidence_factor` | `auto_adaptive.py` | `:999` / `:1016` |
| `recommend_allocation` (firma + shrink de celda) | `auto_adaptive.py` | `:1040` · shrink `:1108-1122` · rampa `:1141` |
| `build_adaptive_plan` (paso de celdas) | `auto_adaptive.py` | `:1223-1234` |
| Declaración del tick | `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` | `:3167` |
| Proyección durable (lista blanca) | `packages/py/application/src/bolsa_application/auto_adaptive_journal.py` | `:58` (`riskMultipliers`, `evidenceAxis`) |

**Suites de la fase** (verificadas): unit `test_auto_adaptive.py` (**90**, HEAD 78) y las costuras
`test_auto_v53_auto12_confidence_seam.py` (**9**), `test_auto_v54_auto13_recovery_seam.py` (**14**) y
`test_auto_v55_auto14_regime_cell_allocation_seam.py` (**6**, nueva). Tramo: **`119 passed`**.

**Sonda:** `apps/api-python/scripts/v2_44_mutation_audit.py` amplía **9 etiquetas** (`M99`…`M107`).

---

## 4. El método de verificación del repo (no improvisar)

1. **Compuertas** (los comandos de CI, no rutas sueltas):
   ```bash
   uv run ruff check packages/py apps/api-python --config pyproject.toml
   uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
               packages/py/application/src apps/api-python/src --follow-imports=silent
   uv run lint-imports --config packages/py/.importlinter
   ```
2. **Delta simétrico fichero a fichero contra `HEAD`** (nunca restando totales): los tests
   **modificados** se corren también en su versión de `HEAD` contra el código nuevo. Los rojos
   admisibles son los **declarados** (el contrato de celdas y el sello); cualquier otro rojo es
   regresión. **Cuidado con la trampa del terminal:** `git show HEAD:<f>` **fabrica bytes nulos** en
   PowerShell; el delta de esta fase se corrió con un script que lee y reescribe **bytes**
   (`Path.read_bytes`/`write_bytes` + reintento) y **verifica la restauración byte a byte** al final.
3. **Mutaciones**: `uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py` (filtro
   opcional por rótulo: `… M99 M100`). Gate: la matriz **completa** (`M1…M107`) sin ninguna etiqueta en
   `NADA`, sin fragmentos ausentes y con el árbol **intacto** al terminar.
4. **Todo lo que no se puede medir, se declara** (`UNKNOWN`/`PARTIAL` + motivo). Nunca un `0` que se lea
   como «coste cero», ni un estado que afirme más de lo medido.
5. **No tocar nada sellado** ni editar los planes de fases cerradas: son documento histórico. El plan
   de esta fase se **respeta**: la única desviación (declarar la celda en el nivel del plan en vez de
   dentro del frame de `allocation`) se declara en el audit-pack (§5) y es **más** estricta.

---

## 5. Trampas conocidas del entorno (Windows / este repo)

1. `git show HEAD:<f> > <f>` **fabrica bytes nulos** en PowerShell: leer y reescribir **como bytes** con
   Python y **comprobar la restauración** (esta fase lo hizo así en el delta simétrico).
2. **Los ficheros de test con CRLF**: `git` avisa (`CRLF will be replaced by LF`) al tocar el fichero
   con herramientas que normalizan. Comprobar `git diff --numstat` para descartar churn de fin de línea
   (**la fase quedó limpia**: `360` inserciones / `16` borrados reales en `test_auto_adaptive.py`).
3. **Suites PG** (`asyncpg` ausente, teardown de sesión del conftest): **no** corren offline; con
   `DATABASE_URL` a un puerto cerrado y `PGCONNECT_TIMEOUT=5` el tramo de la fase tarda **6 s** en vez
   de minutos. No confundir un error de entorno con un fallo de la fase.
4. Escribir mensajes de commit a un **fichero** y usar `git commit -F` (PowerShell no traga heredocs).
5. Interrumpir la consola **no mata** al hijo de la matriz de mutaciones (sigue reescribiendo ficheros):
   comprueba procesos y `git status` **antes** de dar una corrida por cerrada.
6. El `ruff` de la fase **no** incluye `ruff format`: formatear en masa reescribe ficheros ajenos.

---

## 6. El cierre, hecho y medido

- **Compuertas:** `ruff check packages/py apps/api-python --config pyproject.toml` → **`All checks
  passed!`** · `mypy` (comando de CI) → **`0` errores en `497` ficheros** · `lint-imports` →
  **`4 kept, 0 broken`**.
- **Tramo de la fase:** **`119 passed`** (`test_auto_adaptive.py` 90 + las tres costuras 9 + 14 + 6),
  `0` rojos.
- **Delta simétrico fichero a fichero:** **5 rojos** en `HEAD` con **2 causas declaradas** (el contrato
  de celdas y el sello `auto13-v1` → `auto14-v1`, que aparecía dentro de tres tests distintos) y **0**
  regresiones de comportamiento. Detalle y tabla en el audit-pack (§8).
- **Matriz de mutaciones COMPLETA:** **`107/107` muerden**, **`0`** en `NADA`, **`0`** fragmentos
  ausentes, restauración **byte a byte** y huella `git status` **idéntica** (`intacto: la sonda no
  altero el arbol`).
- **Sello:** tag anotado **`v2.55-beta`** sobre el commit del paquete de cierre (`e29e6227`), empujado
  **de uno en uno** (sin `--follow-tags`), y `main` en **fast-forward** (`6fad572d..e29e6227`). Tabla de
  runs en el audit-pack (§12). **Medido:** `Release tag CI`
  [35889751810](https://github.com/jvelasca/Bolsa_V1/actions/runs/35889751810) **GREEN** (`10 success` +
  `1 skipped`), job `quality` del tag **`2575 passed / 38 skipped`** con `Ruff: All checks passed!`, los
  **4 jobs PG verdes** y `check-runs` del commit sellado **`26 success + 1 skipped`**. **Delta contra el
  sello anterior:** `2568/35` → `2575/38` (la causa de los `+3` skipped **no** se atribuye: delta medido
  sin atribuir).
- **Lo que no se pudo medir aquí:** la batería offline **completa** de los jobs `quality`/`python` del
  tag (su recolección incluye suites PG que importan `asyncpg`, ausente, y el teardown de sesión exige
  PostgreSQL). **Ese límite lo cierra la CI del tag, medida.**

---

## 7. Límites declarados y freeze

- El reparto por celda **solo** actúa sobre el eje del **R neto medido**; con el eje de moneda es global
  y lo declara (no hay moneda medida por régimen y **no se inventa**).
- La celda **nunca** cambia quién compite: solo el peso relativo de quien ya competía.
- **El flag Adaptive sigue OFF**: sin él, esta fase **no se ejecuta** y el runtime publicado es, en
  comportamiento, el de `v2.53-beta`.
- **Fuera de alcance, sin tocar (declarado para una fase siguiente):** el **Data Gate persistido** (hoy
  el contador de fallos se pierde al reiniciar) y la **UI** de `AUTO-7`…`AUTO-14`.
- **Freeze respetado:** `auto_adaptive_journal.py` **byte a byte igual**, sello de `V2.53`/`V2.54`
  intacto, `yahoo_circuit_breaker.py`, `ADAPTIVE_ADVERSE_REGIMES` y los umbrales de rotación sin tocar,
  el **gobernador** con diff **vacío** (`exit 0`), la tabla `decision_journal_entries` y el esquema
  intactos, **sin migración**, **sin backfill**, **sin SHORT**, **sin UI**. `*.md` **sin `prettier`**.
  `governor.json` sigue **sin trackear**.

---

## 8. Punto de entrada para el siguiente agente

El **punto de entrada** de la fase siguiente es
[`arranque-agente-post-v2.55-auto-14-2026-09-23.md`](./arranque-agente-post-v2.55-auto-14-2026-09-23.md)
(con el prompt listo para copiar). Los **candidatos declarados** para `AUTO-15` y el estado del epic
están en su §5. **No** se decide alcance aquí: se propone y se **espera ratificación**.
