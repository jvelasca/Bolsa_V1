# Entrega a auditoría externa MIA — `v2.88.3-beta` (desde GitHub, 2026-09-29)

> **Objeto auditado:** tag anotado **`v2.88.3-beta`** (objeto `66f47cf8e72449dc5bb907ef208abcc7afb0e857` →
> commit **`0038adfc`**), versión **`2.11.3-beta`**, Alembic head **`046_fill_reference_mid`** (**sin
> migración**).
> **Repositorio:** `https://github.com/jvelasca/Bolsa_V1` — **PÚBLICO** (el auditor clona sin credenciales).
> **Punto de entrada del auditor:** [`arranque-auditor-v2-88-auto-material-16-obs14-2026-09-29.md`](./arranque-auditor-v2-88-auto-material-16-obs14-2026-09-29.md)
> (léelo **primero**: §1.1 cita del CI, §2 checklist reconciliada).
> **Evidencia:** [`evidence/v2.88.3/README.md`](./evidence/v2.88.3/README.md) ·
> **Informe/relevo:** [`obs-14c-costura-sin-atributo-v2.88.3-2026-09-29.md`](./obs-14c-costura-sin-atributo-v2.88.3-2026-09-29.md).

---

## 0. Qué es y qué NO es esta entrega

**Es** el paquete de handover para una **auditoría externa (MIA) desde GitHub**: el objeto ya está sellado y
publicado, con su CI acreditado y su evidencia dentro del tag. Esta entrega **no cambia código**: es un
`docs`-only que (a) fija la **firma de estado verificada** antes de auditar, (b) enumera las **trampas
declaradas** que un auditor puede leer mal y (c) deja el **prompt** y el **entregable esperado**.

**NO es** una auditoría. El veredicto lo emite el auditor externo. **NO** cierra ninguna deuda: `OBS-14.b`,
`OBS-15` y `OBS-16` siguen **ABIERTAS** (§8).

---

## 1. El objeto y cómo obtenerlo

| | |
| --- | --- |
| Tag (anotado) | `v2.88.3-beta` → objeto `66f47cf8e72449dc5bb907ef208abcc7afb0e857` |
| Commit sellado | `0038adfcf548361986b6e93825402d7f377311f0` |
| Versión | `2.11.3-beta` |
| Alembic head | `046_fill_reference_mid` (único head, **sin migración**) |
| Fase | `AUTO-MATERIAL-16c` (RE-SELLO 3) |
| Tags superados | `v2.88-beta` (rojo), `v2.88.1-beta` (rojo), `v2.88.2-beta` (rojo) — **sus rojos se conservan**, no se borran |

```
git clone https://github.com/jvelasca/Bolsa_V1.git
cd Bolsa_V1
git rev-parse v2.88.3-beta                # 66f47cf8e72449dc5bb907ef208abcc7afb0e857
git rev-list -n1 v2.88.3-beta             # 0038adfc...
git show v2.88.3-beta:package.json        # "version": "2.11.3-beta"
```

---

## 2. Firma de estado verificada **antes** de auditar

Todo lo de esta tabla se **midió en un clon fresco desde GitHub** (no en el árbol de trabajo del autor),
el 2026-09-29. El clon pesa **17,2 MB**.

