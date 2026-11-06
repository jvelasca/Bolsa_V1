# Handoff · Entrega 060 — comprobación de servidores (ON/OFF, intervalo, modelo único)

**Fecha de cierre:** 2026-10-29 (13:30, UTC+1)
**Rama:** `fix/auditoria-2-d1-d4` · **HEAD:** `393c45fe`
**Versión del paquete:** `2.11.171-beta`
**Estado:** código completo, verificado y **sin commitear** (el árbol ya estaba sucio antes de esta entrega)

> **Cómo usar este documento.** Cada afirmación de estado lleva el comando que la
> comprueba (§8). Si un dato no cuadra con lo que ves, **gana el comando**, no este texto.
> No se ha inventado ningún pendiente: lo que no se probó, está declarado como no probado
> en §10.

---

## 1. Estado del árbol de trabajo (leer antes de tocar nada)

- `git status --porcelain` devuelve **90 entradas**. No es una entrega limpia y aislada.
- Conviven **tres bloques de cambios sin commit**:
  1. **059** — registro de proveedores (`market_provider_settings`, CRUD, prueba de conexión,
     `scope` de sync, fallo cerrado del worker, throttle). Cerrada hoy, documentada en
     §1–§6 de `seguimiento-ui-proveedores-2026-10-29.md`.
  2. **060** — esta entrega (política de comprobación). Documentada en §7 del mismo fichero.
  3. **Ajenos** — cambios de la auditoría D1–D4 y de otras áreas (`auto_ops_jobs`,
     `estudio_daily_proposal`, `portfolio_decision_engine`, help, etc.). **No son de esta área.**
- **No hay commit.** Si hay que commitear, se hace en rama nueva, con staging selectivo y
  avisando antes: mezclar 059 + 060 + auditoría en un único commit hace el diff inrevisable.
- Scripts temporales de sondeo creados en esta sesión: borrados (`tmp_check_providers.py`,
  `_tmp_db_state.py`). Único residuo ajeno: `_tmp_evidence.ps1` y `_tmp_evidence_409.ps1`
  (de la entrega 059, no de esta).
- Captura nueva en evidencia: `docs/engineering/evidence/proveedores-ui-2026-10-29/ui-automatizacion-velas-servidores.png`
  (copiada desde `C:\Users\josea\provider-check-panel.png`, que sigue en la carpeta personal).

---

## 2. Doctrina del área (las cuatro reglas que no se negocian)

1. **Modelo único de verdad.** El estado de un servidor es **su última comprobación
   persistida** (`market_provider_settings.last_check_*`). Ningún `GET` mide. Medir es
   competencia exclusiva de `ProviderHealthMonitor` (bucle o «Comprobar ahora»).
2. **Honestidad.** Sin medición no hay verde: es `unverified` (ámbar). Un proveedor
   **deshabilitado** no pinta rojo: apagarlo es una decisión, no una caída.
3. **«Vencido» no es «caído».** Si la automática está ON y la medición supera `2 × intervalo`,
   el veredicto es `stale` (ámbar), nunca verde ni rojo.
4. **Dos automatizaciones distintas.** `autoSyncEnabled` descarga velas OHLCV;
   `providerCheckEnabled` solo mide conectividad. Confundirlas fue el problema que abrió
   esta entrega.

---

## 3. Contrato del dominio (símbolos exactos)

### 3.1 `bolsa_domain.entities.market_provider`

| Símbolo | Valor / forma | Nota |
|---|---|---|
| `MIN_PROVIDER_CHECK_INTERVAL_SECONDS` | `15` | Rango único; lo publican BD, API y UI |
| `MAX_PROVIDER_CHECK_INTERVAL_SECONDS` | `3600` | |
| `DEFAULT_PROVIDER_CHECK_INTERVAL_SECONDS` | `60` | |
| `PROVIDER_HEALTH_STALE_GRACE_FACTOR` | `2.0` | `stale` si `edad > intervalo × 2` |
| `ProviderCheckPolicy` | `frozen dataclass(enabled: bool = True, interval_seconds: int = 60)` | `stale_after_seconds` = `interval × 2.0` |
| `normalize_provider_check_interval(value)` | **acota** al rango; `None`/ilegible → `60` | No lanza: es la última defensa del dominio |

