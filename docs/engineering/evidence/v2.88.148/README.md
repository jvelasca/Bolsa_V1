# Evidencia `v2.88.148-beta` — el artefacto DÍA-D se escribe y se lee en el MISMO sitio (un solo resolvedor honra `DIA_D_AUTO_DIR`)

> **Bump:** `2.11.147-beta` → **`2.11.148-beta`** (`package.json` + `meta.bump` de los **13** CLIs;
> guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) **en verde**).
> Tag **unsigned**.
>
> **Cambio:** coherencia escritor↔lector del artefacto DÍA-D + regresión falsable. **`Δ motor = 0`** ·
> **`Δ decisión = 0`** · **`Δ contrato HTTP = 0`** (`openapi.json`/`schema.d.ts` **sin diff**) ·
> **SIN migración** (head `056_auto_ops_jobs`).

## 1. El defecto (medido al verificar el `.147`, no inferido)

Al cerrar el `.147` se reinició el stack y se encoló un `dia_d_replay` real. El job terminó
**`completed`** y el artefacto quedó en disco:

```text
operability_runs/dia-d-auto/default-account-seed/dia-d-auto-2026-01-02.json   (5 588 B)
```

Pero la lectura HTTP devolvía:

```text
GET /api/auto/dia-d-replay/2026-01-02 → available=false · notes=["artifact_not_found"]
GET /api/auto/dia-d-replay            → days=[]
```

Causa medida: `DIA_D_AUTO_DIR` lo honraban **sólo** las rutas de lectura
([`auto_dia_d.py`](../../../../apps/api-python/src/bolsa_api/api/v1/routes/auto_dia_d.py) y
[`auto_dia_d_feedback.py`](../../../../apps/api-python/src/bolsa_api/api/v1/routes/auto_dia_d_feedback.py)),
mientras el worker escribía siempre bajo `_repo_root()`
([`auto_ops_dia_d.py`](../../../../apps/api-python/src/bolsa_api/background/auto_ops_dia_d.py)).
Con la variable informada, **escritor y lector apuntan a árboles distintos** y la UI declara «sin
artefacto» **sin ningún error visible**: el fichero existe, el job está `completed` y no hay señal
de fallo en ninguna superficie.

## 2. El arreglo (un solo resolvedor)

[`dia_d_artifacts.py`](../../../../packages/py/application/src/bolsa_application/dia_d_artifacts.py):

- NUEVO `artifacts_root(default_root, environ)`: devuelve `DIA_D_AUTO_DIR` si viene informada y
  `default_root` si no; **vacío o en blanco cuenta como ausente**. El `environ` se pasa **explícito**
  para que el módulo siga siendo puro y la resolución sea falseable.
- NUEVOS `artifact_path_in(artifacts_dir, day, account)` y `progress_path_in(artifacts_dir, job, account)`:
  construyen bajo la carpeta **ya resuelta** (`…/dia-d-auto`), sin volver a prefijar
  `operability_runs/dia-d-auto`.
- `artifact_path`/`progress_relpath` conservan su semántica (raíz del repo) para los consumidores que
  ya los usaban.

Consumo:

- Worker: `artifacts_dir_for_jobs()` = `artifacts_root(_repo_root() / DIA_D_ARTIFACT_DIR, os.environ)`;
  `out_path` y `progress_file` salen de `artifact_path_in`/`progress_path_in`.
- Rutas HTTP: `_artifacts_dir()` usa el mismo helper (se elimina la copia local de la regla).
- `_display_path`: si el override deja el artefacto **fuera** del repo, el resultado declara la ruta
  **absoluta**; antes `relative_to(root)` habría lanzado `ValueError` al formatear el resultado.

## 3. Regresión falsable

[`test_auto_dia_d_route.py`](../../../../apps/api-python/tests/test_auto_dia_d_route.py) —
`test_escritor_y_lector_resuelven_la_misma_raiz`:

- con `DIA_D_AUTO_DIR` informada, `worker.artifacts_dir_for_jobs() == route._artifacts_dir()` y la
  ruta del artefacto del worker es **idéntica** a la de la ruta HTTP;
- sin la variable (y con la variable en blanco) ambas caen en la **misma** carpeta por defecto.

**Comprobado que es falsable:** con la implementación anterior, la ruta del worker y la del lector
diferían (`…\Bolsa_V1\operability_runs\dia-d-auto\…` vs `…\Temp\<dir>\…`) ⇒ el test habría fallado.

## 4. Verificación medida (worker real en Windows)

Stack reiniciado con el código nuevo (`pnpm dev`; el proceso anterior era anterior al arreglo del
`.147`) y dos jobs encolados por la **cola durable**:

| Comprobación | Resultado |
| --- | --- |
| Job `dia_d_replay` (2026-01-02) | **`completed`** · `6,1 s` · `watchSize 20` · `verdict DIVERGENT` |
| Segundo job, mismo día/cuenta | **`completed`** · `6,1 s` · ruta idéntica |
| Artefacto | `operability_runs/dia-d-auto/default-account-seed/dia-d-auto-2026-01-02.json` |
| Progreso | `…/progress/<job>.jsonl` (uno por job) |
| Lectura HTTP (cuenta propia) | `available=true` · **9 pasos** · `notes=[]` · `days=[2026-01-02]` |
| Frescura | `artifactModifiedAt` **avanza** con la segunda corrida (`08:46:46Z` → `08:48:14Z`) |
| `NotImplementedError` en el log nuevo | **0** |

## 5. Paridad y pruebas

| Comando | Resultado |
| --- | --- |
| `python -m pytest test_auto_dia_d_route test_auto_ops_dia_d test_auto_daily_dia_d_chain_integration test_auto_dia_d_feedback_route` | **32 passed** |
| `python -m pytest apps/api-python/tests packages/py` (completa; `--ignore` del módulo bloqueado) | **5799 passed / 1 skipped** (11m58s) |
| `python -m pytest test_dia_d_bump_guard` | **2 passed** |
| `pnpm lint:py` | **`All checks passed!`** |
| `pnpm imports:py` (por `python -m`, app-control) | **`4 kept, 0 broken`** |
| `pnpm types:py` | **`Success: no issues found in 566 source files`** |

### Límites del entorno (declarados, no ocultados)

- El **control de aplicaciones de Windows** bloquea `lint-imports.exe` (`os error 4551`) y la carga de
  `llvmlite.dll`: import-linter se ejecutó por su entrypoint de módulo y `test_vectorbt_optuna` se
  **ignora** en la corrida completa (el CI Linux los corre completos).
- La variable `DIA_D_AUTO_DIR` que destapó el hallazgo era **residuo de depuración del shell**, no
  configuración del producto; el defecto se reprodujo igual con ella puesta y desaparece con el
  arreglo (el worker y el lector coinciden **con y sin** override).

## 6. Invariantes que NO cambian

- **SIM-only:** ninguna orden real; la operativa sigue contra ledger virtual/PAPER.
- **Decisión:** sin umbrales, reparto, `TOP_N`, régimen, protección ni ejecución tocados.
- **Contrato HTTP:** `openapi.json`/`schema.d.ts` **sin diff**; `contract:check` **OK**.
- **Ventana PAPER:** `window:status` ⇒ **`3` días de ventana · `0` medidos** (`NO_MEDIDO_REGIMEN` por
  `BEAR_TREND` en `20261014/15/16`; `2` no-mercado) ⇒ gate **`NO_MEDIDO`** ⇒ **no demuestra
  rentabilidad**.

## 7. Publicación

Commit funcional + bump y re-anclaje del pin (`window:pin --write`) → `window:freeze OK`.
Tag `v2.88.148-beta` (**anotado, unsigned**) y `Release tag CI`.
