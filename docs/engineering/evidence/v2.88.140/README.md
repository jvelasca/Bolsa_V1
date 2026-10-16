# Evidencia `v2.88.140-beta` — VIGILANCIA de la operativa diaria de la ventana PAPER: cadencia instalable + vigía con aviso de «día perdido»

> **Bump:** `2.11.139-beta` → **`2.11.140-beta`** (`package.json` + `meta.bump` del CLI OOS `v2_87`, de los 9 CLIs `v2_89`…`v2_97`, del certificador `v2_98`, del CLI `v2_99` y de `v2_100` — **13 scripts** en [`apps/api-python/scripts`](../../../../apps/api-python/scripts/); guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) **2 passed**).
>
> **Naturaleza:** incremento **de operación + observabilidad + documentación** — **no** toca el motor de decisión, ni umbrales, ni el contrato HTTP, ni el esquema. · **`Δ motor = 0`** · **`Δ decisión = 0`** · **`Δ contrato HTTP = 0`** (`contract:check` **OK**; sin endpoint nuevo) · **SIN migración** (head `055_dia_d_identity_nullable`). Tag **unsigned**.
>
> **Base:** `v2.88.139-beta` (commit del tag `0739daae`).

---

## 1. Qué cierra (y qué NO)

Responde a la directriz del propietario **«debe estar siempre vigilando la operativa diaria … siempre
vigilando y avisando»**. Cierra **dos huecos declarados** de la vigilancia (la **cadencia no se podía
instalar** y **nada avisaba** de un día perdido). **NO** certifica la ventana: sigue `0/4 · 0/2 · 0/32`
⇒ `INCONCLUSIVE` (falta **MERCADO/OPERACIÓN**, no software).

### 1.1 Hallazgo A — el instalador de la cadencia diaria estaba ROTO (arreglado, freeze-neutral)

- **Defecto.** [`scripts/window-forward-runner.mjs`](../../../../scripts/window-forward-runner.mjs)
  construía el `/tr` de `schtasks` con **comillas ANIDADAS** escapadas a mano
  (`/tr "cmd /c \"cd /d \"…\" && \"…\\pnpm.cmd\" window:run-day\""`). En Windows ese anidamiento rompe
  el parseo: las comillas internas se consumen y `schtasks` responde
  **«Sintaxis no válida. Falta la opción obligatoria "sc"»** ⇒ `pnpm window:task:install` **fallaba**
  (exit `1`) y **no había forma de registrar la vigilancia diaria**.
- **Prueba controlada (falsable).** Antes del fix: `pnpm window:task:install -- --at 18:00` ⇒
  `schtasks devolvio error` (arriba). Después: **«se creó correctamente la tarea programada
  "BolsaV1_WindowForward"»** y `schtasks /query` muestra **`Estado: Listo`**, próxima ejecución
  **`17/10/2026 18:00:00`**.
- **Fix (freeze-neutral).** La tarea apunta a un **wrapper `.cmd`** generado en
  `operability_runs/window-runs/window-forward-task.cmd` (`cd /d <raíz>` + `node_modules\.bin\pnpm.cmd
  window:run-day`): `/tr "<ruta-wrapper.cmd>"` es **un único token**, sin comillas anidadas. El fix vive
  en `scripts/` (**NO participa del pin**): `Δ árbol = 0`.

### 1.2 Hallazgo B — nada AVISABA de un «día perdido» (vigía nuevo, ON por defecto)

- **Defecto (hueco declarado).** La ventana exige **un `run-day` por día de mercado** (el cubo de
  calendario sale del **reloj de pared**), pero **ningún** worker ni la tarea emitían señal si ese día no
  se corría: un fallo silencioso podía costar días de ventana sin que nadie se enterara.
- **Fix.** NUEVO [`window_day_watch_worker.py`](../../../../apps/api-python/src/bolsa_api/background/window_day_watch_worker.py),
  registrado en el proceso de crons
  ([`scheduler_worker`](../../../../apps/api-python/src/bolsa_api/workers/scheduler_worker.py)). Una vez
  por día laborable, **después** de la hora del `run-day`, lee el **ledger del runner**
  (`operability_runs/window-runs/ledger.jsonl`) y decide —de forma **pura y falsable**— si el día se
  ejecutó. Si **no** consta (`MISSED`) o quedó en `HARD_ERROR` ⇒ **AVISA**: log estructurado `ALERTA`
  **siempre** y email por el canal SMTP ya existente cuando está configurado (nunca en silencio).
- **Semántica (veredictos).** `NON_MARKET_DAY` (finde) · `NOT_DUE` (antes de la hora) · `RUNNING` (lock
  del día presente) · `OK` (`MEDIDO`) · `VETO` (`NO_MEDIDO_REGIMEN` ⇒ **INFO, no alerta**) · `DECLARED`
  (`DECLARADO`) · `HARD_ERROR` (**alerta**) · `MISSED` (**alerta**: día laborable, hora vencida, sin fila
  y sin run en curso).