> **Asimetría intencional.** El dominio **acota** (nunca explota), la API **rechaza con 422**
> (`ge=15, le=3600` en el DTO). No es un bug: la UI valida, la API contrata y el dominio
> protege caminos que no pasan por ninguno de los dos.

### 3.2 `bolsa_application.market_providers`

| Símbolo | Contrato |
|---|---|
| `summarize_provider_health(statuses, *, policy=None, now=None)` | Devuelve `ProviderHealthSummary` con `status`, `ok`, `measured_at`, `providers`, `auto_check_enabled`, `check_interval_seconds`, `next_check_at` |
| Precedencia del veredicto | `degraded` (fallo medido) > `unverified` (falta medir) > `stale` > `ok`; `none` si ningún proveedor habilitado |
| `ProviderHealthMonitor.probe_now()` | Mide **solo habilitados** y persiste `last_check_*`. Nunca propaga el fallo: el fallo es un dato |
| `ProviderHealthMonitor.probe_if_due(*, force=False)` | `force=True` = «Comprobar ahora» (mide aunque la automática esté OFF). Sin `force`: `None` si OFF **o** si no ha vencido — **no distingue ambos casos por el retorno** |
| `ProviderHealthMonitor.policy()` | Lee `sync_settings`; si la BD falla, defecto ON/60 s + `warning` |
| `ProviderHealthMonitor.last_measured_at()` | `max(last_check_at)` de los habilitados, **persistido** |
| `ProviderHealthMonitor.is_due(policy, last)` | `enabled and (last is None or edad >= interval)` |
| `ProviderHealthMonitor.ensure_fresh()` | No bloquea; programa `probe_if_due()`. `True` = hay tarea viva, **no** promesa de medición |
| `ProviderHealthMonitor.start()` / `run_forever()` | Bucle idempotente; tick `PROVIDER_HEALTH_TICK_SECONDS = 10.0` |
| `ProviderHealthMonitor.aclose()` | Cancela bucle y sonda en vuelo; sin tareas huérfanas |
| `PROVIDER_HEALTH_MAX_AGE_SECONDS` | **Sigue existiendo** (= 60.0) pero ya **no es la cadencia**: solo eco del defecto |

### 3.3 `bolsa_application.sync_scheduler`

- `GetProviderCheckPolicy(repo).execute() -> ProviderCheckPolicy` — caso de uso propio, para
  que el bucle de salud no arrastre la semántica de las velas.
- `SyncSettingsRecord` gana `provider_check_enabled` y `provider_check_interval_seconds`;
  `get_settings()` crea la fila si falta; `update_settings()` los acepta opcionales.

### 3.4 `bolsa_application.market.GetMarketStatus`

- `GetMarketStatus(configs, *, xtb_health=None, live=True)`.
- `live=False` → **solo lo persistido**, sin petición al bridge. Es la lectura del icono.
- Con `live=True` (default, resto de la app) XTB se mide en vivo contra el bridge.

---

## 4. Mapa de ficheros

### Nuevos

| Fichero | Contenido |
|---|---|
| `packages/py/infrastructure/alembic/versions/060_provider_check_policy.py` | 2 columnas + `CHECK` (`down_revision = 059`), aditiva e idempotente, `downgrade` simétrico |
| `packages/py/application/tests/test_market_providers.py` | 33 pruebas: política, `due`, `stale` vs `unverified`, `probe_if_due`, resumen sin medición |
| `apps/api-python/tests/test_provider_health_startup.py` | 2 pruebas del cableado del `lifespan` con dobles |
| `apps/api-python/tests/test_market_providers_pg.py` | 5 pruebas PG de `market_provider_settings` (de 059, ampliadas) |
| `apps/web/src/features/trading/trading-provider-health-button.tsx` (+ `.test.tsx`) | Icono de servidores con `stale`, tooltip con política y poll adaptativo (9 pruebas) |
| `apps/web/src/features/settings/market-providers-status-card.test.tsx` | 7 pruebas de la tarjeta de proveedores |
| `packages/py/domain/src/bolsa_domain/entities/market_provider.py` | Registro de proveedores (059) **+** `ProviderCheckPolicy` (060) |
| `packages/py/application/src/bolsa_application/market_providers.py` | Resolver, casos de uso (059), resumen y monitor (060) |
| `packages/py/infrastructure/.../repositories/market_provider_settings_repository.py` | Persistencia de `market_provider_settings` (059) |
| `apps/api-python/tests/test_market_providers_api.py` | 17 pruebas: CRUD de 059 **+** salud/política de 060 (`health`, `stale`, OFF, `check` manual, 503) |