| # | Comprobación | Comando | Resultado |
| --- | --- | --- | --- |
| 1 | Clon anónimo (repo público) | `git clone https://github.com/jvelasca/Bolsa_V1` | OK, `HEAD` = `daa84386` |
| 2 | Los 4 tags del sello viajan | `git tag -l "v2.88*"` | `v2.88-beta`, `v2.88.1-beta`, `v2.88.2-beta`, **`v2.88.3-beta`** |
| 3 | Tag **anotado** (no ligero) | `git cat-file -t v2.88.3-beta` | `tag` |
| 4 | Árbol limpio | `git status --porcelain` | **vacío** |
| 5 | **El motor NO cambia en este sello** | `git diff --stat v2.88.2-beta v2.88.3-beta -- packages/py apps/api-python/src` | **vacío** |
| 6 | Delta acumulado del motor desde `v2.88.1` | `git diff --numstat v2.88.1-beta v2.88.3-beta -- packages/py apps/api-python/src` | `auto_simulation_worker.py` **57/2** + `replay_oos.py` **13/1** (aportados por `v2.88.2`, no por este sello) |
| 7 | Contenido del tag | `git diff --name-status v2.88.2-beta v2.88.3-beta` | **13 ficheros** = 1 test + 1 script de mutaciones + `CHANGELOG` + `package.json` + 9 docs |
| 8 | El arreglo **no** oculta pruebas | `git diff v2.88.2-beta v2.88.3-beta -- <el test>` | **+5 líneas**: 4 de comentario + `worker._v2_owned_reservations = set()`; **0** `skip`/`xfail` |
| 9 | **No** se toca config ni CI | `git diff --name-only v2.88.2-beta v2.88.3-beta -- .github pyproject.toml` | **ninguno** |
| 10 | **No** se borra ni renombra ningún test | `git diff --diff-filter=DR --name-status v2.88.2-beta v2.88.3-beta` | **0** |
| 11 | La evidencia viaja entera | 660 enlaces relativos de los 5 docs clave, en el tag **y** en `main` | **0 roto** |
| 12 | CI del tag | `Release tag CI` [`36558405748`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36558405748) | **SUCCESS**, `attempt 1`, 8m29s |

**Lo que mide el CI del tag** (job `python`, el que tumbó `v2.88.2-beta`): `ruff` `All checks passed!` ·
`Contracts: 4 kept, 0 broken.` · `mypy` `508` ficheros · **`3040 passed, 37 skipped`** (0 fallos) — frente a
`3034 passed + 6 failed + 37 skipped` del objeto anterior. **`3040 + 37 = 3077`** recogidos = los mismos
`3077`. El job `lifecycle-pg` (crash/recovery real + **3 sesiones concurrentes** + golden day + aislamiento
por cuenta) quedó **verde** con **220 passed** en 8 invocaciones.

---

## 3. Trampas declaradas: lo que el auditor **NO** debe concluir (8)

1. **«El CI del tag no está acreditado.»** La cita **no puede** vivir dentro del tag: `Release tag CI` solo
   corre **al empujar**, así que es **POST-TAG** por construcción (patrón `OBS-3`/`OBS-4`). La copia sellada
   de `evidence/v2.88.3/README.md` dice literalmente `Pendiente de medir…` **a propósito**; la cita real
   está en `main` (`a6c44b77`, hash registrado en `e5e5a909`) y en §1.1 del arranque del auditor.
   *Verifícalo:* `git log --format=%h:%s -1 --grep "cita POST-TAG del CI del tag v2.88.3-beta"`.
2. **«La versión del objeto es `2.11.0-beta` / el tag es `v2.88-beta`.»** El **§2 del arranque del auditor**
   es la checklist de la fase de **ORIGEN** (`v2.88`) y sus puntos 1 y 8 citan valores de entonces. **El
   objeto vigente es `v2.88.3-beta` / `2.11.3-beta` y la matriz es `252`.** La reconciliación está en la
   tabla insertada al principio del §2 **en `main`** (la lista sellada **no** se reescribe).
3. **«El motor cambió en este sello.»** No: `v2.88.2-beta..v2.88.3-beta` sobre `packages/`/`apps/*/src` es
   **vacío** (comprobación 5). Lo que cambia es **un test de costura** y el **arnés de mutaciones**.
4. **«El arreglo relaja la prueba para que pase.»** El diff del test son **+5 líneas** (comentario +
   declaración del libro de propiedad), **sin** `skip`/`xfail` y **sin** tocar `pytest.ini`/workflows
   (comprobaciones 8-10). El CI mantiene los **mismos 37 skips**.
5. **«Falta la evidencia de `v2.86`/`v2.87` (o está manipulada).»** Los artefactos de `operability_runs/`
   son **gitignoreados** (`.gitignore:102`) y **no viajan en un clon**: cada evidencia lo **declara** con su
   **SHA-256**, su comando de regeneración y la exigencia de **RE-EJECUCIÓN**. No se afirma ningún número
   como reproducible sin volver a correrlo.
