# Arranque del agente — post `v2.55-beta` (`AUTO-14` cerrada) · 2026-09-23

**Para qué es este documento.** `AUTO-14` está **sellada** (`v2.55-beta`, `1.80.0-beta`) y `main` la
recibió en fast-forward. Esto es el **punto de entrada** de un agente nuevo: el orden de lectura, el
método de verificación que no se improvisa, el freeze y las trampas del entorno. **No** decide el alcance
de `AUTO-15`: propone candidatos y **espera ratificación del propietario** antes de tocar código.

---

## 0. El prompt para arrancar (cópialo tal cual)

```
Continúa la línea AUTO en este repo. Lee primero, en este orden:
  1. docs/engineering/traspaso-relevo-post-v2.55-auto-14-reparto-por-celda-de-regimen-2026-09-23.md
  2. docs/engineering/audit-pack-v2-55-auto-14-reparto-por-celda-de-regimen-2026-09-23.md
  3. docs/engineering/arranque-auditor-v2.55-auto-14-reparto-por-celda-de-regimen-2026-09-23.md
  4. docs/engineering/PROJECT_STATE.md

AUTO-14 está CERRADA y sellada (tag v2.55-beta, 1.80.0-beta). NO reabras esa fase ni toques nada sellado.
El flag Adaptive sigue OFF: el runtime publicado es, en comportamiento, el de v2.53-beta.

Confirma primero el estado medido del repo (git log, git tag --points-at, git status limpio salvo
governor.json) y verifica que las compuertas pasan (ruff del scope CI, mypy del YAML, lint-imports) ANTES
de proponer nada.

Después, NO implementes: propónme el ALCANCE de AUTO-15 como máximo en 3 opciones, cada una con
  (a) el invariante que protege, (b) los ficheros que tocaría, (c) si exige migración y por qué,
  (d) el gate de verificación (tests, mutaciones nuevas M108+ y delta simétrico).
Candidatos declarados por la fase anterior: Data Gate PERSISTIDO (hoy el contador de fallos se pierde al
reiniciar), la UI de AUTO-7..AUTO-14 (la celda, la banda medida, el estado del gate y la rampa ya existen
y no se ven) y el COSTE REAL por ciclo (hoy es estimado, así que el R neto cae a PARTIAL y la celda
declara su hueco). Espera mi ratificación antes de escribir código.

Método obligatorio: compuertas del §5 del relevo, delta simétrico FICHERO A FICHERO contra HEAD (nunca
restando totales) y matriz de mutaciones COMPLETA sin ninguna etiqueta en NADA. Si algo falla, se declara;
nunca se silencia.
```

---

## 1. Estado en una tabla

| Corte | Estado | Ref |
| --- | --- | --- |
| `AUTO-14` (Reparto por CELDA de régimen) | **cerrada y sellada** | tag **`v2.55-beta`**, `1.80.0-beta` |
| `main` | **recibió la fase** (fast-forward, sin merge) | `6fad572d..e29e6227` |
| Tag | **`v2.55-beta`** empujado **suelto** (sin `--follow-tags`) | `Release tag CI` [`35889751810`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35889751810) **GREEN** (`10 success` + `1 skipped`); job `quality` del tag **`2575 passed / 38 skipped`** |
| Runtime | **el de `v2.53-beta`**: flag Adaptive **OFF** | el reparto por celda **no se ejecuta** |
| Migración | **ninguna** | Alembic head `044_auto_cycle_trace` |
| Árbol | limpio **salvo `governor.json`** (sin trackear) | — |
| Siguiente | **`AUTO-15`** (alcance **por ratificar**, no decidido) | §5 de este documento |

---

## 2. Dónde está cada cosa (anclas re-medidas sobre el árbol sellado)

| Superficie | Ruta | Ancla |
| --- | --- | --- |
| Sello y motivos de celda | `packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive.py` | sello `:168` · motivos `:242-256` |
| `AllocationPlan` (+3 campos de celda) | `auto_adaptive.py` | `:504` · `cell_for` `:539` · `cell_note_for` `:542` · `as_dict` `:544` |
| Base de celda del plan | `auto_adaptive.py` | `allocationCells` `:750-754` |
| Selección de celda (helper puro) | `auto_adaptive.py` | `_cell_key` `:860` · `regime_cell_for` `:871` |
| Reparto | `auto_adaptive.py` | `_AllocationSources` `:910` · `_allocation_weights` `:923` |
| Encogimiento de celda | `auto_adaptive.py` | `_cell_confidence` `:999` · `_confidence_factor` `:1016` |
| Reparto público + rampa | `auto_adaptive.py` | `recommend_allocation` `:1040` · shrink `:1108-1122` · rampa `:1141` |
| Plan del tick | `auto_adaptive.py` | `build_adaptive_plan` `:1223-1234` |
| Declaración en el tick | `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` | `:3167` |
| Contrato durable (lista blanca) | `packages/py/application/src/bolsa_application/auto_adaptive_journal.py` | `_ALLOCATION_KEYS` `:58` |
| Sonda de mutaciones | `apps/api-python/scripts/v2_44_mutation_audit.py` | `M99…M107` |