### Modificados (esta entrega)

| Fichero | Cambio |
|---|---|
| `.../database/models/tables.py` | Columnas mapeadas en `SyncSettingsRow` |
| `.../repositories/sync_scheduler_repository.py` | Record + `get_settings` + `update_settings` |
| `.../config.py` | `provider_health_probe_on_startup` (alias `PROVIDER_HEALTH_PROBE_ON_STARTUP`, default `True`) |
| `packages/py/application/.../sync_scheduler.py` | `GetProviderCheckPolicy` |
| `packages/py/application/.../market.py` | `live: bool = True` en `GetMarketStatus` |
| `apps/api-python/src/bolsa_api/main.py` | Lifespan: monitor, `probe_if_due()` condicionado al flag, `start()`, `aclose()` |
| `.../api/dependencies.py` | `get_provider_check_policy_use_case`, `get_market_status_use_case(..., live=True)` |
| `.../api/v1/routes/market.py` | `GET health` con `live=False` + `POST health/check` (503 sin monitor) |
| `.../api/v1/routes/sync.py` | `_settings_dto` y PATCH con los dos campos |
| `.../schemas/market.py`, `schemas/sync.py` | DTOs (`autoCheckEnabled`, `checkIntervalSeconds`, `nextCheckAt`, `stale`; `ge=15, le=3600`) |
| `packages/shared/src/types.ts` | `ProviderHealthStatus` + `stale`; `ProviderHealthSummaryDto` con los 3 campos nuevos |
| `packages/shared/src/chart-defaults.ts` | `SyncSettingsDto` + `providerCheckEnabled` / `providerCheckIntervalSeconds` |
| `apps/web/src/lib/api.ts` | `getProviderHealth()` (GET) y `checkProviderHealth()` (POST) |
| `apps/web/src/features/sync/sync-settings-panel.tsx` | Dos bloques rotulados, un Guardar, «Comprobar ahora» (11 pruebas) |
| `apps/web/src/features/settings/market-providers-status-card.tsx` | Estado por proveedor desde la última comprobación |
| `apps/web/src/features/settings/data-sync-summary-card.tsx` | Chip «Servidores cada N s / sin comprobación automática» junto al de auto-sync (testid `data-sync-provider-check`) |
| `apps/web/src/features/config/platform-config-dialog.tsx` | Pestaña «other»: título «Automatización: velas y servidores» y aviso de que son cosas distintas |
| `apps/web/api/openapi.json`, `apps/web/src/api/schema.d.ts` | Contrato regenerado |
| `apps/api-python/tests/conftest.py` | Fixture autouse que apaga la sonda al arrancar en toda la suite |
| 5 tests PG de guardia de head | Constante a `060_provider_check_policy` |
| `docs/MARKET_DATA.md` | §«Dos automatizaciones distintas», diagrama, tabla de colores |
| `docs/engineering/seguimiento-ui-proveedores-2026-10-29.md` | §7 bitácora + evidencia + captura |

---

## 5. Contrato HTTP

| Endpoint | Efecto | Códigos |
|---|---|---|
| `GET /api/market/providers/health` | **Solo lectura** de lo persistido + `ensure_fresh()` no bloqueante | 200 |
| `POST /api/market/providers/health/check` | Mide habilitados **aunque la automática esté OFF** y persiste; devuelve el mismo DTO | 200 · **503** si el proceso no tiene monitor |
| `GET /api/sync/settings` | Publica `providerCheckEnabled`, `providerCheckIntervalSeconds` | 200 |
| `PATCH /api/sync/settings` | Actualiza ambos (opcionales) | 200 · **422** fuera de `15..3600` |

Respuesta de salud (`ProviderHealthSummaryResponseDto`): `status`, `ok`, `measuredAt`,
`probing`, `autoCheckEnabled`, `checkIntervalSeconds`, `nextCheckAt`, `providers[]`.
`probing` es informativo: una tarea puede decidir que no toca medir.

---

## 6. UI

- **Panel** (`sync-settings-panel.tsx`): secciones `sync-block-velas` («Velas (histórico)»,
  «No comprueba servidores») y `sync-block-servidores` («Comprobación de servidores», «Solo
  prueba la conexión: no descarga datos»), un único «Guardar cambios» y «Comprobar ahora»
  (`checkNowMutation` → `api.checkProviderHealth()`, invalida salud y proveedores).
