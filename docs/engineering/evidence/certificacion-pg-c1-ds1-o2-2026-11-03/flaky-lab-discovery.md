# Cierre del flaky de `test_lab_discovery_dispatch.py`

**Fecha:** 2026-11-03 · **Fichero:** `packages/py/application/tests/test_lab_discovery_dispatch.py`

## Qué reportó la auditoría

> `test_lab_discovery_dispatch` — «Falla en suite, pasa aislado» — *Flaky pendiente de explicación*.

El dictamen no cerraba el bloque con un flaky sin explicar. Esto es la reproducción, el
descarte y el cierre.

## Qué se intentó reproducir

| Escenario | Ejecuciones | Fallos |
| --- | --- | --- |
| Fichero aislado | 25 | 0 |
| Fichero aislado bajo carga fuerte de CPU (dos suites completas en paralelo) | 12 | 0 |
| `PYTHONHASHSEED` = 0…39 (orden de `set`/`dict`) | 40 | 0 |
| Con la política `WindowsSelectorEventLoopPolicy` importada de otro módulo (efecto colateral que otros tests PG aplican al importarse) | 4 | 0 |
| Suite completa `packages/py/application/tests` (3107 tests) | 3 | 0 |

**Total: 84 ejecuciones, 0 fallos.** No se reprodujo.

## Por qué el fichero no puede ser flaky por azar

El fichero es hermético y no tiene ninguna fuente de no-determinismo:

- **Sin BD, red ni ficheros.** Los dobles son `_Instruments`, `_Ohlcv` y dataclasses locales.
- **Sin reloj.** Las barras llevan `timestamp=f"2026-{i:04d}"` y el código compara cadenas; no se
  usa `now()`.
- **Sin aleatoriedad.** No hay `random` ni `np.random` en el camino declarativo: el grid sale de
  `iter_param_points`, documentado como «producto cartesiano determinista (orden de las claves
  del mapping)».
- **Sin paralelismo con estado compartido.** `_run_in_thread_with_live_progress` usa
  `asyncio.to_thread` con una función pura y un `on_progress` que no muta nada.
- **Sin mutación del input.** `definition` se reconstruye con un helper en cada test; no se
  encontró ninguna escritura in situ en `optimize.py` ni en `rules_grid.py`.
- **Sin orden de `set`.** `pbo.py` usa `set(is_idx)` solo para pertenencia; el recorrido real es
  `itertools.combinations`, y `np.argmax` resuelve empates por el primer máximo (índice estable).

Un fallo «a veces» en este fichero solo podría venir de un resultado no determinista dado el
mismo input. No hay ninguno.

## Qué se cambió

Se añadió `test_the_declarative_pipeline_is_deterministic_across_runs`: ejecuta el MISMO caso dos
veces en el mismo proceso y exige identidad exacta de `engine`, `baseline`, `trials` (params,
score y OOS), `cpcv`, `walkForward` y `pbo`, con un control mínimo (`cpcv is not None` y
`trials` no vacío) para que la igualdad no sea trivial.

Esto convierte la duda abierta en una **aserción ejecutable**: si alguien introduce orden de
`set`, muestreo con `random` o una mutación del `definition` compartido, el fallo aparece aquí,
determinista y con nombre y apellidos, en vez de como un flaky intermitente en otra máquina.

Resultado: `9 passed` (los 8 previos + el nuevo).

## Conclusión

No hay causa raíz que corregir en el código: **el fichero es determinista y no se reprodujo en
84 ejecuciones**. La observación «falla en suite» es más consistente con el entorno de la
auditoría que con el test — el mismo informe declara que ese entorno **no podía cargar `libpq`**
y que sus 125 errores de colección eran ambientales. Un proceso con la cadena de `psycopg`
rota puede fallar de formas que no se reproducen con `.venv` (Python 3.12 + `psycopg` 3.3.4
binario), que es el intérprete con el que se ejecutó esta evidencia.

Lo que sí queda cerrado, y ya no depende de reproducir un evento único, es la garantía de
determinismo: el test nuevo la vigila en cada corrida.
