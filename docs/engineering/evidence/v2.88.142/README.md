# Evidencia `v2.88.142-beta` — «VIGÍA 2.0»: vigilancia verificable e independiente del stack (latido durable + arrastre de días perdidos + CLI/tarea `window:watch`)

> **Bump:** `2.11.141-beta` → **`2.11.142-beta`** (`package.json` + `meta.bump` del CLI OOS `v2_87`, de los 9 CLIs `v2_89`…`v2_97`, del certificador `v2_98`, del CLI `v2_99` y de `v2_100` — **13 scripts** en [`apps/api-python/scripts`](../../../../apps/api-python/scripts/); guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) **2 passed**).
>
> **Naturaleza:** incremento **de observabilidad + operación + documentación** sobre el **vigía** — **no** toca el motor de decisión, ni umbrales, ni pesos A/B, ni el contrato HTTP, ni el esquema: **`Δ motor = 0`** · **`Δ decisión = 0`** · **`Δ contrato HTTP = 0`** (`contract:check` **OK**) · **SIN migración** (head `055_dia_d_identity_nullable`). Tag **unsigned**.
>
> **Base:** `v2.88.141-beta`.

**Qué es este sello.** Cierra el hueco declarado el `16/10` a las 20:00 («debe estar siempre vigilando la operativa diaria»): el vigía del `.140` **sólo emitía log** (y el log del stack dev **no captura** los loggers `bolsa_api.*`) y **sólo miraba el día de HOY**, de modo que su vigilancia era **indemostrable desde fuera** y **ciega a los días perdidos con el equipo apagado**. Aquí se le dan **tres instrumentos** (latido durable, arrastre, CLI+tarea propia) y se **corrige** el hallazgo del `.141`, que se había medido con un instrumento ciego.

---

## 1. Corrección del hallazgo del `.141` (el instrumento, no el vigía)

### 1.1 Lo que decía el `.141`

> «Los dos arranques del `scheduler_worker` registran `Scheduler worker iniciado` y **ninguna** línea del vigía ⇒ **las 20:00 de hoy NO hubo vigilancia**».

### 1.2 Lo que se ha medido hoy (falsación del propio hallazgo)

| Medición | Comando / fuente | Resultado |
| --- | --- | --- |
| ¿El log dev captura **todo** el stderr del scheduler? | [`tee()`](../../../../scripts/run-dev.mjs) — `stream.on('data', …)` → `appendFileSync` **sin filtro** | **Sí**: cada chunk va íntegro a `logs/dev/dev-*.log` |
| ¿Ese fichero tiene líneas de ese proceso? | `logs/dev/dev-2026-10-16T21-57-43-859Z.log` (sesión del reinicio 23:57:48) | **Sí**: `[stderr] INFO:__main__:Scheduler worker iniciado` + líneas `alembic` |
| ¿Hay **algún** registro de un logger `bolsa_api.*` en `logs/`? | `rg "bolsa_api" logs/` | **0 coincidencias** en **todos** los ficheros de `logs/` |
| ¿El vigía **funciona**? (control positivo aislado) | `python -c "start_window_day_watch(None)"` (mismo intérprete/PYTHONPATH/cwd que `run-dev`) | **Sí**: `INFO:bolsa_api.background.window_day_watch_worker:WindowDayWatch iniciado (tick=900.0s; hora=20:00 Europe/Madrid)` |
| ¿El vigía está **registrado** en el scheduler del repo? | `scheduler_worker._event_loop_starters()` | **Sí**: **19 starters**, incluye `start_window_day_watch` |
| ¿Qué código ejecuta el **proceso vivo**? | `uvx py-spy dump --pid 31152` (arrancado 23:57:48) | `bolsa_api\workers\scheduler_worker.py:159` ⇒ **el módulo del repo** |

**Conclusión (declarada, sin adornos).** La ausencia de la línea del vigía en el log **no probaba** que el vigía no corriera: **ese sink nunca lleva registros `bolsa_api.*`**, así que era **ciego** justo para lo que se quería medir. Por tanto:

- **Se retira** la afirmación «a las 20:00 no hubo vigilancia» y la de «el proceso vivo no ejecuta el vigía»: **no estaban soportadas** por el instrumento.
- **Se declara el hallazgo real**, que sí es medible y sí importa: **(a)** el vigía **no dejaba rastro comprobable** (sólo log invisible + email que sólo sale si hay alerta), **(b)** **sólo miraba hoy** ⇒ un día perdido con el equipo apagado **no se avisaba nunca**, y **(c)** vivía **dentro** del stack ⇒ con el API/crons caído, **no vigila**.
- **Sigue medido** (y no cambia): el vigía es **on-by-default**, está **registrado**, y su decisión es **pura y falsable**.

---

## 2. Las tres piezas nuevas (y el arranque comprobable)

### 2.1 Latido durable — el instrumento

`operability_runs/window-runs/day-watch.json` (+ línea en `day-watch.jsonl`) en **cada tick**:

```json
{"alerts": [], "at": "2026-10-17T01:58:17.742703+02:00", "checks": [{"day": "20261017", "reason": null, "severity": "ok", "verdict": "NON_MARKET_DAY"}], "day": "20261017", "dayIso": "2026-10-17", "lookbackDays": 7, "message": "fin de semana: no es día de mercado", "reason": null, "severity": "ok", "source": "cli", "status": null, "verdict": "NON_MARKET_DAY"}
```

**Falsable sin logs y sin email:** si el fichero no avanza, el vigía **no** está corriendo. Escritura **best-effort** (un fallo se registra y **no** tumba el aviso). **Δ ventana = 0**: su única escritura es ese fichero propio; el ledger y el lock se **leen**.

### 2.2 Arrastre de días perdidos — `WINDOW_DAY_WATCH_LOOKBACK_DAYS`

- `evaluate_backfill(...)` (**puro**): días **laborables anteriores** sin fila en el ledger ⇒ `MISSED` (`reason=ledger_sin_dia_previo`), **mismo** aviso (log `ALERTA` + email).
- **Default `7`** días, tope `90`, `0` lo apaga (nuevo campo en [`config.py`](../../../../packages/py/infrastructure/src/bolsa_infrastructure/config.py)).
- **Anti-falso-positivo (baseline):** sólo mira **después de la primera fila** del ledger; con el ledger **vacío** no declara nada; **nunca** cuenta hoy ni fines de semana.

### 2.3 Vigilancia independiente del stack — `pnpm window:watch` + `BolsaV1_WindowWatch`

- `pnpm window:watch` ⇒ CLI `python -m bolsa_api.background.window_day_watch_worker --once` (opciones `--json`, `--lookback-days N`, `--now ISO`, `--no-persist`). **Exit `0`** sin aviso · **`3`** con día perdido/`HARD_ERROR` · `1` error.
- `pnpm window:task:install` registra **dos** tareas diarias (wrapper `.cmd`, el mismo fix de comillas del `.140`): `BolsaV1_WindowForward` (**18:00** → `window:run-day`) y **`BolsaV1_WindowWatch`** (**20:20** → `window:watch`). `--watch-at HH:MM` / `--no-watch`.
- **Instrumento extra:** `LastTaskResult = 3` en la tarea del vigía significa «hoy hubo aviso» (`schtasks /query`).

### 2.4 El primer tick ya no espera 15 minutos

El bucle **evalúa y escribe el latido ANTES de dormir** (antes: `sleep 900 s` → evaluar). Al arrancar el stack **ya hay veredicto escrito** ⇒ el arranque es comprobable de inmediato. La idempotencia pasa a ser **por aviso** (`{día}:{día-vigía}:{veredicto}` anunciado **una vez**): un `MISSED` **no** se repite cada tick (**sin spam de email**) mientras el **latido** sí se reescribe (**prueba de vida**).

---

## 3. Verificación (medida, con los comandos del CI)