- **Icono** (`trading-provider-health-button.tsx`): tonos `ok` verde, `degraded` rojo,
  `unverified`/`stale` ámbar, `none` gris. Poll `healthPollIntervalMs(summary)` =
  `min(60 s, max(15 s, intervalo/2))`; **120 s** si `autoCheckEnabled === false`.
  Clic → `openPlatformConfig("other")`.
- **Visibilidad del icono**: preferencia persistida en `bolsa-status-bar-prefs-v1`
  (`status-bar-prefs.ts` / `use-status-bar-prefs.ts`, de la entrega 059). El engranaje de la
  barra lo enciende/apaga.

---

## 7. Estado de la BD (verificado hoy, solo lectura)

Consulta: script de 3 tablas vía `create_engine(get_settings())` con `SelectorEventLoop`
(Windows). Resultado literal:

```
HEAD  ['060_provider_check_policy']

COL provider_check_enabled          boolean  default true   NOT NULL
COL provider_check_interval_seconds integer  default 60     NOT NULL
CON sync_settings_provider_check_interval_check
    CHECK (((provider_check_interval_seconds >= 15) AND (provider_check_interval_seconds <= 3600)))

SYNC auto_sync_enabled=True, scan_interval_minutes=30, provider_check_enabled=True, provider_check_interval_seconds=3600

PROV xtb   enabled=True  last_check_at=2026-10-29T12:25:56.446Z  ok=True  "XTB bridge simulado"
PROV yahoo enabled=True  last_check_at=2026-10-29T12:25:55.961Z  ok=True  "Yahoo respondió 18758.7000 (ref. ^IBEX, 1793275850)"
```

**Dos avisos sobre esto:**

1. `provider_check_interval_seconds` quedó en **3600** (valor usado al probar el límite
   superior), no en 60. La documentación lo afirmaba mal y ya está corregida en §7.3. Con
   3600 s el bucle no vuelve a medir hasta una hora después de la última medición; el estado
   actual del icono es `ok` (no `stale`), porque `stale` exige `> 2 × 3600 s`.
2. La fila de `sync_settings` es **única y global**: la cadencia no es por proveedor.

Reproducir sin psql: guarda esto como `_check_db.py` en la raíz y bórralo después (fue lo que
se usó para la tabla de arriba; no deja residuos):

```python
import asyncio, selectors
from sqlalchemy import text
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.session import create_engine

async def main() -> None:
    engine = create_engine(get_settings())
    async with engine.connect() as conn:
        print("HEAD", (await conn.execute(text("select version_num from alembic_version"))).scalars().all())
        print("SYNC", (await conn.execute(text(
            "select provider_check_enabled, provider_check_interval_seconds from sync_settings"
        ))).all())
        print("PROV", (await conn.execute(text(
            "select id, enabled, last_check_at, last_check_ok from market_provider_settings order by id"
        ))).all())
    await engine.dispose()

asyncio.run(main(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
```

```sql
-- equivalente en psql
select version_num from alembic_version;
\d+ sync_settings            -- columnas provider_check_* y su CHECK
select * from sync_settings; -- fila única de automatización
```

---

## 8. Comandos de verificación (con resultado esperado)

```powershell
# Área Python (no-PG): 33 + 17 + 2 = 52
python -m pytest packages/py/application/tests/test_market_providers.py `
  apps/api-python/tests/test_market_providers_api.py `
  apps/api-python/tests/test_provider_health_startup.py -q
# => 52 passed

# Área Python (PG): 52 passed (incluye guardias de head)
python -m pytest apps/api-python/tests/test_discovery_evidence_snapshot_pg.py `
  apps/api-python/tests/test_auto_v57_auto16_applied_cost_pg.py `
  apps/api-python/tests/test_auto_v88_27_durable_facts_idempotent_pg.py `
  apps/api-python/tests/test_signal_alerts_v111_pg.py `
  apps/api-python/tests/test_dia_d_cycle_verification_pg.py `
  apps/api-python/tests/test_market_providers_pg.py -q

