# Evidencia `v2.88.144-beta` — la cadencia se **recupera** si el equipo estaba dormido (`StartWhenAvailable` por XML, verificado en el registro)

> **Bump:** `2.11.143-beta` → **`2.11.144-beta`** (`package.json` + `meta.bump` de los **13** CLIs; guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) **en verde**).
>
> **Naturaleza:** incremento **de operación + observabilidad + documentación** sobre el **registro de las tareas de Windows** — **no** toca motor de decisión, umbrales, pesos A/B, contrato HTTP ni esquema: **`Δ motor = 0`** · **`Δ decisión = 0`** · **`Δ contrato HTTP = 0`** · **SIN migración** (head `055_dia_d_identity_nullable`). Vive en `scripts/` (+ `meta.bump`) ⇒ **freeze-neutral**. Tag **unsigned**.
>
> **Base:** `v2.88.143-beta`.

## 1. El defecto (medido el domingo `18/10/2026`)

El §7 de la evidencia del `.143` dejó medido que la tarea de las **18:00** se ejecutó a las **18:39:13**. La causa raíz está en el registro de energía: el equipo entra en **modern standby** (`506`) y despierta (`507`) **cada ~60 min**; a las 18:00 **estaba dormido**.

Los ajustes con los que `schtasks /create` había registrado las dos tareas eran:

```text
StartWhenAvailable        = False      <-- si el equipo duerme, la corrida NO se recupera
WakeToRun                 = False
DisallowStartIfOnBatteries= True
MultipleInstances         = IgnoreNew
```

**Por qué importa:** `StartWhenAvailable = False` significa que una corrida **perdida no se recupera**. Lo de hoy se salvó porque el equipo despertó **ese mismo día**; si no despierta en todo el día, el día **se pierde** (lo detectaría después el **arrastre** del vigía, pero el día ya no se mide). Un fallo silencioso de la cadencia.

## 2. El cambio

`schtasks /create` **no tiene** el flag: `StartWhenAvailable` **sólo existe en el XML** de la tarea (o vía `Set-ScheduledTask`). Por eso el registro pasa a ser **XML declarativo**:

- **`taskXml({...})`** (**puro**, [`window-forward.mjs`](../../../../scripts/lib/window-forward.mjs)): genera el XML de una tarea diaria. Fija `StartWhenAvailable = true`, `CalendarTrigger` diario a la hora pedida, `InteractiveToken`, `IgnoreNew`, la acción `Exec` con el **wrapper absoluto** (sin comillas anidadas) y **escapa** el texto (nombre/descripción/ruta). Valida `time` (`HH:MM`) y la fecha; **lanza** en vez de registrar algo opaco.
- **`registerTask`** ([`window-forward-runner.mjs`](../../../../scripts/window-forward-runner.mjs)): escribe el XML en `operability_runs/window-runs/window-<kind>-task.xml` (**UTF-16 con BOM**, lo que exige el Programador), registra con `schtasks /create /tn ... /xml ... /f` y **verifica después**.
- **`verifyTaskXml`** (**fail-closed**): lee `schtasks /query /tn "<name>" /xml ONE` y exige el literal `<StartWhenAvailable>true</StartWhenAvailable>`. Si no casa, **desregistra** la tarea: mejor ninguna tarea que una que se declara y no lo es (mismo criterio que la sonda del wrapper del `.142`).

### 2.1 Lo que **no** se cambia (declarado, no silencioso)

| Ajuste | Valor | Por qué |
| --- | --- | --- |
| `WakeToRun` | `false` | Despertar el equipo a diario tiene coste real y depende de hardware/BIOS ⇒ **decisión del operador**, no del sello |
| `DisallowStartIfOnBatteries` / `StopIfGoingOnBatteries` | `true` | Valor **medido antes** del cambio: no se amplía alcance |
| `ExecutionTimeLimit` | `PT72H` | Es el **default** de `schtasks /create`; se preserva (se corrigió un `PT1H` que el propio cambio había introducido y **recortaba** margen) |
| `LogonType` / `MultipleInstances` | `InteractiveToken` / `IgnoreNew` | Mismas garantías que antes |

## 3. Verificación (medida)

| Comprobación | Comando | Resultado |
| --- | --- | --- |
| Tests JS | `pnpm window:test` | **48 passed** (40 + **8 nuevos** de `taskXml`: marcador `StartWhenAvailable`, disparador diario/fecha, acción = wrapper absoluto **sin** `pnpm` ni `<Arguments>`, interactivo + `IgnoreNew`, batería/`WakeToRun`/`PT72H` intactos, los flags **no son decorativos** (`false` se escribe `false`), escape XML, y rechazo de `name`/`wrapper`/`time`/`date` inválidos) |
| Registro real | `pnpm window:task:install` | `wrapper verificado end-to-end (exit 0)` · `XML ... escrito` · `Correcto: se creó correctamente la tarea programada` · **`verificada: StartWhenAvailable = true (leido del registro)`** — para **las dos** tareas |
| Lectura independiente del registro | `Get-ScheduledTask` | `FORWARD: StartWhenAvailable=True TimeLimit=PT72H` · `WATCH: StartWhenAvailable=True TimeLimit=PT72H` · `WakeToRun=False` · `Battery=True` · `Logon=Interactive` |
| Próximas corridas | `Get-ScheduledTaskInfo` | `forward next = 19/10/2026 18:00` · `watch next = 19/10/2026 20:20` |

## 4. Dato adicional medido en la misma noche: el **vigía** también disparó solo

