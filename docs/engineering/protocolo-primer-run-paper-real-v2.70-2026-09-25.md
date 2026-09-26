# Protocolo operativo — primer RUN de evidencia PAPER real (`AUTO-22` / `AUTO-23`)

> **AsOf:** 2026-09-25 · **Versión:** `1.95.0-beta` · **Fase:** `v2.70-beta` / `AUTO-23`
> **Naturaleza:** runbook **operativo** del propietario. **No hay código nuevo de decisión**: se usan
> el RUN ya auditado (`auto_evidence_run.py`, `AUTO-22`) y el harness de validación
> (`auto_evidence_validate.py`, `AUTO-23`). **El freeze no se toca** y **la evidencia no reparte**.

## Invariante del protocolo

> **La corrida se ejecuta COMPLETA o se declara BLOQUEADA; y para conseguir la primera lectura NO se
> baja ningún umbral.** Si hace falta bajar `min cycles` / `min R` / `folds` para que el runner
> produzca algo, la respuesta correcta es **esperar más material**, no relajar la evidencia.

## Prerrequisitos (comprobables)

1. **Material en PostgreSQL durable.** La cuenta PAPER tiene fills durables de la estrategia a medir
   y las reservas por ciclo (`reserved_risk`) reconstruibles. El régimen lo lee `AUTO-10` por
   `decision_id`.
2. **Venue PAPER.** `BROKER_VENUE=paper` (literal). Si la venue no es `paper`, el lector único
   **BLOQUEA** (`NonPaperVenueError`, `exit 2`): un artefacto PAPER no se sella con material de otra
   venue.
3. **Completitud.** La lectura de reservas se pagina hasta agotar; si una página llena no aporta ids
   nuevos, se **BLOQUEA** (`MaterialIncompleteError`, `exit 2`) en vez de medir un universo sesgado.
4. **Muestra mínima para UNA estrategia.** El walk-forward por defecto (`folds=3`, `min_is=8`,
   `min_oos=4`) exige **≥32 ciclos medidos** (con R) **por estrategia**. Con menos, el RUN no puede
   producir evidencia: es **BLOQUEADO por material**, no un bug.
5. **`auto18-v1` / `auto15-v1` congelados**, Alembic head `046_fill_reference_mid`. Este protocolo
   **no** ejecuta migraciones ni toca el reparto.

## Paso 0 — comprobar el material antes de correr

```bash
# ¿Cuántos ciclos medibles hay por versión? (perímetro, sin publicar nada)
uv run --no-sync python apps/api-python/scripts/paper_cycles_export.py \
    --account-id <uuid> --strategy-version <v> > /tmp/material.json
```

El `material_manifest` declara `closedCycles`, `cyclesWithRisk`, `cyclesWithoutRisk`, el perímetro y
la **huella** (`material_fingerprint_v1`). Si `cyclesWithRisk` < 32, **no se sigue**: falta material.

## Paso 1 — PRIMERA corrida: UNA sola estrategia

Primero **una** estrategia. No arrancar con 10 estrategias y 500 ciclos: si aparece una discrepancia,
aislarla con una sola es mucho más fácil.

```bash
uv run --no-sync python apps/api-python/scripts/auto_evidence_run.py \
    --account-id <uuid> --strategy-version <v> \
    --bucket day --folds 3
```

Qué produce, en `evidence_runs/<UTC>-<huella8>/`:

| Fichero | Qué es |
|---|---|
| `cycles.json` | el material leído (con su manifest y huella) |
| `artifact.json` | el `auto20c_evidence_artifact_v1` que importa la cabina |
| `render.txt` | el `AUTO EVIDENCE REPORT` legible |
| `run.json` | schema, args, **huella**, origen y los tres niveles |

- **Es inmutable.** Si el directorio ya existe se **BLOQUEA** (`exit 2`): no se sobrescribe una
  medición.
- **Es fail-closed.** Sin PG / sin material / sin R medible / venue ≠ paper, **no se crea carpeta**.
- **Importar en la cabina:** sección **AUTO EVIDENCE** → `Importar JSON` → `artifact.json`. La UI
  muestra **SOURCE** (`PAPER REAL` = datos reales, **dinero VIRTUAL**) y **EXECUTION REALITY**
  (`VIRTUAL — NO REAL MONEY`) antes de cualquier número.

