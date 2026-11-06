# Seguimiento — consolidación UI · proveedores y sincronismo

> **AsOf:** 2026-10-29 · **Área:** Configuración → Sync / proveedores y Ayuda → Datos de mercado
> **Naturaleza:** documento vivo de consolidación. Registra el contrato por área, los casos de
> prueba (backend → frontend), las evidencias y los defectos. No certifica el sello ni sustituye
> a una auditoría independiente.

---

## 0. Método de trabajo

Cada área se trabaja en tres pasos y **en este orden**:

1. **Backend**: contrato en código + pruebas automatizadas (unitarias y PostgreSQL real cuando
   el estado es durable). Si una prueba no se puede ejecutar, se declara como límite; nunca se
   cuenta como éxito.
2. **Frontend**: el mismo caso se reproduce en la UI y se cubre con Vitest/RTL.
3. **En vivo**: con el stack real (`pnpm dev` + PostgreSQL + `pnpm xtb:mock`) se recorre el caso
   en el navegador y se guardan capturas y respuestas de red en `evidence/`.

Cada caso de la tabla de §3 tiene un identificador estable (`PRV-*`, `SYN-*`, `HLP-*`) que se usa
igual en el test, en la evidencia y en la Ayuda de la app.

---

## 1. Estado del árbol al abrir esta consolidación

- Rama: `fix/auditoria-2-d1-d4` · HEAD `393c45fe`.
- **Cambios sin commit de la auditoría D-1–D-4** (22 modificados + 3 sin seguimiento) y
  `stash@{0}` = `aud2-evidence-baseline`. Esta área **no los toca ni los commitea**.
- Baseline ejecutado al abrir (2026-10-29):
  - `pytest packages/py/application/tests/test_sync_queue_retryable.py` + forma de
    `/api/market/providers`: **3 passed**.

### Defectos conocidos al abrir

| ID | Severidad | Descripción | Estado |
| --- | --- | --- | --- |
| PRV-D1 | Alta | `GetMarketStatus` devuelve Yahoo con `healthy=True` **hardcodeado**: la UI afirma un estado que nadie ha medido. | Corregido |
| PRV-D2 | Alta | Los proveedores no son configurables: XTB solo por `XTB_BRIDGE_URL` y Yahoo siempre activo. | Corregido |
| SYN-D1 | Media | `scope` sin validar (acepta cualquier cadena); la UI traduce `all` → `stale` de forma opaca. | Corregido |
| SYN-D2 | Media | El formulario de sync dispara un `PATCH` por cada tecla, sin botón ni feedback de error. | Corregido |
| SYN-D3 | Media | La cola no muestra `lastError` ni traduce estados. | Corregido |
| SYN-D4 | Baja | Sin endpoint de prueba de conexión: no se puede verificar un proveedor desde la UI. | Corregido |
| SYN-D5 | Media | Con Yahoo deshabilitado el worker seguiría encolando y sincronizando en silencio. | Corregido |

---

## 2. Contrato del área

| Superficie | Contrato |
| --- | --- |
| Registro de proveedores | IDs estables `yahoo` y `xtb` con etiqueta, capacidades y qué campos son configurables. Fuente única para API, UI, tests y Ayuda. |
| Persistencia | `market_provider_settings` (una fila por proveedor): `enabled`, `priority`, `min_interval_seconds`, `base_url`, `options`, `last_check_*`, `updated_at`. Defaults sembrados en la primera lectura. |
| Lectura | `GET /api/market/providers` devuelve configuración **y** estado efectivo. Para XTB el estado es una medición viva del bridge; para Yahoo es la última verificación persistida (`lastCheck`), no una suposición. |
| Escritura | `PATCH /api/market/providers/{id}` valida URL `http(s)`, prioridad e intervalo. 404 para ID desconocido, 422 para valor inválido. |
| Verificación | `POST /api/market/providers/{id}/test` ejecuta una comprobación real acotada y persiste `last_check_*`. |
| Fallo cerrado | Un proveedor deshabilitado no se usa en ningún camino (sync manual, cola, worker, quotes) y el motivo se declara en API, log y UI. |
| Sincronización | `scope ∈ {lists, stale}` validado en API. La respuesta de `enqueue-stale` declara `skippedReason` cuando no se encoló nada por configuración. |
| Cola | Estados `pending` / `processing` / `failed` / `completed` traducidos; `lastError` visible; contadores por estado. |
| Ayuda | Secuencia `HLP-1…HLP-8` reproducible: qué haces, qué debes ver, dónde se comprueba. |

