# Evidencia `v2.88.147-beta` — el replay DÍA-D por cola ya funciona en Windows (Popen portable) y el E2E integrado cubre la UI diaria y el aislamiento por cuenta

> **Bump:** `2.11.146-beta` → **`2.11.147-beta`** (`package.json` + `meta.bump` de los **13** CLIs; guardián
> [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) **en verde**). Tag **unsigned**.
>
> **Cambio:** arreglo de plumbing del worker (`dia_d_replay`) + pruebas integradas. **`Δ motor = 0`** ·
> **`Δ decisión = 0`** · **`Δ contrato HTTP = 0`** (`openapi.json`/`schema.d.ts` **sin diff**) ·
> **SIN migración** (head `056_auto_ops_jobs`).

## 1. El defecto (medido, no inferido)

En Windows `scheduler_worker` fuerza `SelectorEventLoop` porque `psycopg` async no funciona en
`ProactorEventLoop`. Ese bucle **no implementa** `asyncio.create_subprocess_*`:

```text
auto_ops_dia_d.py:197  process = await asyncio.create_subprocess_exec(...)
asyncio/base_events.py:528  _make_subprocess_transport → raise NotImplementedError
auto_ops_job <id> falló inesperadamente
→ job failed · error "NotImplementedError: "
```

Consecuencia medida: **todo** job `dia_d_replay` fallaba en Windows y **nunca** generaba artefacto;
`estudio_daily` no se veía afectado (no lanza subproceso). El botón «Ejecutar DÍA-D ahora» de la UI
quedaba inservible en local, y el E2E `S5-07` no podía comparar dos artefactos.

## 2. El arreglo

[`auto_ops_dia_d.py`](../../../../apps/api-python/src/bolsa_api/background/auto_ops_dia_d.py):

- `subprocess.Popen` lanzado en un hilo (`asyncio.to_thread`), **sin shell**.
- `stdout`/`stderr` a **ficheros temporales**: el hijo nunca se bloquea por un pipe lleno.
- Espera por `poll()` desde el bucle, `kill()` al vencer el timeout y `wait(15)` para el reaping.
- Progreso y latido publicados en sesiones cortas (best-effort: un fallo de BD no tumba el job).
- Se conserva el contrato de validación: `exit 0` + artefacto existente + `day` + `meta.account`.
- `stderr` tail acotado (4 000 caracteres), con caída a `stdout` si aquel viene vacío.

## 3. Regresión falsable

- [`test_auto_ops_dia_d.py`](../../../../apps/api-python/tests/test_auto_ops_dia_d.py): dobles
  **síncronos** de `Popen` (`poll`/`wait`/`kill`) y NUEVO
  `test_no_depende_de_subprocesos_asyncio` — si el handler vuelve a `create_subprocess_*`, **falla**.
- [`test_auto_daily_dia_d_chain_integration.py`](../../../../apps/api-python/tests/test_auto_daily_dia_d_chain_integration.py):
  el doble del CLI se instala en `_spawn_process` (antes `asyncio.create_subprocess_exec`).

## 4. E2E integrado (`gp-v288-s5`, opt-in)

[`gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts`](../../../../apps/web/e2e/gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts):

- **S5-06 — UI diaria real** (`/auto-monitor?mode=daily`): leyenda «Decisión propuesta · no es una
  orden» y **cero** «Plan disparado»; el botón encola el **mismo** job durable (`estudio_daily`, leído
  por `/api/auto/ops-jobs`); «Actualizar» del panel produce **0** peticiones a
  `/api/auto/operational-monitor` (el global no existe en ese modo); la ficha enlaza a DÍA-D con
  `day`+`symbol` y el panel declara **contexto global**, no validación individual.
- **S5-07 — aislamiento por cuenta en el borde HTTP**: A (fixture) y B encolan el mismo día; **C**
  (control negativo) nunca encola. Se exige que cada artefacto declare su `meta.account`/`day`, que C
  no vea ni liste el día ajeno, y que A/B no compartan artefacto. Sin artefactos, se **declara** con
  anotación (`hueco-entorno`), nunca se finge.
- Teardown: las cuentas extra se cierran y borran con verificación (no-residuo).

## 5. Verificación medida (local, comandos de casa)

| Comando | Resultado |
| --- | --- |
| `python -m pytest apps/api-python/tests -q -k "auto or dia_d"` | **708 passed** (1 warning de limpieza preexistente) |
| `python -m pytest test_auto_ops_dia_d test_auto_dia_d_route test_auto_daily_dia_d_chain_integration` | **22 passed** |
| Sonda REAL del handler en `SelectorEventLoop` (CLI real, `--at 2026-01-02`) | **OK** · `verdict DIVERGENT`, `watchSize 20`, `6.1 s`; artefacto de sonda eliminado |
| `pnpm lint:py` | **`All checks passed!`** |
| `pnpm imports:py` (por `python`, app-control) | **`4 kept, 0 broken`** |
| `pnpm types:py` (por `python -m mypy`) | **`Success: no issues found in 566 source files`** |
| `playwright test gp-v288-s5` (`E2E_INTEGRATION=1 E2E_RUN=1 E2E_ALLOW_DEV_DB=1`) | **7/7 passed** (39,1 s) |

### Límites del entorno (declarados, no ocultados)

- El **control de aplicaciones de Windows** bloquea `mypy.exe`/`lint-imports.exe` (`os error 4551`):
  se ejecutaron por `python -m` / entrypoint de módulo.
- La comparación de **dos artefactos** en `S5-07` requiere worker + barras. En la corrida local el
  replay de ese día terminó `failed` en el worker **antiguo** (proceso ya arrancado con el código
  anterior) y se declaró con anotación; la sonda directa con el código nuevo sí generó artefacto.
- El stack local debe **reiniciarse** para que el worker cargue el arreglo.

## 6. Invariantes que NO cambian

- **SIM-only:** ninguna orden real; la operativa sigue contra ledger virtual/PAPER.
- **Decisión:** sin umbrales, reparto, `TOP_N`, régimen, protección ni ejecución tocados.
- **Contrato HTTP:** `openapi.json`/`schema.d.ts` **sin diff**; `contract:check` **OK**.
- **Ventana PAPER:** sigue **`0/4 días`, `0/2 regímenes`, `0/32 ciclos` ⇒ `INCONCLUSIVE`** (hoy
  `BEAR_TREND` con `entriesAllowedLong=false`) ⇒ **no demuestra rentabilidad**.

## 7. Publicación

- Commit funcional + bump y re-anclaje del pin (`window:pin --write`) → `window:freeze OK`.
- Tag `v2.88.147-beta` (**anotado, unsigned**) y `Release tag CI` — pendiente de ejecución en este
  documento; se citará el run al publicarse.
