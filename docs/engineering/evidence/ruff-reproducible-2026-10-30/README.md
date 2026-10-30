# Expediente B — Ruff reproducible (2026-10-30)

Cierra el gate de lint sin reformatear ~800 ficheros: el rojo masivo no era una deriva de
versión, era una invocación sin `--config`.

## Diagnóstico medido

Con `ruff 0.16.2` (la versión que ya resolvía `uv.lock`):

| Árbol | Comando | Resultado |
|---|---|---|
| base `c9e572cb` | `ruff check packages/py apps/api-python --config pyproject.toml` | **0 errores** |
| base `c9e572cb` | `ruff check packages/py apps/api-python` (sin `--config`) | **824 errores** (todos `I001`) |
| integración `06653971` | `ruff check packages/py apps/api-python --config pyproject.toml` | **2 errores** (`I001`) |
| integración `06653971` | sin `--config` | **828 errores** (todos `I001`) |

Causa: al recibir **directorios**, Ruff sin `--config` no resuelve el `pyproject.toml` de la
raíz y pierde `known-first-party`; entonces ordena los paquetes propios como terceros y
marca imports correctos como mal ordenados. `package.json` (`lint:py`) y el step `Ruff` del
CI ya pasaban `--config`; el target `lint` del `Makefile` **no**.

Solo hay 2 `I001` reales en el árbol integrado, y son de contenido integrado (en la base
común esos dos ficheros están limpios):

```
apps/api-python/tests/integration/test_accounts.py
apps/api-python/tests/integration/test_tax_report.py
```

## Qué se cambió

| Pieza | Fichero | Cambio |
|---|---|---|
| Pin | `pyproject.toml` (raíz) | `ruff>=0.9` -> `ruff==0.16.2` |
| Pin | `apps/api-python/pyproject.toml` | `ruff>=0.9` -> `ruff==0.16.2` |
| Lock | `uv.lock` | Regenerado: solo cambia el specifier; `ruff` sigue en **0.16.2** |
| Makefile | `Makefile` | `lint` usa `--config pyproject.toml` en `ruff check` y `format` |
| CI | `.github/workflows/python-ci.yml` | `uv sync --frozen` + guardia de versión de Ruff en el job `quality` |

```diff
-  "ruff>=0.9",
+  "ruff==0.16.2",
```

```diff
 lint:
-	uv run ruff check packages/py apps/api-python
-	uv run ruff format --check packages/py apps/api-python
+	uv run ruff check --config pyproject.toml packages/py apps/api-python
+	uv run ruff format --check --config pyproject.toml packages/py apps/api-python
```

La guardia del CI falla si el binario resuelto no es exactamente `ruff 0.16.2`, y
`uv sync --frozen` impide que una re-resolución cambie el motor sin tocar el manifiesto.

## Verificación (medida)

```
$ uv lock --check
Resolved 124 packages in 2ms                      # OK: lock coherente con los manifiestos

$ uv sync --frozen
Installed 124 packages                            # OK: instala exactamente el lock

$ .venv/Scripts/ruff --version
ruff 0.16.2

$ ruff check packages/py apps/api-python --config pyproject.toml
All checks passed!
```

`uv.lock` solo cambia en los specifiers:

```
 { name = "ruff", specifier = "==0.16.2" },
 ...
 name = "ruff"
 version = "0.16.2"
```

## Nota sobre los 2 `I001` del árbol integrado

La rama `chore/ruff-reproducible-2026-10-30` sale de `c9e572cb` (base común), donde esos
dos ficheros ya están limpios; el `I001` lo introduce el contenido fusionado. Por eso el
pin, el Makefile, el CI y la evidencia viajan en esta rama, y el reordenado exacto
(`ruff check --fix --config pyproject.toml` sobre los dos ficheros) se aplica en la
**fusión final** sobre la rama de integración, donde el defecto existe. Se corrige solo
esos dos ficheros: nada de `--fix` sobre el árbol completo.

El `ruff.txt` de la evidencia de integración estaba desincronizado (medido sin `--config`);
la auditoría final lo regenera con el comando exacto del CI.