---

## 3. Casos de prueba

Leyenda de estado: `pendiente` · `verde` · `rojo` · `limite` (no ejecutable en esta máquina).

### 3.1 Proveedores — backend

| ID | Caso | Capa | Esperado | Estado |
| --- | --- | --- | --- | --- |
| PRV-1 | Defaults del registro | unit | Yahoo y XTB con prioridad e intervalo por defecto; XTB toma `XTB_BRIDGE_URL` si existe | verde |
| PRV-2 | Sembrado en primera lectura | PG | La tabla vacía se siembra una sola vez y es idempotente | verde |
| PRV-3 | Round-trip de configuración | PG | PATCH persiste y GET lo devuelve con `updatedAt` nuevo | verde |
| PRV-4 | Validación de PATCH | unit/API | URL no `http(s)` → 422; prioridad negativa → 422; ID desconocido → 404 | verde |
| PRV-5 | Resolución por capacidad y prioridad | unit | Se elige el proveedor habilitado de menor `priority` para la capacidad pedida | verde |
| PRV-6 | Proveedor deshabilitado no resuelve | unit | Devuelve `None` con motivo declarado; no cae al siguiente en silencio | verde |
| PRV-7 | Test de conexión OK | unit | Persiste `last_check_ok=True` con mensaje y hora | verde |
| PRV-8 | Test de conexión fallido | unit | Persiste `last_check_ok=False` con el motivo; no lanza 500 | verde |
| PRV-9 | Caché de resolución | unit | Relee tras invalidación; no consulta la BD en cada llamada | verde |
| PRV-10 | Estado de Yahoo honesto | unit | Sin verificación, `healthy=False` y `verified=False`; nunca afirma disponibilidad | verde |

### 3.2 Sincronización — backend

| ID | Caso | Capa | Esperado | Estado |
| --- | --- | --- | --- | --- |
| SYN-1 | `scope` inválido | API | 422 y el valor previo no cambia | verde |
| SYN-2 | `scope=stale` persiste | PG | Se guarda y se devuelve tal cual | verde |
| SYN-3 | Encolado con Yahoo deshabilitado | unit | `scanned=0`, `enqueued=0`, `skippedReason=provider_disabled:yahoo` | verde |
| SYN-4 | Encolado normal | unit | Solo encola `stale`/`empty`/`error` y prioriza vacíos | verde |
| SYN-5 | Sync manual con Yahoo deshabilitado | API | 409 `provider_disabled:yahoo` y no escribe velas | verde |
| SYN-6 | Ventana post-cierre | unit | Laborable 17:35 Madrid en adelante procesa; antes y fin de semana no | verde |
| SYN-7 | Backoff y tope de reintentos | PG | `attempts` crece, `scheduled_at` retrocede por backoff y al llegar al tope queda `failed` | verde |
| SYN-8 | Prioridad de la cola | PG | `priority` mayor y `scheduled_at` más antiguo salen primero | verde |
| SYN-9 | Worker con proveedor deshabilitado | unit | No escanea ni procesa; lo declara una sola vez por transición | verde |
| SYN-10 | Throttle aplicado | unit | El cliente Yahoo recibe `min_interval_seconds` de la configuración | verde |

### 3.3 UI

| ID | Caso | Capa | Esperado | Estado |
| --- | --- | --- | --- | --- |
| UI-1 | Tarjetas de proveedor | Vitest | Muestran capacidades, prioridad, throttle, estado honesto y hora de verificación | verde |
| UI-2 | Guardado explícito de sync | Vitest | Un solo PATCH con los campos cambiados; sin PATCH por tecla | verde |
| UI-3 | Validación en cliente | Vitest | Fuera de rango → mensaje y botón deshabilitado, sin petición | verde |
| UI-4 | Error de API visible | Vitest | 422/500 se muestran con su detalle | verde |
| UI-5 | Probar conexión | Vitest | Resultado OK/fallo con mensaje y hora sin recargar | verde |
| UI-6 | Cola legible | Vitest | Estado traducido, `lastError` visible, contadores por estado | verde |
| UI-7 | Aviso de proveedor deshabilitado | Vitest | La UI avisa de que no se encolará ni sincronizará | verde |

