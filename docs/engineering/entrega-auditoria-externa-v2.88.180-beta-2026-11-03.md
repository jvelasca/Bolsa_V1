# Entrega para auditoría externa — `v2.88.180-beta`

> **Objeto entregado:** tag anotado `v2.88.180-beta` (identidad en §7, medida POST-TAG).
> **Rama:** `seal/v2.88.180-beta` (**no** `main`).
> **Naturaleza:** **acto de publicación**. Publica el bloque **C-1** (lecturas tipadas de la cadena y
> `readGaps`) con su evidencia y su certificación de integración. No reabre `.179`, no cambia motor ni
> decisión, y **no** abre PR ni fusiona a `main`.
> **Para quién:** auditor externo que no conoce la historia del repositorio y necesita un punto de entrada
> único, verificable y con sus límites escritos.

---

## 0. Qué recibe el auditor (y qué no)

Este documento **no** es un dictamen. Es un **índice verificable** de un expediente y una declaración
explícita de procedencia: qué se midió, qué se cita y qué queda fuera.

| Afirmación | Procedencia | ¿Re-verificada al escribir esto? |
| --- | --- | --- |
| `origin/main` = `26250187` y su `package.json` está en `2.11.160-beta` | `git log origin/main`, `git show origin/main:package.json` | **Sí** |
| `origin/main` es **ancestro** de esta rama (185 commits de distancia) | `git merge-base --is-ancestor` + `git rev-list --left-right --count` | **Sí** |
| La base del sello es `0f3ac4a7` (tronco de `.179`) | `git log --oneline 0f3ac4a7..HEAD` | **Sí** |
| El bump deja `package.json` en `2.11.180-beta` y `freeze OK` | `git show`, `pnpm window:freeze` | **Sí** |
| CI, recuentos de suites y límites de §6 | **Evidencia aportada** en [`evidence/v2.88.180/README.md`](./evidence/v2.88.180/README.md) | **No**: se acepta como evidencia aportada |
| `Release tag CI` y GitHub Release de **este** sello | Medidos POST-TAG; citados en §7 | **Sí** (§7) |

Consecuencia práctica: lo verificable **sin confiar en nadie** es la **identidad del objeto**, el **alcance del
diff** y la **posición de `main`**. Lo relativo a la corrida local de pruebas se acepta como **evidencia
aportada** por quien lo firmó, y el `Release tag CI` del tag lo re-mide en infraestructura del repositorio.

---

## 1. Índice del expediente (todo dentro del árbol del tag)

| Documento | Qué es |
| --- | --- |
| [`evidence/v2.88.180/README.md`](./evidence/v2.88.180/README.md) | Evidencia del sello: contrato, corrección del test, matriz de verificación y límites |
| [`dictamen-cierre-c1-2026-11-03.md`](./dictamen-cierre-c1-2026-11-03.md) | Dictamen de cierre de C-1 y de sus dos deudas |
| [`evidence/certificacion-pg-c1-ds1-o2-2026-11-03/README.md`](./evidence/certificacion-pg-c1-ds1-o2-2026-11-03/README.md) | Certificación PostgreSQL (con nota de alcance: aquí solo se acreditan las filas de C-1) |
| [`evidence/certificacion-pg-c1-ds1-o2-2026-11-03/deuda-multiproceso.md`](./evidence/certificacion-pg-c1-ds1-o2-2026-11-03/deuda-multiproceso.md) | Diagnóstico del defecto de sincronización del test multiproceso |
| [`evidence/certificacion-pg-c1-ds1-o2-2026-11-03/flaky-lab-discovery.md`](./evidence/certificacion-pg-c1-ds1-o2-2026-11-03/flaky-lab-discovery.md) | Cierre del flaky y su red de determinismo |
| [`evidence/v2.88.131/README.md`](./evidence/v2.88.131/README.md) §10 | Contrato de `readGaps`: semántica por etapa, compatibilidad y propagación |
| [`CHANGELOG.md`](../../CHANGELOG.md) §`2.11.180-beta` | Declaración del acto de publicación |
| `.github/workflows/python-ci.yml` · `.github/workflows/release-tag-ci.yml` | Cableado del gate `AUTO_CHAIN_READ_GAPS_PG_REQUIRED` y del paso anti-skip |

---

## 2. Qué cambia el sello (y qué no)

| Elemento | Antes (`2.11.179-beta`) | Ahora (`2.11.180-beta`) |
| --- | --- | --- |
| Fallo de lectura de propuestas | indistinguible de «sin propuesta» | declarado en `readGaps` y atribuido `unmeasured` |
| Ficha de la cadena | sin superficie para el hueco de lectura | aviso `data-read-gaps` con etapa y motivo |
| Certificación de `readGaps` | offline (dobles) | PostgreSQL real, 6 pruebas, gate fail-if-skipped |
| Test multiproceso | esperaba «cola viva» (no converge con fill completo) | espera la materialización real de la trancha |
| Determinismo del pipeline declarativo | sin red ejecutable | test de identidad entre corridas |
| Motor / decisión / migraciones | — | **sin cambio** (`Δ motor = 0`, `Δ decisión = 0`, head `062`) |

