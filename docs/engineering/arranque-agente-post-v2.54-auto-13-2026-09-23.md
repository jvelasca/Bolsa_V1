# Arranque del agente — post `v2.54-beta` (`AUTO-13` cerrada) · 2026-09-23

**Para qué es este documento.** `AUTO-13` está **sellada** (`v2.54-beta` → `54a3b86a`, `1.79.0-beta`) y
`main` la recibió en fast-forward. Esto es el **punto de entrada** de un agente nuevo: el orden de lectura,
el método de verificación que no se improvisa, el freeze y las trampas del entorno. **No** decide el alcance
de `AUTO-14`: propone candidatos y **espera ratificación del propietario** antes de tocar código.

---

## 0. El prompt para arrancar (cópialo tal cual)

```
Continúa la línea AUTO en este repo. Lee primero, en este orden:
  1. docs/engineering/traspaso-relevo-post-v2.54-auto-13-adaptive-data-gate-y-recovery-gradual-2026-09-23.md
  2. docs/engineering/audit-pack-v2-54-auto-13-adaptive-data-gate-y-recovery-gradual-2026-09-23.md
  3. docs/engineering/arranque-auditor-v2.54-auto-13-adaptive-data-gate-y-recovery-gradual-2026-09-23.md
  4. docs/engineering/PROJECT_STATE.md

AUTO-13 está CERRADA y sellada (tag v2.54-beta -> 54a3b86a, 1.79.0-beta). NO reabras esa fase ni toques
nada sellado. El flag Adaptive sigue OFF: el runtime publicado es, en comportamiento, el de v2.53-beta.

Confirma primero el estado medido del repo (git log, git tag --points-at, git status limpio salvo
governor.json) y verifica que las compuertas pasan (ruff del scope CI, mypy del YAML, lint-imports) ANTES
de proponer nada.

Después, NO implementes: propónme el ALCANCE de AUTO-14 como máximo en 3 opciones, cada una con
  (a) el invariante que protege, (b) los ficheros que tocaría, (c) si exige migración y por qué,
  (d) el gate de verificación (tests, mutaciones nuevas M99+ y delta simétrico).
Candidatos declarados por la fase anterior: reparto por CELDA de régimen (la matriz avanzada que el §20
dejó fuera), Data Gate PERSISTIDO (hoy el contador de fallos se pierde al reiniciar) y la UI de
AUTO-7..AUTO-13. Espera mi ratificación antes de escribir código.

Método obligatorio: compuertas del §5 del relevo, delta simétrico FICHERO A FICHERO contra HEAD (nunca
restando totales) y matriz de mutaciones COMPLETA sin ninguna etiqueta en NADA. Si algo falla, se declara;
nunca se silencia.
```

---

## 1. Estado en una tabla