### 3.4 Ayuda

| ID | Caso | Capa | Esperado | Estado |
| --- | --- | --- | --- | --- |
| HLP-1 | Secuencia completa | Vitest | `DATA_PROVIDER_VERIFY` tiene 8 pasos, cada uno con acción y comprobación | verde |
| HLP-2 | Sin pasos huérfanos | Vitest | Cada paso referencia un endpoint o pantalla existente | verde |
| HLP-3 | Registro de fuentes | Vitest | La sección `data` declara el tracker y el documento de seguimiento | verde |

### 3.5 Salud de proveedores en la barra de estado (HLT)

| ID | Caso | Capa | Esperado | Estado |
| --- | --- | --- | --- | --- |
| HLT-1 | Sonda al arrancar | pytest | El `lifespan` construye el monitor y dispara la sonda sin bloquear; `PROVIDER_HEALTH_PROBE_ON_STARTUP=0` solo omite el disparo, no el monitor | verde |
| HLT-2 | Solo se miden habilitados | pytest | `probe_now` escribe `last_check_*` únicamente de proveedores habilitados; uno deshabilitado nunca recibe un fallo engañoso | verde |
| HLT-3 | Agrupación por ventana | pytest | Dos consultas dentro de 60 s producen una sola sonda; pasada la ventana se vuelve a medir | verde |
| HLT-4 | La sonda no tumba el proceso | pytest | Una excepción de un proveedor se registra y la sonda termina; el arranque no falla | verde |
| HLT-5 | Veredicto agregado | pytest | `ok` / `degraded` (fallo medido gana) / `unverified` (falta medir) / `none` (ninguno habilitado); el deshabilitado no pinta rojo | verde |
| HLT-6 | Contrato del endpoint | pytest | `GET /api/market/providers/health` publica `status`, `ok`, `measuredAt`, `probing` y el detalle por proveedor | verde |
| HLT-7 | Icono de la barra | Vitest | Verde si todo medido y OK, rojo si alguno cae, ámbar sin medir, gris sin habilitados; tooltip con detalle y hora | verde |
| HLT-8 | Clic al origen | Vitest | El clic abre Configuración en la pestaña Sync / proveedores (`openPlatformConfig("other")`) | verde |
| HLT-9 | Mostrar/ocultar desde la barra | Vitest | El engranaje de la barra enciende/apaga el icono y la elección persiste en `bolsa-status-bar-prefs-v1` | verde |
| HLT-10 | Configuración persistida | Vitest | Las métricas de la cuenta y el icono sobreviven a la recarga (antes vivían en `useState`) | verde |


---

## 4. Evidencias

Directorio: `docs/engineering/evidence/proveedores-ui-2026-10-29/`.

### 4.1 Gates automatizados

| Evidencia | Contenido | Estado |
| --- | --- | --- |
| `ruff.txt` | `uv run ruff check packages/py apps/api-python` — All checks passed | verde |
| `mypy.txt` | `mypy` sobre domain/market/infrastructure/application/api — 576 ficheros sin errores | verde |
| `lint-imports.txt` | 4 contratos de `importlinter` mantenidos (grimp funciona en esta máquina) | verde |
| `pytest-area.txt` | 38 pruebas del área: unit + API + PostgreSQL real | verde |
| `pytest-full.txt` | `packages/py/application/tests` + `apps/api-python/tests` completos: **4455 passed, 5 failed** — triaje en `pytest-full-triage.md` | mixto |
| `vitest-area.txt` | 17 pruebas de UI del área (`sync-settings-panel`, `market-providers-status-card`, `data-provider-verify`) | verde |
| `vitest-web-full.txt` | Suite completa de `apps/web`: 341 ficheros / 2556 pruebas | verde |
| `tsc.txt` | `pnpm --filter @bolsa/web typecheck` | verde |
| `eslint.txt` | `pnpm --filter @bolsa/web lint` — 0 errores; 23 avisos `react-hooks/exhaustive-deps` **preexistentes** en otras áreas | verde |
| `contract-check.txt` | `pnpm contract:check` — `openapi.json` y `schema.d.ts` al día | verde |