**Suites de la fase** (verificadas): unit `test_auto_adaptive.py` (**90**) y las costuras
`test_auto_v53_auto12_confidence_seam.py` (**9**), `test_auto_v54_auto13_recovery_seam.py` (**14**),
`test_auto_v55_auto14_regime_cell_allocation_seam.py` (**6**, nueva). Tramo: **`119 passed`**.

---

## 3. El método (no se improvisa)

1. **Compuertas** (los comandos de CI, no rutas sueltas):
   ```bash
   uv run ruff check packages/py apps/api-python --config pyproject.toml
   uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
               packages/py/application/src apps/api-python/src --follow-imports=silent
   uv run lint-imports --config packages/py/.importlinter
   ```
2. **Delta simétrico fichero a fichero contra `HEAD`** (nunca restando totales): los tests
   **modificados** se corren también en su versión de `HEAD` contra el código nuevo. El **único rojo
   admisible** es un contrato **declarado** como cambiado (el sello de política, una regla que la fase
   cambia); cualquier otro rojo es regresión. Hazlo con un script que **lea y escriba bytes** y
   **verifique la restauración** (`git show` por PowerShell fabrica bytes nulos).
3. **Mutaciones**: `uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py`. La matriz va
   por **`M107`**; una fase nueva añade **`M108+`**. Gate: la matriz **completa** sin ninguna etiqueta en
   `NADA`, sin fragmentos ausentes y el árbol **intacto** al terminar.
4. **Todo lo que no se puede medir, se declara** (`UNKNOWN`/`PARTIAL` + motivo). Nunca un `0` que se lea
   como «coste cero», ni un estado que afirme más de lo medido.
5. **No tocar nada sellado** ni editar los planes de fases cerradas: son documento histórico.

---

## 4. Freeze que hereda `AUTO-15`

- **NO LIVE** · sin SHORT · **sin migración** salvo que la fase lo justifique y se ratifique.
- **No se toca:** `auto_adaptive_journal.py` (**byte a byte igual** tras `AUTO-14`), el contrato de la
  tabla `decision_journal_entries` (sin claves nuevas ni backfill), `yahoo_circuit_breaker.py`,
  `ADAPTIVE_ADVERSE_REGIMES`, los umbrales de rotación, el **gobernador**
  (`v2_43_governor_evidence.py`, diff vacío) y el esquema.
- **No se mezclan los ejes:** operativo (`ACTIVE`/`PAUSED`/`RECOVERING`), datos
  (`OK`/`DEGRADED`/`STALE`/`BLOCKED`), calidad (`LOW`/`MEDIUM`/`HIGH`) y base de reparto
  (`allocationCells`) van en **campos propios**.
- **El flag Adaptive sigue OFF**: nada de lo nuevo puede cambiar el comportamiento publicado por
  defecto.
- `*.md` **sin `prettier`**.

---

## 5. Candidatos para `AUTO-15` (declarados, **no decididos**)

| # | Candidato | Invariante que protege | Migración |
| --- | --- | --- | --- |
| A | **Data Gate persistido** (hoy el contador de fallos se pierde al reiniciar) | «No acusar sin prueba» **sobrevive a un reinicio**; cierra la ventana declarada de `AUTO-13` §9.1 | Probablemente **sí** (estado durable) |
| B | **UI de `AUTO-7`…`AUTO-14`** (el cruce `strategy × regime`, la base de CELDA del reparto, la banda medida, el estado del gate y la rampa **ya existen y no se ven**) | Lo medido se **publica**, no se oculta; el operador no lee un `0` donde no hubo medida | No |
| C | **Coste REAL por ciclo** (hoy es **estimado**, el R neto cae a `PARTIAL` y la celda declara `cell_net_unmeasured`) | «Lo que no se midió, se declara» **deja de ser el caso común**: el eje del R neto y las celdas actúan donde hoy se abstienen | Probablemente **sí** (productor de coste) |

**Pregunta abierta que el propietario debe cerrar antes de elegir:** ¿el siguiente movimiento es
**capacidad nueva** (C, la deuda más repetida en los límites declarados), **durabilidad de lo ya
construido** (A) o **explicabilidad** (B)?

---

## 6. Trampas del entorno (Windows / este repo)

1. `git show HEAD:<f> > <f>` **fabrica bytes nulos** en PowerShell: leer y reescribir **como bytes** con
   Python y **comprobar la restauración**.
2. `asyncpg` ausente y teardown PG del conftest de `apps/api-python`: las suites PG **no** corren offline;
   la CI sí las mide. Con `DATABASE_URL` a un puerto cerrado y `PGCONNECT_TIMEOUT=5`, el tramo de esta
   fase tarda **6 s** (sin eso, minutos). No confundir un error de entorno con un fallo de la fase.
3. Escribir mensajes de commit a un **fichero** y usar `git commit -F` (PowerShell no traga heredocs).
4. Salida no-ASCII por `python -c` revienta en `cp1252`: escribir a **fichero UTF-8**.
5. Interrumpir la consola **no mata** al hijo de la matriz de mutaciones (sigue reescribiendo ficheros):
   comprueba procesos y `git status` **antes** de dar una corrida por cerrada.
6. Copiar del visor puede dejar el **prefijo de línea** dentro del código: `rg "^\s*\d+\|"` antes de
   commitear.
7. **El `ruff` de la fase no incluye `ruff format`**: formatear en masa reescribe ficheros ajenos.