# Lint del área tocada
python -m ruff check packages/py/application/src/bolsa_application/market_providers.py `
  packages/py/application/src/bolsa_application/sync_scheduler.py `
  packages/py/domain/src/bolsa_domain/entities/market_provider.py `
  packages/py/infrastructure/alembic/versions/060_provider_check_policy.py `
  apps/api-python/src/bolsa_api/main.py `
  apps/api-python/src/bolsa_api/api/v1/routes/market.py `
  apps/api-python/src/bolsa_api/api/v1/routes/sync.py -q
# => All checks passed!

# Web del área: 11 + 9 + 7 = 27
pnpm --filter @bolsa/web exec vitest run `
  src/features/sync/sync-settings-panel.test.tsx `
  src/features/trading/trading-provider-health-button.test.tsx `
  src/features/settings/market-providers-status-card.test.tsx

# Suite web completa: 343 ficheros / 2577 pruebas
pnpm --filter @bolsa/web test -- --run

# Tipos y contrato
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/web typecheck
pnpm contract:check   # => contract:check OK
```

---

## 9. Trampas que harían alucinar a un agente nuevo

1. **`Settings` usa alias en MAYÚSCULAS.** `Settings(provider_health_probe_on_startup=False)`
   **se ignora en silencio** (`extra="ignore"`). Hay que pasar
   `PROVIDER_HEALTH_PROBE_ON_STARTUP="0"` o `XTB_BRIDGE_URL=None`. Esto hacía que
   `test_provider_health_startup` pasara por la razón equivocada; corregido.
2. **`conftest.py` apaga la sonda en toda la suite** (fixture autouse
   `_isolate_provider_health_startup_probe`), porque decenas de tests entran en el `lifespan`.
   Un test que espere sonda real debe encenderla explícitamente y sustituir el monitor.
3. **`SyncSettingsDto` vive en `chart-defaults.ts`**, no en `types.ts`.
   `ProviderHealthSummaryDto` sí está en `types.ts`. Buscar `providerCheck` en `types.ts`
   devuelve **cero** resultados: no significa que falte el campo.
4. **`live=False` es obligatorio en el GET de salud.** Si alguien «restaura» el default
   `live=True`, cada consulta del icono vuelve a sondear XTB: dos fuentes de verdad y un GET
   con efecto de red.
5. **`summarize_provider_health` sin `policy` nunca da `stale`** (usa la política por
   defecto). `stale` solo aparece si el llamador pasa la política persistida.
6. **Los tests PG de roundtrip hacen `downgrade/upgrade` sobre la BD real `bolsa_v1`.** No
   lanzar la suite completa con `pnpm dev` arriba: puede dejar el esquema a medias y
   **recrear vacía** `market_provider_settings` (documentado en §6 del otro doc).
7. **La head de Alembic está fijada en 5 tests PG.** Si se añade una `061`, hay que
   actualizar esas constantes o los guardias fallan (y ese fallo es correcto).
8. **`PROVIDER_HEALTH_MAX_AGE_SECONDS` ya no es la cadencia.** Solo es el eco del defecto de
   60 s. El valor efectivo sale de `sync_settings`.
9. **`probe_if_due()` devuelve `None` por dos motivos distintos** (OFF y «aún no toca»). El
   `probing` de la API no prueba que se haya medido.
10. **`auto_sync_enabled` no prueba servidores.** Es la confusión original; no reintroducirla
    en textos ni en nombres de variables.
11. **Constante muerta eliminada:** `PROVIDER_HEALTH_POLL_MS = 30_000` (no la usaba nadie y
    contradecía el poll adaptativo). Si la ves en un diff antiguo, está obsoleta.

---

## 10. Deuda declarada y discrepancias abiertas

| ID | Estado | Detalle |
|---|---|---|
| D-1 | **Abierto** | `provider_check_interval_seconds = 3600` en la BD del operador (residuo de probar el límite). Devolver a 60 s desde la UI o con `PATCH /api/sync/settings` |
| D-2 | **No probado en vivo** | El `stale` no se forzó con el stack arriba (exigiría matar el bucle sin tumbar la API). Cubierto por tests unit/API y explicado en el tooltip |
| D-3 | **Por diseño** | Cadencia global (fila única de `sync_settings`), no por proveedor |
| D-4 | **Sin commit** | 059 + 060 + cambios de auditoría conviven en el árbol; ninguna de las dos entregas está commiteada |
| D-5 | **Preexistente, ajeno** | Según §6 del doc anterior: 3 rojos PG de conciliación P&L (1×10⁻⁶ €) y 23 avisos `react-hooks/exhaustive-deps` de otras áreas. No se tocan aquí |
| D-6 | **Aviso** | El icono depende de que el proceso API tenga monitor instalado; si no, `POST check` → 503 (nunca finge medición) |