### 4.2 Peticiones reales capturadas (`red-*.json`)

| Evidencia | Caso | Resultado |
| --- | --- | --- |
| `red-providers.json` | PRV-10 (estado honesto) | Yahoo `healthy=false`, `verified=false`, `lastCheckAt=null` antes de medir; XTB medido por el bridge |
| `red-providers-tras-recarga.json` | PRV-3 (persistencia) | Tras recargar: XTB `priority=25`, `minIntervalSeconds=1`, `lastCheckAt` de la prueba en UI |
| `red-test-yahoo.json` | PRV-7 | `ok=true`, mensaje «Yahoo respondió 18764.3000 (ref. ^IBEX…)» |
| `red-test-xtb.json` | PRV-7 | `ok=true`, mensaje «XTB bridge simulado» |
| `red-patch-xtb.json` | PRV-3 | 200 con los valores nuevos |
| `red-patch-invalid.json` | PRV-4 | 422 «baseUrl inválida…» |
| `red-patch-unknown.json` | PRV-4 | 404 «Proveedor desconocido: nasdaq» |
| `red-disable-yahoo.json` / `red-enable-yahoo.json` | PRV-2/fallo cerrado | `enabled=false` con mensaje «Deshabilitado en Configuración» y vuelta a `true` |
| `red-sync-409.json` | SYN-5 | 409 «Proveedor de histórico no disponible (provider_disabled:yahoo)» |
| `red-enqueue-disabled.json` | SYN-3 | `scanned=0`, `enqueued=0`, `skippedReason=provider_disabled:yahoo` |
| `red-sync-invalid-scope.json` | SYN-1 | 422 con `expected: 'lists' or 'stale'` (el alias `all` ya no existe) |
| `red-settings.json` / `red-queue.json` | Lectura base | Ajustes persistidos y cola vacía en el momento de la captura |

### 4.3 Recorrido en navegador (`ui-*.png`)

| Evidencia | Qué muestra |
| --- | --- |
| `ui-config-sync-proveedores.png` | Pestaña completa: dos tarjetas con capacidades, prioridad, throttle, estado medido y fecha de verificación + formulario de sincronización |
| `ui-test-conexion-xtb-ok.png` | «Conexión OK: XTB bridge simulado» y hora de última verificación actualizada sin recargar |
| `ui-yahoo-deshabilitado-cola-bloqueada.png` | Yahoo «Deshabilitado», aviso en Sincronización y botón de encolar bloqueado |
| `ui-encolar-con-proveedor-habilitado.png` | Tras rehabilitar: «Escaneados 35, encolados 0» (todo fresco en ese momento) |
| `ui-ayuda-verificacion-proveedores.png` | Ayuda → Datos de mercado con la secuencia `HLP-1…HLP-8` de verificación |

---

## 5. Bitácora

| Fecha | Paso | Resultado |
| --- | --- | --- |
| 2026-10-29 | Baseline | 3 passed (tests existentes de sync y proveedores) |
| 2026-10-29 | F2 · dominio + migración 059 + repositorio | Tabla creada, siembra idempotente en primera lectura |
| 2026-10-29 | F3 · casos de uso + rutas | `GET/PATCH /api/market/providers`, `POST /{id}/test`, `scope` cerrado a `lists`/`stale` |
| 2026-10-29 | F4 · cableado | Sync manual 409, cola y worker con fallo cerrado, throttle aplicado al cliente Yahoo |
| 2026-10-29 | F5 · UI | Tarjetas con guardado explícito, prueba de conexión, formulario con borrador y avisos |
| 2026-10-29 | F6 · recorrido en vivo | API 8000 + web 5173 + PostgreSQL + `pnpm xtb:mock`; 13 respuestas de red y 5 capturas |
| 2026-10-29 | F7 · Ayuda | `DATA_PROVIDER_VERIFY` con 7 pasos en Config y Ayuda, fuentes registradas, as-of 2026-10-29 |
| 2026-10-29 | Gates | ruff / mypy / lint-imports / área pytest / vitest / tsc / eslint / contract:check en verde. Suite Python completa: 4455 passed / 5 failed, triaje en §6 |

### Hallazgos de esta pasada (corregidos)