6. **«Los tags rojos anteriores estaban rotos y se han ocultado.»** Al contrario: los tres rojos
   (`36544461660`, `36548125321`, `36553839085`) se **conservan citados** en `evidence/v2.88/`,
   `evidence/v2.88.1/` y `evidence/v2.88.2/`. Este sello **arregla el último** y no reescribe los anteriores.
7. **Nota menor de higiene (declarada, no corregida):** la nota de contexto de `evidence/v2.86/README.md`
   dice que esa evidencia viaja en el tag `v2.88-beta`; describe el **tag de origen** (el sello conjunto) y
   se conserva **verbatim** dentro del tag. No afecta a ninguna cifra.
8. **Un enlace muerto PREEXISTENTE en el índice** (no lo introduce este sello): la entrada **132** de
   `engineering-index-2026-08-03.md` apunta a `./plan-v2.48-auto-8-adaptive-auto-2026-09-21.md`, que **no
   existe** en el repo (el `audit-pack` y el relevo de esa misma entrada **sí** existen). Es un enlace
   muerto de una fase antigua (`V2.48/AUTO-8`); se **declara**, no se reescribe el histórico. Un auditor que
   lo encuentre **no** debe concluir que se ha borrado evidencia.

---

## 4. Alcance sugerido de la auditoría

Por orden de valor:

1. **Que el arreglo sea el correcto y mínimo** (punto 3 de §3): 1 línea funcional en una **costura de test**,
   motor intacto, sin `getattr` defensivo (que convertiría un fallo de inicialización en **silencio**).
2. **Que la deuda viva esté declarada y no maquillada** (§8): `OBS-14.b`, `OBS-15`, `OBS-16`, `P3-2`/`P3-3`.
3. **Que el CI del tag acredite de verdad** el objeto (`36558405748`): los 10 jobs y `python` `3040/37`.
4. **Que la cobertura de mutación muerda el arreglo** (`M252`, matriz `252/252`) y que sus límites estén
   declarados (la pata de **salida** `_v2_reserve_exit` **no** tiene test ni mutación: declarado).
5. **Que nada de lo publicado dependa de material gitignoreado** que no viaja.

---

## 5. Reproducción en un clon fresco

```
git clone https://github.com/jvelasca/Bolsa_V1.git && cd Bolsa_V1
git checkout v2.88.3-beta                      # o trabaja en main para ver la cita POST-TAG

# Gate de estilo (el comando EXACTO del CI)
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter

# Batería offline COMPLETA (los 115 argumentos salen del propio workflow)
#   .github/workflows/release-tag-ci.yml :: step "Pytest offline"

# Matriz de mutaciones
uv run python apps/api-python/scripts/v2_44_mutation_audit.py            # 252/252, árbol intacto
uv run python apps/api-python/scripts/v2_44_mutation_audit.py --only M252
```

Los jobs que necesitan PostgreSQL (`lifecycle-pg`, `a7-gate`, `dr-verify`) se reproducen con el servicio
`postgres:16-alpine` del workflow; en local sin PG, esos tests se **saltan** (y se declaran).

---

## 6. Entregable esperado del auditor

Mismo formato que las auditorías externas previas del repo (p. ej.
[`auditoria-v2-84-auto-material-12-instrument-funnel-contract-2026-09-28.md`](./auditoria-v2-84-auto-material-12-instrument-funnel-contract-2026-09-28.md)):
un `docs/engineering/auditoria-v2-88-3-auto-material-16c-2026-09-XX.md` con

- **Veredicto**: `APROBADO` / `APROBADO CON OBSERVACIONES` / `RECHAZADO`;
- **Bloqueantes** (si los hay), cada uno con **evidencia reproducible** (comando + salida);
- **Observaciones** clasificadas por severidad, distinguiendo **deuda ya declarada** de **hallazgo nuevo**;
- **Lo que el auditor NO pudo medir** (declarado, no omitido);
- **Recomendación** de siguiente paso.

**Regla de la casa:** ninguna cifra sin comando; un hueco se declara **`NO MEDIDO`**, jamás un `0` fingido.

---

## 7. Prompt listo para pegar (auditor MIA externo)