- **Config (nombres).** `WINDOW_DAY_WATCH_ENABLED` (**default ON**; se apaga con `0/false/no/off`) ·
  `WINDOW_DAY_WATCH_HOUR`/`_MINUTE` (default `20:00` Europe/Madrid, después del `run-day` de las `18:00`)
  · `WINDOW_DAY_WATCH_EMAIL_TO` (destinatario; si falta cae a `estudio_opinion_email_to` → `smtp_user` →
  `smtp_from`). `WINDOW_LEDGER_PATH` permite apuntar a otro ledger.

> **Aclaración honesta.** El «modo AUTO» del motor (`auto_simulation_worker`, `paper_auto_engine_worker`,
> `auto_orchestrator`) nace **default OFF** y **NO** mide la ventana: la medición diaria es `run-day`
> (proceso aparte) y `v2_98` declara que es **operación del propietario**. Por eso la vigilancia se monta
> sobre la **cadencia** (`run-day`) y **no** sobre el motor AUTO —activarlo no habría avisado de un día
> perdido y podría contaminar la cuenta de la ventana con fills ajenos—.

### 1.3 Tests nuevos

[`test_window_day_watch.py`](../../../../apps/api-python/tests/test_window_day_watch.py) (**20 passed**):
decisión pura por veredicto (finde, no-vencido, en curso, perdido, medido, veto, declarado, hard error,
estado desconocido, «gana la última fila del día», fila de otro día **no** cuenta como hoy), lectura del
ledger (ignora líneas corruptas; ausente ⇒ vacío), resolución de destinatario y **cableado del aviso**
(un `MISSED` **sí** llama al email; un `VETO` **no**). Actualizado el guardián
[`test_scheduler_worker.py`](../../../../apps/api-python/tests/test_scheduler_worker.py) (el vigía entra
en `_event_loop_starters`).

---

## 2. Verificación (medida)

| Compuerta | Resultado |
| --- | --- |
| `pytest apps/api-python/tests/test_window_day_watch.py` | **20 passed** |
| `pytest apps/api-python/tests -k "scheduler or worker or window or config or settings"` | **282 passed / 1 failed** — el fallo es el caos **conocido** `test_c3a` (worker del servidor dev **vivo** compite por el outbox; ver §3) |
| `test_dia_d_bump_guard` | **2 passed** (`2.11.140-beta`) |
| `pnpm window:test` | **28 passed / 0 failed** |
| `ruff check` (ficheros tocados) | **`All checks passed!`** |
| `pnpm window:task:install -- --at 18:00` | **tarea creada**; `schtasks /query` ⇒ **`Estado: Listo`**, próxima **`17/10/2026 18:00:00`** |
| `pnpm window:status` | `medidos=0 · veto=3 · duros=0` ⇒ gate **`NO_MEDIDO`** |

---

## 3. Límites declarados (sin fabricar)

- La **ventana PAPER real** (ADR-046) sigue **`0/4 días`, `0/2 regímenes`, `0/32 ciclos` ⇒
  `INCONCLUSIVE`**; días `20261014/15/16` = `NO_MEDIDO_REGIMEN` por veto **`BEAR_TREND`** (LONG vetadas).
  Falta **OPERACIÓN** (días de mercado con LONG permitida), **no** software.
- El vigía **no toca la ventana**: sólo **LEE** el ledger y el lock; **no** lanza `run-day`, **no**
  fuerza régimen, **no** cambia umbrales. `Δ motor = 0`; `Δ decisión = 0`.
- **Dependencia declarada:** el vigía corre en el proceso de crons del **API**; si el API está caído a la
  hora del vigía, ese día no avisa (la **tarea de Windows** sí corre `run-day` aunque el API esté caído,
  pero es la **vigilancia** la que requiere el proceso vivo). El **silenciamiento en curso** (`RUNNING`)
  es **conservador**: mientras el lock del día exista, no se avisa en falso.
- El caos `test_c3a` exige **acceso exclusivo** a la BD; con el stack dev vivo (worker drena el outbox)
  falla **por diseño** — **no** es regresión de este sello (se reproduce/diagnostica en `v2.88.139`).
- `Δ contrato HTTP = 0` (sin endpoint nuevo); sin migración; tag **unsigned**; **no demuestra
  rentabilidad**.

---

## 4. Publicación del sello

El gate `window:freeze` del job `shared` de
[`release-tag-ci.yml`](../../../../.github/workflows/release-tag-ci.yml) es **fail-closed**: compara los
dos *tree hashes* del pin con `HEAD`. Por eso `window:pin` re-ancla el pin al árbol del sello y el tag
`v2.88.140-beta` (**anotado, unsigned**) se crea sobre el commit **cuyo pin casa con su árbol** (el
commit del **re-anclaje**), **no** sobre el commit del sello de contenido. Como la ventana seguía con
**0 días `MEDIDO`**, re-anclar **no** invalida ningún día medido.

### 4.1 Cita POST-TAG — CI del sello

_Pendiente de la corrida del `Release tag CI` de `v2.88.140-beta` (se citará aquí el run y la tabla de
jobs al completarse)._