| Corte | Estado | Ref |
| --- | --- | --- |
| `AUTO-13` (Adaptive Data Gate + recovery gradual) | **cerrada y sellada** | tag **`v2.54-beta`** → `54a3b86a`, `1.79.0-beta` |
| `main` | **recibió la fase** (fast-forward, 10 commits, sin merge) | `origin/main` = `9ac2e0d8` (docs de sellado) |
| Rama de auditoría | `auto-13-adaptive-data-gate` · **PR draft [#63](https://github.com/jvelasca/Bolsa_V1/pull/63)** | delta completo sobre `v2.53` |
| Runtime | **el de `v2.53-beta`**: flag Adaptive **OFF** | gate y rampa **no se ejecutan** |
| Migración | **ninguna** | Alembic head `044_auto_cycle_trace` |
| Árbol | limpio **salvo `governor.json`** (sin trackear) | — |
| Siguiente | **`AUTO-14`** (alcance **por ratificar**, no decidido) | §5 del relevo |

**Commits de la fase:** `009e8965` (plan) · `d9242970` (ratificación) · `f45ac604` … `dcc0d64b` (Pasos 1–5) ·
`c6aec527` (relevo Paso 5) · `54a3b86a` (**paquete + bump**, el que lleva el tag) · `6ab3c851` y `9ac2e0d8`
(documentación de sellado en `main`).

---

## 2. Dónde está cada cosa (anclas re-medidas sobre el árbol sellado)

| Superficie | Ruta | Ancla |
| --- | --- | --- |
| Gate puro | `packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive_data_gate.py` | estados `:57` · efectos `:62` · tabla `:85` · política `:69` · `journal_age_cycles` `:205` · `assess_data_gate` `:237` |
| Adaptive | `packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive.py` | sello `:143` · estados `:208` · rampa `:216`/`:219` · `StrategyHealth` `:290` · `recovery_reading` `:527` · `AdaptivePlan` `:560` · `recommend_rotation` `:708` · `recommend_allocation` `:826` · `build_adaptive_plan` `:916` |
| Lector durable | `packages/py/application/src/bolsa_application/auto_adaptive_recovery.py` | `_reactivations` `:258` · `AdaptiveStateReading` `:301` · `last_published_at` `:323` · `reactivated_at` `:327` · `read_adaptive_state` `:357` |
| Feed | `packages/py/application/src/bolsa_application/auto_self_evaluation_feed.py` | `_positive_cycles_after` `:257` · `recovery_evidence_from_fills` `:319` |
| Worker | `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` | contador `:748` · lectura `:753` · cortes `:759` · `_v2_build_adaptive_plan` `:3036` · `shrink=` `:3130` · hueco `:3158-3164` · `_v2_next_paused_cycles` `:3238` · política/regime `:3249`/`:3259` · `_v2_adaptive_data_gate` `:3273` · `_v2_adaptive_decision_cycles` `:3322` · ancla `:3369` · sink `:3386` · contador `:3424`/`:3432` |

**Suites de la fase** (verificadas): unit `test_auto_adaptive.py` (78), `test_auto_adaptive_data_gate.py`
(29), `test_auto_adaptive_recovery.py` (26), `test_auto_self_evaluation_feed.py` (29) y las cuatro costuras
`test_auto_v54_auto13_*.py`: `data_gate_seam` (9), `data_gate_wiring_seam` (10), `recovery_seam` (14),
`regime_fallback_seam` (7).

---

## 3. El método (no se improvisa)

1. **Compuertas** (los comandos de CI, no rutas sueltas):
   ```bash
   uv run ruff check packages/py apps/api-python --config pyproject.toml
   uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
                packages/py/application/src apps/api-python/src --follow-imports=silent
   uv run lint-imports --config packages/py/.importlinter
   ```
2. **Delta simétrico fichero a fichero contra `HEAD`** (nunca restando totales): los tests **modificados**
   se corren también en su versión de `HEAD` contra el código nuevo. El **único rojo admisible** es el test
   del sello de política o un contrato **declarado** como cambiado; cualquier otro rojo es regresión.
3. **Mutaciones**: `uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py`. La matriz va
   por **`M98`**; una fase nueva añade **`M99+`**. Gate: la matriz **completa** sin ninguna etiqueta en
   `NADA` y el árbol **intacto** al terminar.
4. **Todo lo que no se puede medir, se declara** (`UNKNOWN`/`PARTIAL` + motivo). Nunca un `0` que se lea
   como «coste cero», ni un estado que afirme más de lo medido.
5. **No tocar nada sellado** ni editar los planes de fases cerradas: son documento histórico.

---

## 4. Freeze que hereda `AUTO-14`

- **NO LIVE** · sin SHORT · **sin migración** salvo que la fase lo justifique y se ratifique.
- **No se toca:** `auto_adaptive_journal.py` (**byte a byte igual** tras `AUTO-13`), el contrato de la tabla
  `decision_journal_entries` (sin claves nuevas ni backfill), `yahoo_circuit_breaker.py`,
  `ADAPTIVE_ADVERSE_REGIMES`, los umbrales de rotación, el **gobernador** (`v2_43_governor_evidence.py`,
  diff vacío) y el esquema.
- **No se mezclan los tres ejes:** operativo (`ACTIVE`/`PAUSED`/`RECOVERING`), datos
  (`OK`/`DEGRADED`/`STALE`/`BLOCKED`) y calidad (`LOW`/`MEDIUM`/`HIGH`) van en **campos propios**.
- **El flag Adaptive sigue OFF**: nada de lo nuevo puede cambiar el comportamiento publicado por defecto.
- `*.md` **sin `prettier`**.

---

## 5. Candidatos para `AUTO-14` (declarados, **no decididos**)

| # | Candidato | Invariante que protege | Migración |
| --- | --- | --- | --- |
| A | **Reparto por celda de régimen** (la matriz avanzada que el §20 dejó fuera) | El reparto no puede mejorar con una celda que no se ha medido: sin muestra suficiente, se **declara** y cae al global | No (cálculo puro) |
| B | **Data Gate persistido** (hoy el contador de fallos se pierde al reiniciar) | «No acusar sin prueba» **sobrevive a un reinicio**; cierra la ventana declarada del §9.1 del arranque del auditor | Probablemente **sí** (estado durable) |
| C | **UI de `AUTO-7`…`AUTO-13`** (el cruce `strategy × regime`, la banda medida, el estado del gate y la rampa **ya existen y no se ven**) | Lo medido se **publica**, no se oculta; y el operador no lee un `0` donde no hubo medida | No |

**Pregunta abierta que el propietario debe cerrar antes de elegir:** ¿el siguiente movimiento es
**capacidad nueva** (A), **durabilidad de lo ya construido** (B) o **explicabilidad** (C)?

---

## 6. Trampas del entorno (Windows / este repo)

1. `git show HEAD:<f> > <f>` **fabrica bytes nulos** en PowerShell: leer y reescribir **como bytes** con Python.
2. `asyncpg` ausente y teardown PG del conftest de `apps/api-python`: las suites PG **no** corren offline;
   la CI sí las mide. No confundir un error de entorno con un fallo de la fase.
3. Escribir mensajes de commit a un **fichero** y usar `git commit -F` (PowerShell no traga heredocs).
4. Salida no-ASCII por `python -c` revienta en `cp1252`: escribir a **fichero UTF-8**.
5. Interrumpir la consola **no mata** al hijo de la matriz de mutaciones (sigue reescribiendo ficheros):
   comprueba procesos y `git status` **antes** de dar una corrida por cerrada.
6. Copiar del visor puede dejar el **prefijo de línea** dentro del código: `rg "^\s*\d+\|"` antes de commitear.