---

## 11. Punto de partida para «seguir con la BD»

Hechos verificados (no hipótesis): el esquema está en head `060`, las dos columnas existen
con sus defaults y el `CHECK`, y la política efectiva es **ON cada 3600 s**.

Decisiones que **solo el operador** puede tomar (por eso quedan abiertas):

1. **Commit de las dos entregas** (059 + 060) antes de seguir tocando el esquema. Con 90
   ficheros sucios, cualquier migración nueva se vuelve difícil de atribuir.
2. **Intervalo de producto**: devolver a 60 s (defecto) o dejar 3600 s a propósito.
3. **Alcance de la BD**: ¿la siguiente entrega es *esquema* (nueva migración), *datos*
   (backfill de `last_check_at`, limpieza), o *operación* (verificar `downgrade` de 060 en una
   copia antes de producción)?
4. **¿Cadencia por proveedor?** Hoy es global; hacerla por proveedor exige tabla nueva o
   columna en `market_provider_settings` y una migración (061), más un cambio de contrato.

---

## 12. Prompt listo para pegar en el agente nuevo

```text
Contexto: repo Bolsa_V1 (monorepo pnpm + Python, Clean Architecture). Rama
fix/auditoria-2-d1-d4, HEAD 393c45fe. El árbol está SUCIO a propósito: conviven las
entregas 059 (registro de proveedores) y 060 (comprobación de servidores configurable),
ambas sin commit, junto con cambios de la auditoría D1–D4 que NO son de esta área.

Antes de hacer nada, lee ENTERO:
  docs/engineering/handoff-060-comprobacion-servidores-2026-10-29.md
y la §7 de:
  docs/engineering/seguimiento-ui-proveedores-2026-10-29.md
y la sección «Dos automatizaciones distintas (no confundirlas)» de:
  docs/MARKET_DATA.md

Reglas duras de esta área:
- Modelo único de verdad: el estado de un proveedor es su última comprobación persistida
  (market_provider_settings.last_check_*). Ningún GET mide; GET /api/market/providers/health
  usa GetMarketStatus(live=False). "Comprobar ahora" es POST /api/market/providers/health/check.
- Dos automatizaciones distintas: autoSyncEnabled (velas OHLCV) ≠ providerCheckEnabled
  (solo conectividad). No las mezcles en código ni en textos.
- No inventes estado: sin medición es `unverified`; proveedor deshabilitado no pinta rojo;
  `stale` solo con política ON y edad > 2 × intervalo.
- settings usa alias en MAYÚSCULAS (Settings(PROVIDER_HEALTH_PROBE_ON_STARTUP="0")); los
  kwargs en minúsculas se ignoran en silencio.
- No lances la suite Python completa con `pnpm dev` arriba: los tests de roundtrip de
  Alembic hacen downgrade/upgrade sobre la BD real bolsa_v1.
- SyncSettingsDto está en packages/shared/src/chart-defaults.ts, NO en types.ts.

Estado verificado de la BD (2026-10-29): alembic_version = 060_provider_check_policy;
sync_settings.provider_check_enabled = true; provider_check_interval_seconds = 3600
(residuo de probar el límite superior; el defecto de producto es 60); el CHECK
sync_settings_provider_check_interval_check exige 15..3600.

Ahora vamos a seguir con la BD. Antes de escribir código:
1) Confirma con comandos de solo lectura el estado que acabo de describir (migración head,
   columnas, valores de la fila única de sync_settings) y dime si algo no cuadra.
2) Dime qué opciones ves para el siguiente paso de BD y sus riesgos, sin tocar nada todavía.
3) Espera mi decisión sobre: commit de 059+060, intervalo definitivo (60 vs 3600) y si el
   siguiente trabajo es esquema, datos u operación.

No commitees, no ejecutes migraciones destructivas y no edites el plan.
```

---

## 13. Prompt corto (si prefieres seguir en esta misma conversación)

```text
Sigue con la BD. Relee docs/engineering/handoff-060-comprobacion-servidores-2026-10-29.md,
verifica el estado con comandos de solo lectura (head de Alembic, columnas
provider_check_*, valores de sync_settings) y propón opciones antes de tocar nada.
```