```text
Actúa como auditor externo independiente. Auditas un repositorio PÚBLICO de GitHub:
https://github.com/jvelasca/Bolsa_V1

OBJETO: tag anotado v2.88.3-beta (objeto 66f47cf8e72449dc5bb907ef208abcc7afb0e857)
        -> commit 0038adfc, versión 2.11.3-beta, Alembic head 046_fill_reference_mid (sin migración).

PRIMERO lee, en este orden:
  1) docs/engineering/arranque-auditor-v2-88-auto-material-16-obs14-2026-09-29.md  (§1.1 y §2)
  2) docs/engineering/evidence/v2.88.3/README.md
  3) docs/engineering/obs-14c-costura-sin-atributo-v2.88.3-2026-09-29.md
  4) docs/engineering/entrega-auditoria-externa-mia-v2.88.3-2026-09-29.md  (trampas declaradas)

QUÉ AUDITAR (en este orden de valor):
  a) Que el arreglo sea mínimo y correcto: 1 línea funcional en una COSTURA DE TEST
     (worker._v2_owned_reservations = set()), MOTOR INTACTO. Verifícalo:
     git diff --stat v2.88.2-beta v2.88.3-beta -- packages/py apps/api-python/src   (debe estar vacío)
  b) Que el arreglo no oculte pruebas: git diff v2.88.2-beta v2.88.3-beta  ->  +5 líneas, sin skip/xfail,
     sin tocar config/CI, sin tests borrados.
  c) Que el CI del tag lo acredite de verdad: Release tag CI run 36558405748 -> SUCCESS en la primera
     pasada; job python 3040 passed / 37 skipped (0 fallos); lifecycle-pg verde (crash/recovery + 3
     sesiones concurrentes + golden day).
  d) Que la deuda viva esté DECLARADA y no maquillada: OBS-14.b, OBS-15, OBS-16, P3-2/P3-3.
  e) Que la cobertura de mutación muerda el arreglo (M252; matriz 252/252) y que sus LÍMITES estén
     declarados (la pata de salida _v2_reserve_exit no tiene test ni mutación).

REGLAS:
  - Trabaja sobre un clon fresco desde GitHub (repo público, sin credenciales).
  - NO aceptes ninguna cifra sin comando que la reproduzca.
  - Si algo no lo puedes medir, dilo explícitamente como NO MEDIDO; no lo estimes ni lo inventes.
  - No propongas reescribir el tag: es inmutable. Declara lo que veas, y separa HALLAZGO NUEVO de
    DEUDA YA DECLARADA.

QUÉ ENTREGAR: un informe con veredicto (APROBADO / APROBADO CON OBSERVACIONES / RECHAZADO),
bloqueantes con evidencia reproducible, observaciones por severidad, lo que NO pudiste medir y
la recomendación de siguiente paso.
```

---

## 8. Deuda viva que el auditor debe encontrar declarada (no oculta)

| ID | Severidad | Alcance | Estado |
| --- | --- | --- | --- |
| **`OBS-16`** | MEDIUM | proceso: 15 costuras `object.__new__` duplican a mano el estado del worker ⇒ todo atributo nuevo del `__init__` puede romper el job offline sin aviso local | **ABIERTA** (mitigación medida: correr la batería offline completa del workflow) |
| **`OBS-14.b`** | MEDIUM | motor: el barrido de **arranque** no distingue una huérfana de una reserva viva de otra sesión (reinicio rodante); discriminador posible **no implementado**: ventana de gracia por **edad** | **ABIERTA** |
| **`OBS-15`** | MEDIUM | motor: el techo de **1000** filas `APPLIED` (`read_applied_fill_facts`) puede enganchar `RECONCILIATION_FAILURE`; la retención de `900` de `v2.87` es mitigación **interna al instrumento**, no existe en producción | **ABIERTA** |
| **Pata de SALIDA sin cobertura** | — | `_v2_reserve_exit` registra propiedad pero **no** tiene test ni mutación dedicados (solo un docstring lo menciona) | **DECLARADA** |
| **`P3-2`/`P3-3`** | — | ventana PAPER **real** ≥4 días con material durable | **ABIERTAS** (este sello no las mide ni las mueve) |

**Límite de la evidencia de `v2.86`/`v2.87`:** son evidencia de **INVESTIGACIÓN**; exigen **RE-EJECUCIÓN** y
**no** son evidencia del edge del motor ni mueven `P3-2`/`P3-3`.