---

## 3. Cómo verificarlo sin confiar en este documento

```powershell
git fetch origin --tags
git rev-parse v2.88.180-beta^{}                 # commit del tag
git cat-file -p v2.88.180-beta                  # objeto anotado + mensaje
git merge-base --is-ancestor origin/main v2.88.180-beta; $LASTEXITCODE   # 0 = main es ancestro
git show v2.88.180-beta:package.json | Select-String '"version"'         # 2.11.180-beta
git diff --stat 0f3ac4a7 v2.88.180-beta         # alcance completo del sello
git grep -n "readGaps" v2.88.180-beta -- packages apps                   # la superficie publicada
git grep -n "AUTO_CHAIN_READ_GAPS_PG_REQUIRED" v2.88.180-beta -- .github # el cableado del gate
```

Y para re-medir lo que no depende de CI:

```powershell
$env:DATABASE_URL='postgresql://bolsa:bolsa_dev@127.0.0.1:5432/bolsa_v1'
$env:AUTO_CHAIN_READ_GAPS_PG_REQUIRED='1'
.\.venv\Scripts\python.exe -m pytest apps/api-python/tests/test_auto_chain_read_gaps_pg.py -q -rs
```

---

## 4. Límites declarados (heredados, no reabiertos)

- `L-180-1`: la matriz PG combinada se midió sobre un árbol con DS-1 y O-2; este tag acredita **solo** las filas
  de C-1.
- `L-180-2`: la corrección del test multiproceso es **del test**, no una nueva certificación del mecanismo
  productivo de reservas.
- `L-180-3`: `readGaps` cubre las etapas con lector tipado; toda etapa nueva debe traer su contrato y sus pruebas.
- `L-180-4`: el dwell de FASE 2 sigue fijo en 30 s; no se parametriza sin prueba de seguridad.

---

## 5. Qué queda fuera de este sello

- **DS-1** (lease/reaper de `scan_jobs`), **O-2** (savepoint del sumidero de propuestas), **H-1** y **GP-V190**:
  su código y sus pruebas **no** están en este árbol.
- Las **56 entradas** pendientes del árbol de trabajo de desarrollo (no commiteadas) no forman parte del tag.
- **AUTO** sigue **OFF** y **PAPER** sigue **INCONCLUSIVE**: el sello no aporta evidencia de resultados.
- No hay PR ni fusión a `main`; `main` sigue en `26250187` (`2.11.160-beta`).

---

## 6. Qué no se acepta como cerrado por este acto

1. Las suites completas: las re-mide el `Release tag CI` del tag, no esta entrega.
2. La rentabilidad ni la operativa real: son OPERACIÓN y medición longitudinal.
3. El determinismo del pipeline declarativo **fuera** de la vía cubierta por el test nuevo.
4. Cualquier etapa de la cadena sin lector tipado: `readGaps` no la declara por existir.

---

## 7. POST-TAG (identidad y corrida)

Medido en un descendiente del tag, para que el acto no se certifique a sí mismo:

| Dato | Valor |
| --- | --- |
| Objeto del tag | `037c3656293a56c0e436c600a873f694050bb247` |
| Commit apuntado | `92d66fc41b56b62c0a6824f9211611966f37c1b3` |
| `Release tag CI` | [41683440085](https://github.com/jvelasca/Bolsa_V1/actions/runs/41683440085) → **`failure`** |
| Paso `Pytest C-1 readGaps (PG, fail if skipped)` | **success** (y su guarda anti-`SKIPPED`, sin disparar) |
| Job `python (ruff/imports/mypy/pytest offline)` | **failure**: 3 `FAILED` por `connection refused` a PostgreSQL en un job sin PostgreSQL |
| Job `certify (aggregate + artifact)` | **failure** (agrega el anterior) |
| GitHub Release | **NO creada** (un rojo no publica release; precedente `.177`/`.178`) |

**Causa del rojo (no es C-1).** El commit de cableado `c9eaeeaf` metió comentarios `#` **dentro** del bloque
plegado `run: >` de las listas de `--ignore` de `release-tag-ci.yml` y `python-ci.yml`. En un escalar plegado el
`#` es texto del comando: comentó el resto de la lista y el job offline empezó a recoger ficheros que exigen
PostgreSQL. Se descartaron **44** exclusiones en el tag CI (48 de 92 honoradas) y **45** en `Python CI` (52 de 97).
El detalle, las cifras y los tres runs afectados están en
[`evidence/v2.88.180/README.md`](./evidence/v2.88.180/README.md) §10.

**Consecuencia declarada.** El tag `v2.88.180-beta` queda publicado y **rojo**; la certificación de C-1 sí quedó
verde en `lifecycle-pg`. La corrección va en un sello **`.181`** —comentarios fuera del bloque y una prueba que
impida la recaída— sin reabrir C-1 y sin mover este tag.

