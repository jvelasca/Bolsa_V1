# `StackReady` y el árbol de procesos del Programador — prueba del 2026-11-09

**Fecha:** 2026-11-09, 12:18-12:32 (local, `Europe/Madrid`)
**Objeto:** el riesgo declarado en el cierre de auditoría: si el Programador de tareas cierra
el árbol de procesos al terminar `BolsaV1_StackReady`, el `pnpm dev` que arranca moriría a
continuación y el API no llegaría vivo a las 17:40 (`BarsSync`) ni a las 18:30 (`run-day`).
**Veredicto: el riesgo NO se materializa** con la tarea tal como está registrada. El stack
sobrevivió **13 minutos** con `ready` 200 y los mismos PID, después de que la tarea saliera
con código 0.

---

## 1. Estado de partida

| Elemento | Valor |
| --- | --- |
| Stack en marcha | `pnpm dev:auto` (cmd raíz PID 11192, creado 10:03:18), log `operability_runs/window-runs/20261109/dev-auto.log` |
| API | PID 9992 en `0.0.0.0:8000`, `/api/health/ready` → **200**, esquema en head `066_account_evidence_policy` |
| Web (Vite) | en **5173** (PID no capturado antes de parar) |
| Puente XTB mock | PID 18988 en **3002** |
| `BolsaV1_StackReady` | Estado `Listo`, **último resultado 267011** (`0x41303`: nunca ejecutada) |
| `ExecutionTimeLimit` | `72:00:00` (el valor por defecto; no es un límite de minutos) |
| `LogonType` / `MultipleInstancesPolicy` | `InteractiveToken` / `IgnoreNew` |
| `StartWhenAvailable` / `WakeToRun` | `true` / `true` |
| Registro `Microsoft-Windows-TaskScheduler/Operational` | **deshabilitado** (`enabled: false`) |

## 2. Procedimiento y resultado

1. **Parada limpia por el árbol.** `taskkill /PID 11192 /T /F` terminó 17 procesos (cmd →
   pnpm → cmd → `run-dev.mjs` → API, Vite, scheduler, queue-poll y puente XTB).
   Verificado: 8000 y 3002 **libres**, `ready` falla, `bolsa-postgres` sigue `Up 21 hours`.
2. **Sonda del supervisor.** `node scripts/window-stack-ready.mjs --no-start` →
   `stack NO listo (…): fetch failed`, exit **1**.
3. **Disparo de la tarea** a las **12:18:58** (`schtasks /run`). La tarea salió **0** a las
   **12:19:05**: `stack-ready` registró `status: ready, started: true, pid: 30476`.
   Arranque medido: API lista en **3 894 ms**; Web lista después; total ~7 s.
4. **Árbol creado por la tarea:**

   ```text
   30476  cmd.exe    cmd /c "pnpm dev"          <- lanzado por el Programador
   35768  node.exe   pnpm.cjs dev
    8640  cmd.exe    node scripts/run-dev.mjs
   16396  node.exe   run-dev.mjs
   22632  python.exe .venv\Scripts\python.exe  -> 33992 uvicorn
   22900  node.exe   Vite (5173)
   33404  node.exe   xtb-bridge-mock (3002)
   ```

5. **Observación de 13 minutos** (sonda cada 60 s, desde 12:19:35 hasta 12:31:51):

   ```text
   12:19:35 ready=200 apiPid=33992 web5173=22900 runDev=1
   12:20:37 ready=200 apiPid=33992 web5173=22900 runDev=1
   …
   12:31:51 ready=200 apiPid=33992 web5173=22900 runDev=1
   ```

   **13/13 sondas con 200, PID idénticos, cero reinicios.** El `cmd` 30476 fue reparentado
   (su padre pasó a 33672) y sobrevivió; el `spawn(..., { detached: true })` de
   [`window-stack-ready.mjs`](../../scripts/window-stack-ready.mjs) hace su trabajo.

**Conclusión:** con esta configuración (`InteractiveToken`, `LeastPrivilege`, `AllowHardTerminate`,
`PT72H`) el Programador **no** mata los procesos desprendidos al terminar la tarea. No hace
falta una tarea de vida larga ni un arranque *breakaway*. Queda declarado que la medición es
de **esta** configuración: si la tarea pasa a "ejecutar tanto si el usuario inició sesión como
si no" (S4U o con contraseña), cambia de sesión y hay que repetir la prueba.

## 3. Dos defectos encontrados al probarlo

### 3.1 El supervisor vigila el puerto equivocado (3002 es el puente XTB, no la web)

| Fichero | Puerto web |
| --- | --- |
| [`scripts/run-dev.mjs`](../../scripts/run-dev.mjs) | `WEB_PORT ?? 5173` |
| [`apps/web/vite.config.ts`](../../apps/web/vite.config.ts) | `process.env.WEB_PORT ?? 5173` |
| [`scripts/window-stack-ready.mjs`](../../scripts/window-stack-ready.mjs) | `process.env.WEB_PORT ?? **3002**` |

`.env` **no** define `WEB_PORT`, así que la web vive en **5173** y **3002** es el puente
`xtb-bridge-mock` (verificado con `netstat` y la línea de comandos del PID). Consecuencias:

- Si el API está caído pero el puente XTB sigue vivo (p. ej. se mató solo el proceso uvicorn),
  `StackReady` ve un listener en 3002, concluye `port-busy`, **no arranca nada** y sale 1: el
  único escenario que debía recuperar es justo el que se niega a recuperar.
- Si el API y el puente están caídos pero Vite sigue en 5173, el guard no lo ve y arranca un
  segundo `pnpm dev`; `ensureStackPortsFree()` de `run-dev.mjs` libera 8000/5173/3002, con lo
  que la recuperación funciona pero a costa de matar el Vite anterior.

**Arreglo aplicado (2026-11-09, `scripts/` — no mueve el pin):** la lógica vive ahora en
[`scripts/lib/stack-ports.mjs`](../../scripts/lib/stack-ports.mjs), con test en
`scripts/lib/stack-ports.test.mjs` (7 casos, dentro de `pnpm window:test`).

- `stackPorts()` lee **8000 / 5173 / 3002** con los mismos defaults que `run-dev.mjs`.
- `decidePortConflict()` **bloquea solo si el API está ocupado** (un segundo uvicorn pelea
  por el puerto y matar a un proceso ajeno no es tarea del supervisor).
- Web o puente ocupados: **avisa y arranca**, porque `run-dev.mjs` libera los tres puertos
  en `ensureStackPortsFree()`.

Comprobado con los puertos reales: `{api:8000, web:5173, bridge:3002}` →
`block:true` (API vivo, PID 33992). Simulado "API caído, web y puente vivos" →
`{block:false, stale:[22900, 33404]}`: **antes del arreglo este caso se declaraba
`port-busy` y no recuperaba**; ahora arranca.

### 3.2 El supervisor arranca un stack SIN el perfil AUTO

El stack que estaba en marcha era `pnpm dev:auto`, que declara el perfil AUTO completo
(`AUTO_SIMULATION_WORKER_ENABLED=1`, `AUTO_ENGINE_SIM_V2=1`, gobernador, coste, etc.). `.env`
**no** contiene ninguna clave `AUTO_*`, y `StackReady` ejecuta `pnpm dev`, que —por diseño,
según el docstring de [`scripts/run-dev-auto.mjs`](../../scripts/run-dev-auto.mjs)— deja AUTO
apagado.

No afecta a la ventana forward (`run-day` hace su propio replay contra la base), pero es una
diferencia declarada: si el stack se cae y lo levanta el supervisor, el worker SIM de AUTO
queda apagado. Si se quiere el perfil AUTO en la ventana, el wrapper de la tarea debe invocar
`pnpm dev:auto`, no `pnpm dev`.

## 4. Limitación de la evidencia

El registro `Microsoft-Windows-TaskScheduler/Operational` está **deshabilitado**, así que no
hay eventos 102/111/329 del Programador. La prueba se apoya en el estado del proceso
(`netstat`, `Win32_Process`, `ready` cada minuto), que para esta pregunta es más directo que
el evento: el proceso o está vivo o no lo está. Habilitar el registro queda como mejora de
observabilidad, no como requisito de esta medición.

## 5. Estado al cerrar

- Stack arriba: `ready` **200**, `run-dev.mjs` presente, Vite en 5173, puente XTB en 3002.
- `BolsaV1_StackReady`: `Listo`, último resultado **0**, próxima ejecución 17:33.
- `pnpm window:freeze` → `freeze OK (c6cef5c9)`; `git status --porcelain -- apps packages` vacío.
- La prueba **sí** cambió el perfil del stack en marcha (`dev:auto` → `pnpm dev`), que es el
  que la tarea levantará a las 17:33 de todos modos. Revertir: parar el árbol y relanzar
  `pnpm dev:auto` con la misma redirección a `operability_runs/window-runs/20261109/dev-auto.log`.

## 6. Alcance: cuenta y sesión (medido el 2026-11-09, 13:05)

La medición vale para lo que se midió, y las dos condiciones se comprobaron:

| Comprobación | Valor |
| --- | --- |
| Principal de las cinco tareas | `ASUSPORTATIL\josea` (SID `S-1-5-21-…-1001`), `InteractiveToken` |
| Sesión interactiva | `console`, ID **1**, `Activo`, desde 2026-11-08 14:45 |
| `SessionId` de los procesos del stack | **1** en `cmd` 30476, `run-dev` 16396, uvicorn 33992, Vite 22900 y puente 33404 |
| `/api/health/ready` | **200** |

**Límite declarado:** bloquear la sesión no la cierra (el token interactivo sigue vivo), pero **cerrar
sesión, reiniciar o apagar** sí tumban el stack aunque las tareas sigan "Listo". La ventana corre
enchufada (`STANDBYIDLE`/`HIBERNATEIDLE` en AC a nunca) y con la sesión iniciada; `WakeToRun=true` cubre
que el equipo se duerma, no que se cierre la sesión. Detalle y la causa de la caída del 8-N en
[respuesta-auditoria-externa-2026-11-09.md](./respuesta-auditoria-externa-2026-11-09.md) §5.7.