`Get-ScheduledTaskInfo -TaskName BolsaV1_WindowWatch` ⇒ **`LastRunTime = 18/10/2026 20:39:14`**, `LastTaskResult = 0`; y el journal del latido registra **`20:39:20 · source: cli`** ⇒ lo escribió la **tarea** (no el stack), con `verdict NON_MARKET_DAY` y `alerts: []`.

**Dos lecturas honestas:** (a) la vigilancia **funciona sin stack**, otra vez, y esta vez en domingo; (b) el mismo **modern standby** retrasó también esta tarea (`20:20` → `20:39`), lo que confirma que el §1 no era un caso aislado del run-day.

## 5. Límites declarados (sin fabricar)

- **`StartWhenAvailable` no es magia:** recupera la corrida **cuando el equipo tenga sesión**. El runner sella **el día del reloj al arrancar**, así que una recuperación **dentro del mismo día** sigue siendo ese día; si el equipo no se enciende en todo el día, el día **se pierde** y sólo lo señala el **arrastre** del vigía en la siguiente ejecución. Cerrarlo del todo exigiría `WakeToRun = true` (**no activado**: depende de hardware/BIOS y despierta el equipo a diario).
- Con `DisallowStartIfOnBatteries = true`, **en batería las tareas no corren**. Es un **límite declarado** del registro, no un bug del cambio.
- El XML registrado vive bajo `operability_runs/` (**ignorado por git**): es auditable **en la máquina** (`schtasks /query /tn ... /xml`), mientras que en git queda el **generador** y sus tests.
- La **ventana PAPER real** sigue **`0/4` días · `0/2` regímenes · `0/32` ciclos ⇒ `INCONCLUSIVE`** (`20261014/15/16` vetados por **`BEAR_TREND`**): esto **no** desbloquea la ventana, falta **OPERACIÓN**. **No demuestra rentabilidad.**
- Tag **unsigned**; la ventana avanza **un día de pared por corrida**.

## 6. Reproducción

```powershell
pnpm window:test                                  # 48 (incluye los 8 de taskXml)
pnpm window:task:install -- --dry-run             # plan: /xml ... + StartWhenAvailable=true
pnpm window:task:install                          # registra y VERIFICA leyendo el registro
Get-ScheduledTask -TaskName BolsaV1_WindowForward | Select -Expand Settings |
  Select StartWhenAvailable, WakeToRun, ExecutionTimeLimit
schtasks /query /tn "BolsaV1_WindowForward" /xml ONE | Select-String StartWhenAvailable
```

## 7. Cita POST-TAG — CI del sello

**Tag publicado:** `v2.88.144-beta` (**anotado, unsigned**; objeto `9ba08f6c` → commit **`114396ff`**), empujado junto a `main` (`75054d2d..114396ff`).

**`Release tag CI` [run `39157219505`](https://github.com/jvelasca/Bolsa_V1/actions/runs/39157219505) — VERDE** (`2026-10-18T19:06:17Z` → `19:20:15Z`, ~**13m58s**; **13 jobs `success` + `certify` `success`**; `playwright (integrated E2E, opt-in)` `skipped`, declarado):

| Job | `conclusion` |
| --- | --- |
| `security (gitleaks)` | **success** |
| `decision-spine` | **success** |
| `python (ruff/imports/mypy/pytest offline)` | **success** |
| `lifecycle-pg (Alembic + auth + golden restart)` | **success** |
| `replay-repro (regenera el artefacto del sello desde el fixture)` | **success** |
| `shared (build/typecheck/test)` | **success** |
| `frontend (typecheck/lint/test/build + contract:check)` | **success** |
| `playwright (integrated axe)` | **success** |
| `playwright (integrated AUTO S5)` | **success** |
| `playwright (mock E2E)` | **success** |
| `a7-gate (A7 C3 chaos live_a7 · dedicated real-PG)` | **success** |
| `dr-verify (battery DB_DR / TCP CI)` | **success** |
| `playwright (integrated E2E, opt-in)` | `skipped` (opt-in, declarado) |
| `certify (aggregate + artifact)` | **success** |

**Los dos gates que importan, medidos en el log del CI:**

- **Gate `window:freeze` (job `shared`) — verde:** `> node scripts/window-pin.mjs --check` ⇒ **`[window-pin] freeze OK (114396ff)`** ⇒ el pin (`apps` `e1c5e825` / `packages` `6377a7a2`) **casa** con el árbol del commit del tag.
- **`replay-repro` — `REPRODUCIDO`:** `sha256 1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7` (fichero `3340728` bytes) — **idéntico** al de `.136`…`.143`, y **también** en la 2ª corrida (determinismo) ⇒ **`Δ decisión = 0` medido por el CI**, no afirmado.

**`main` en el mismo commit `114396ff` — VERDE también:** `Python CI` [39157216893](https://github.com/jvelasca/Bolsa_V1/actions/runs/39157216893) · `Frontend CI` [39157216878](https://github.com/jvelasca/Bolsa_V1/actions/runs/39157216878) · `Optimize lab` [39157216884](https://github.com/jvelasca/Bolsa_V1/actions/runs/39157216884) · `Gitleaks` [39157216891](https://github.com/jvelasca/Bolsa_V1/actions/runs/39157216891) — **`success`**.

**Nota de honestidad sobre el orden:** esta cita se escribe **después** del tag (commit POST-TAG sobre `main`), de modo que **dentro** del tag el §7 decía «pendiente». Es el patrón declarado en los sellos anteriores; la medida es **falsable desde GitHub** por cualquiera.