| ID | Descripción | Corrección |
| --- | --- | --- |
| PRV-D3 | La prueba PG `test_seeding_is_idempotent` asumía tabla vacía: con la BD del operador ya sembrada (por el recorrido en vivo) fallaba al comparar defaults. | El test vacía la tabla **dentro de la transacción** que luego revierte; ahora prueba de verdad el sembrado y sigue sin tocar la BD real. |
| UI-D1 | La Ayuda y `docs/MARKET_DATA.md` remitían a «Configuración → Otras», pestaña que se llama «Sync / proveedores». | Referencias corregidas en el tracker, el menú de Ayuda y `MARKET_DATA.md`. |
| UI-D2 | Texto con errata «estánén» en la tarjeta «¿Qué se actualiza solo?». | Corregido. |
| UI-D3 | Aviso de ESLint (`react-hooks/exhaustive-deps`) en `sync-settings-panel.tsx` por derivar `queue` fuera del memo. | El memo usa `queueQuery.data` directamente; el aviso desaparece. |

---

## 6. Límites declarados al cerrar

- **Suite Python completa en mixto, no en verde.** `4455 passed / 5 failed`. Triaje completo en
  `evidence/proveedores-ui-2026-10-29/pytest-full-triage.md`:
  - 3 rojos **preexistentes y fuera del área**: conciliación de P&L del ciclo AUTO/día-D con
    diferencia de 1×10⁻⁶ € (`test_auto_dia_d_trace_pg` ×2 y `test_auto_estudio_chain_evidence_pg`).
    Se reproducen en aislamiento. No los toca este plan y **no se declaran arreglados**.
  - 2 rojos **de entorno** que pasan en aislamiento: un deadlock de migración y una carrera del
    test de caos del worker de recuperación. Causa raíz verificada: los tests de roundtrip
    (`alembic downgrade/upgrade`) **operan sobre la BD real `bolsa_v1`**, así que ejecutar la
    suite con el stack en vivo provoca el deadlock, deja al API sin tablas a media pasada y
    **borra la configuración persistida** (la 059 se recrea vacía y se vuelve a sembrar con
    defaults). Detalle y evidencia SQL en `pytest-full-triage.md` §2. Consecuencia práctica:
    no lanzar la suite completa con `pnpm dev` en marcha.
- **`priority` es contrato, no fallback.** Se persiste y gobierna la resolución por capacidad,
  pero hoy hay un único proveedor por capacidad: su efecto funcional es el orden declarado.
  No se inventa un fallback a otro proveedor cuando el elegido está deshabilitado (fallo cerrado).
- **La verificación de Yahoo es una lectura acotada**, no un SLA: depende de la red del
  operador. Un fallo se persiste con su motivo (`last_check_ok=false`), nunca se convierte en 500.
- **XTB no escribe histórico.** Su prueba de conexión valida el bridge, no la calidad del cierre.
- **El recorrido en vivo se hizo contra la BD del operador.** Las pruebas PG del área aíslan sus
  escrituras en una transacción que se revierte; **pero la suite completa no**: los tests de
  roundtrip de migraciones hacen `downgrade/upgrade` sobre `bolsa_v1`, lo que recreó vacía la
  tabla `market_provider_settings` y la devolvió a defaults (PRV-3 sigue probado por la evidencia
  capturada antes de eso). No lanzar la suite completa con el stack en vivo.
- **No se ha commiteado nada.** El árbol sigue con los cambios de la auditoría D-1–D-4 y los de
  esta área sin commit, tal como se declaró al abrir. Si quieres commit, se hace en rama nueva
  con staging selectivo y avisando antes.
- **23 avisos de ESLint** siguen en pantalla: son `react-hooks/exhaustive-deps` preexistentes de
  otras áreas (backtests, mesa, journal). El del área está corregido; no se limpian los ajenos.

---

## 7. Entrega 060 · comprobación de servidores configurable (ON/OFF, intervalo y un solo modelo de verdad)

### 7.1 Problema que cierra

El nombre «Activar auto-actualización en segundo plano» (`autoSyncEnabled`) invitaba a creer
que ese toggle **probaba servidores**, cuando en realidad solo encola y descarga velas OHLCV.
La salud de proveedores era otra cosa: `ProviderHealthMonitor` con **60 s fijos en código**,
sin interruptor, y `GET /api/market/providers/health` **medía XTB en vivo** en cada consulta
(dos fuentes de verdad y un GET con efecto de red).