Lectura esperada de la primera corrida: `P(R>0)`, `P(R>0) OOS`, `WFE` (Nivel 2) y, en el Nivel 3, el
régimen actual y su evidencia por estrategia. Lo que no se pudo medir sale **`NO MEDIDO`**.

## Paso 2 — SEGUNDA corrida: AÑADIR la segunda estrategia

Solo después de validar la primera:

```bash
uv run --no-sync python apps/api-python/scripts/auto_evidence_run.py \
    --account-id <uuid> --strategy-version <v-a> --strategy-version <v-b> \
    --bucket day
```

Ahora sí se puede evaluar de verdad `correlation(A,B)` y comprobar si la **correlación por cubos
temporales** funciona con material real (deuda **P3-2**). El harness publica, junto al número, sus
diagnósticos:

```bash
uv run --no-sync python apps/api-python/scripts/auto_evidence_validate.py \
    --account-id <uuid> --strategy-version <v-a> --strategy-version <v-b> \
    --sizes 16,32,64,128 --buckets day,week,month
```

Qué mirar en `correlation_validation.json`:

- `pairs[*].correlation` con su `sharedBuckets` (o **`NO MEDIDO`** si no hay cubos compartidos).
- `diagnostics.strategies[*].singleCycleBucketShare`: fracción de cubos sostenidos por **un solo
  ciclo**. Alta ⇒ la media de cubo es ruido, no un resultado.
- `diagnostics.strategies[*].cycles` / `activeBuckets`: **frecuencia y exposición** distintas entre
  estrategias (una opera 10× más que la otra) ⇒ se declara la limitación **antes** de tocar la métrica.

## Paso 3 — `P(R>0)` vs N y estabilidad del régimen

```bash
uv run --no-sync python apps/api-python/scripts/auto_evidence_validate.py \
    --account-id <uuid> --strategy-version <v> \
    --sizes 16,32,64,128
```

- `sweep.json` publica `P(R>0)` / `P(R>0)` OOS / `WFE` / `effective_n` sobre el **prefijo
  cronológico** para cada `N`. **No se elige el `N`** que mejor suena: se observa si la lectura se
  **estabiliza**. Un `N` mayor que el material medido es **`NO MEDIDO`**, nunca una fila fabricada.
- `regime_stability.json` publica el veredicto **global** y el de **cada régimen** con sus
  **divergencias** (p. ej. global `SUPPORTED` y régimen actual `NOT_SUPPORTED`). Es **lectura**, no un
  gate: no bloquea la estrategia ni mueve el reparto.

## Reglas duras (lo que NO se hace)

- **No bajar `min cycles` / `min R` / `folds` / `min_episodes`** para forzar una corrida. Sin material
  suficiente, el resultado correcto es **BLOQUEADO**.
- **No sobrescribir** una corrida o validación: son **inmutables** (`evidence_runs/`,
  `evidence_validations/`, `exist_ok=False`).
- **No copiar números a mano** ni recalcular `P(R>0)` / correlación fuera de los productores
  auditados: el harness **compone**, no reimplementa.
- **No convertir** `P(R>0)`, la correlación ni el régimen en `confidence`, sizing, plan, reserva ni
  rotación: siguen siendo **evidencia publicada** (`ALLOCATION = none`, `auto18-v1` congelado).
- **No leer `PAPER REAL` como dinero real**: es **datos reales de la cuenta PAPER con dinero
  VIRTUAL** (`EXECUTION REALITY = VIRTUAL — NO REAL MONEY`).

## Qué cierra esta fase

Con el primer RUN + la validación sobre material real quedan **cerrables**:

- **P3-2** (validación empírica de la correlación por cubos): comparar el número contra el diagnóstico
  de frecuencia/exposición y declarar si sesga.
- **P3-3** (`P(R>0)` vs tamaño muestral): documentar la relación `P(R>0) ↔ N` (y el `effective_n`) y
  decidir si hace falta una banda de confianza muestral **explícita**. **No** se convierte en permiso
  de sizing.

**Fuera de alcance:** allocation dinámica, `current-regime gating` operativo, LIVE y SHORT.