| Comprobación | Comando | Resultado |
| --- | --- | --- |
| Vigía + guardián + scheduler | `pytest tests/test_window_day_watch.py tests/test_dia_d_bump_guard.py tests/test_scheduler_worker.py -q` | **40 passed** |
| Runner de la ventana (JS) | `pnpm window:test` | **28 passed** |
| Ruff (paridad CI) | `pnpm lint:py` | **`All checks passed!`** |
| Import-linter (paridad CI) | `pnpm imports:py` | **`Contracts: 4 kept, 0 broken.`** |
| Mypy (paridad CI) | `pnpm types:py` | **`Success: no issues found in 557 source files`** |
| Congelación | `pnpm window:freeze` | **OK** tras el re-anclaje del sello — `apps` `446f198b…` (**movido**: el árbol pinado de `apps/` incluye `apps/api-python/src` **y** `apps/api-python/tests`) / `packages` `6377a7a2…` (**movido** por el campo nuevo de `config.py`) |
| Vigía **real** (end-to-end, sin stack) | `pnpm window:watch` | `2026-10-17 · NON_MARKET_DAY` (sábado) + **latido escrito** (`source: cli`), exit **0** |
| Dry-run de la cadencia | `pnpm window:task:install --dry-run` | 2 líneas: `BolsaV1_WindowForward … /st 18:00` y `BolsaV1_WindowWatch … /st 20:20` |

**Tests nuevos (20 → 36 en el fichero del vigía):** arrastre (previos laborables, fin de semana fuera, **baseline**, ledger vacío, `0` apagado, fila presente y hoy excluidos), arrastre **también** avisa por email, latido (`day-watch.json` + `journal` + `alerts[]`), parseo/clamp de `WINDOW_DAY_WATCH_LOOKBACK_DAYS`, `_tick` (**latido sí / aviso no repetido**) y CLI (`--help`, desactivado, `MISSED` ⇒ **3**, `VETO` ⇒ **0**, `--no-persist`, `--json`).

Los ficheros de test del vigía **ya se recogen por directorio** en el job offline del CI ([`release-tag-ci.yml:961`](../../../../.github/workflows/release-tag-ci.yml), `apps/api-python/tests`) ⇒ **no** requieren alta explícita.

---

## 4. Límites declarados (sin fabricar)

- **La ventana PAPER real sigue sin medirse:** ledger `20261014/15/16` = `NO_MEDIDO_REGIMEN` (veto **`BEAR_TREND`**) ⇒ **`0/4` días · `0/2` regímenes · `0/32` ciclos ⇒ `INCONCLUSIVE`**. Falta **OPERACIÓN**, no software ⇒ **no demuestra rentabilidad**.
- **El vigía NO mide la ventana:** no lanza `run-day`, no baja umbrales, no fuerza régimen, no escribe en el journal/ledger. **Δ motor = 0 · Δ decisión = 0.**
- **El email** depende de SMTP + destinatario configurados; si faltan, el aviso queda en el **log** y en el **latido** (nunca en silencio).
- **El latido vive bajo `operability_runs/`** (ignorado por git): su **ausencia no se ve** en `git status`; hay que mirarlo con `Get-Content operability_runs/window-runs/day-watch.json`.
- El arrastre **no inventa pasado**: sólo alerta de días **posteriores a la primera fila** del ledger.
- La ventana avanza **un día de pared por corrida**; el vigía no lo cambia. Tag **unsigned**.

---

## 5. Reproducción

```powershell
pnpm lint:py ; pnpm imports:py ; pnpm types:py          # paridad con el CI
pnpm window:test                                        # 28 (runner JS)
cd apps/api-python ; python -m pytest tests/test_window_day_watch.py tests/test_dia_d_bump_guard.py tests/test_scheduler_worker.py -q
pnpm window:watch                                       # evaluación real + latido (exit 0/3)
pnpm window:task:install --dry-run                      # 2 tareas (18:00 + 20:20)
Get-Content operability_runs/window-runs/day-watch.json # instrumento: ¿vigiló?
```

## 6. Cita POST-TAG — CI del sello

Pendiente de cierre: el `Release tag CI` del tag `v2.88.142-beta` se monitoriza tras publicarlo y su run **se cita aquí** (con `conclusion`) junto al `Python CI` de `main`. Si algún job queda **rojo**, este sello **no** se da por bueno (disciplina: el CI es la medida, no la opinión).