### 7.2 Lo entregado

| Pieza | Cambio |
| --- | --- |
| Migración `060_provider_check_policy` | `sync_settings.provider_check_enabled` (bool, default ON) y `provider_check_interval_seconds` (int, default 60, `CHECK` 15–3600), aditiva e idempotente |
| Dominio | `ProviderCheckPolicy` + `normalize_provider_check_interval` (una sola fuente del rango para BD, API y UI) |
| Aplicación | `summarize_provider_health(..., policy, now)` con estado `stale`; `ProviderHealthMonitor` lee la cadencia **persistida** (`probe_if_due`), bucle `run_forever()` con tick de 10 s y `aclose()` |
| `GetMarketStatus` | Nuevo `live=False`: el GET del icono devuelve **solo lo persistido** (sin tráfico a proveedores) |
| API | `GET /market/providers/health` solo lectura + `POST /market/providers/health/check` («Comprobar ahora», mide aunque esté OFF); `sync/settings` publica y actualiza los dos campos (422 fuera de rango) |
| Lifespan | `await probe_if_due()` al arrancar (si el flag de entorno lo permite) + `start()` del bucle; `aclose()` al apagar |
| UI | Tarjeta «Automatización: velas y servidores» con dos bloques rotulados, un único «Guardar cambios» y «Comprobar ahora»; tarjeta de proveedores con la última comprobación; icono con `stale`, tooltip con la política y poll derivado del intervalo (`min(60 s, max(15 s, ι/2))`; 120 s con OFF) |

### 7.3 Evidencia en vivo (2026-10-29, stack `pnpm dev`)

| Comprobación | Resultado |
| --- | --- |
| Migración aplicada al arrancar | `GET /api/health/ready` → `esquema en head (060_provider_check_policy)` |
| Publicación de la política | `sync/settings` → `providerCheckEnabled=true`, `providerCheckIntervalSeconds=60`; `health` → `autoCheckEnabled`, `checkIntervalSeconds`, `nextCheckAt` |
| Intervalo 15 s sin navegador | `measuredAt` 12:12:30 → 12:14:25 con solo dos GET separados 45 s (el bucle refrescó entre medias) |
| OFF detiene el bucle | Tras `providerCheckEnabled=false`, `measuredAt` idéntico a los 40 s; `nextCheckAt=null`; `status=ok` (no `stale`) |
| «Comprobar ahora» | `POST /market/providers/health/check` → `measuredAt` actualizado al instante; en la UI aparece «Comprobación terminada: proveedores medidos.» |
| Panel en navegador | Dos bloques rotulados («Velas (histórico)» / «Comprobación de servidores»), checkbox ON/OFF, «Comprobar cada (s)» y «Comprobar ahora» bajo un único Guardar — captura `ui-automatizacion-velas-servidores.png` |
| Estado tras las pruebas | `providerCheckEnabled=true`; el intervalo quedó en **3600 s** (valor puesto al probar el límite superior) — pendiente devolverlo a 60 s desde la UI |

### 7.4 Gates

- Área Python: `test_market_providers.py`, `test_market_providers_api.py`, `test_provider_health_startup.py`,
  `test_sync_queue_retryable.py`, `test_market_providers_pg.py` y guardias de head Alembic → verde.
- Web: Vitest del panel (11) e icono (9) → verde; `tsc -b --noEmit` → verde.
- Contrato: `contract:gen` regeneró `openapi.json` (235 paths) y `schema.d.ts`.

### 7.5 Límites declarados

- El **`stale` en vivo** no se ha forzado con el stack arriba (exigiría detener el bucle sin
  tumbar la API); está cubierto por tests unitarios y de API, y se explica en el tooltip.
- «Comprobar ahora» requiere que el proceso API tenga el `ProviderHealthMonitor` instalado
  (siempre en el lifespan normal); si no, responde **503** en lugar de fingir una medición.
- La cadencia se persiste en la fila única de `sync_settings`: es configuración global, no por
  proveedor. Un intervalo por proveedor no forma parte de esta entrega.


