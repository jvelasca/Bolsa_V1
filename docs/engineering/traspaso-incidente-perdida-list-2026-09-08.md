# INCIDENTE — Perdida de las listas propias y de la lista 'estudio' (datos runtime) — 2026-09-08

> **Padre:** [engineering-index](./engineering-index-2026-08-03.md) · contexto de datos [`traspaso-relevo-cierre-auditoria-v214-hotfixes-2026-09-08.md`](./traspaso-relevo-cierre-auditoria-v214-hotfixes-2026-09-08.md) (schema-drift OHLCV y remedio 023).
> **Estado:** **DIAGNÓSTICO CONFIRMADO** (solo lectura). Recuperación **RESUELTA**: el usuario **asume la pérdida** (sin backup externo) y **recreará listas/'estudio' a mano desde la UI** (ver §6). Prevención pendiente (§6.3). No se ha tocado código ni datos.
> **Síntoma:** tras reiniciar todo (incl. el PC), en la UI no se cargan las listas propias ni 'estudio' ni sus valores ("no se muestra nada").

---

## 1. Método y alcance

Verificación **en vivo y en repositorio, solo lectura** (ninguna mutación):

- API local `http://localhost:8000` (`GET /health`, `GET /api/lists`, `GET /api/lists/{id}/quotes`).
- Base de datos `bolsa_v1` (docker `bolsa-postgres`, `psql -U bolsa`), solo `SELECT`.
- Código de seed/migraciones/use-cases de listas en el monorepo.

---

## 2. Diagnóstico confirmado

### 2.1 Backend sano — NO es un problema de barras/freshness

| Verificación                   | Resultado                                                                                                           |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------- |
| `GET /api/health`              | `status=ok`, DB conectada, Alembic `023_ohlcv_bars_unique_reconcile`, provenance `1.43.2-beta` / `2a98886c`.        |
| `GET /api/instruments`         | 35 instrumentos IBEX.                                                                                               |
| `GET /api/lists`               | **solo 2 listas**: `estudio[0]`, `ibex35[35]`.                                                                      |
| `GET /api/lists/ibex35/quotes` | **35 filas con precio**: `freshnessStatus=current`, `barCount≈1278–1279`, `lastBar=2026-09-08`, `lastSync=success`. |

Conclusión parcial: el catálogo IBEX **carga con precios y freshness `current`**. El histórico/barras está presente y sano. El síntoma NO es un fallo de sincronización OHLCV ni de `freshness`.

### 2.2 Pérdida real de filas runtime en `bolsa_v1` (solo SELECT)

```
SELECT                               valor
alembic_version                      023_ohlcv_bars_unique_reconcile
count(*) instrument_lists            2
count(*) instrument_list_items       35
count(*) ohlcv_bars                  44733
count(*) investment_accounts         1
count(*) users                       0
count(*) decision_sessions           0
count(*) instrument_daily_opinions   0
```

Filas de `instrument_lists`:

```
ibex35 :: IBEX 35 :: catalog :: linked_universe
estudio :: Estudio :: custom :: supervision_universe
```

Items por lista: `ibex35 :: items=35` (no hay filas de items de `estudio` ni de listas propias).

Interpretación: la BD quedó en **estado bootstrap/seed**: el catálogo `ibex35` (35) intacto y la lista canónica `estudio` relegada a un **stub vacío** (0 items). Las listas propias/custom y todas las membresías de 'estudio' **ya no existen** en la tabla.

### 2.3 Por qué 'estudio' aparece como stub vacío (comportamiento de código)

`SqlAlchemyListRepository.ensure_estudio_list` ([list_repository.py:397-427](./../py/infrastructure/src/bolsa_infrastructure/database/repositories/list_repository.py)): si la lista canónica `estudio` no existe, la **crea con membresía vacía** `instrument_ids=[]` (kind `supervision_universe`); si ya existe, solo la renombra o fusiona el legacy "Estudio personal". **Nunca añade instrumentos por sí sola ni la borra.** Se invoca en cada camino de listado vía `ListInstrumentLists.execute` ([lists.py:50-52](./../py/application/src/bolsa_application/lists.py) → `await self._list_repo.ensure_estudio_list()`). Por tanto un arranque con la membresía ausente reproduce un `estudio` vacío por diseño.

### 2.4 El repositorio NO tiene un path global destructivo para listas

- **Seed**: `packages/database/prisma/seed.ts` solo hace `upsert` de instrumentos IBEX + una cartera demo; **no hace DELETE** ni escribe `instrument_lists`.
- **Migraciones Alembic** 001–023 (y Prisma legacy): append-only / `if_not_exists`, **ninguna DROP/TRUNCATE** de `instrument_lists`/`instrument_list_items`/`decision_sessions`/`instrument_daily_opinions`/`users`.
- **Reconciliación de índices**: `SyncSubscribedCatalogIndices` ([market_indices.py:306-309](./../py/application/src/bolsa_application/market_indices.py)) hace `if summary.source != "catalog" and summary.kind != "linked_universe": continue` — **solo** toca listas `catalog`/`linked_universe`, no listas custom ni `estudio` (`source=custom`).
- **Toda escritura de membresía** (`_replace_items`) está acotada por `list_id`.

Conclusión: **ningún seed/migración/reconcile del repo puede borrar listas propias ni la membresía de 'estudio'.** El arranque por `db:ensure`/`run-dev` es no destructivo (Alembic idempotente + seed `upsert`); el volumen docker `bolsa_pg_data` está descrito como persistente entre reinicios (`scripts/lib/docker.mjs`, "no se pierden al reiniciar").

### 2.5 Veredicto de causa raíz (honesto)

Dado que **conviven** 44.733 barras y 1 cuenta conservadas con **filas runtime vacías** (listas custom, estudio, decision_sessions, daily_opinions, users), la explicación con más peso es:

> Estas filas `estudio`/custom/cognitive de usuario eran **estado 100% runtime en PostgreSQL** (creadas por llamadas de la UI, nunca versionadas). En un punto la BD quedó en estado de datos mínimos/bootstrap y la reconstrucción documentada (schema-drift V2.14, [`traspaso-relevo-cierre-auditoria-v214-hotfixes-2026-09-08.md`](./traspaso-relevo-cierre-auditoria-v214-hotfixes-2026-09-08.md) §2: BD local "0 barras / listas vacías", reconstruida luego a catálogo IBEX + barras) **nunca restauró las listas/membresías de usuario** — solo el catálogo IBEX (35) y el histórico OHLCV.

No es posible viajar al pasado del volumen `bolsa_pg_data` desde el repo para distinguir entre "las filas se borraron en el reset del drift" y "nunca se llevaron al estado reconstruido" — ambas ramas convergen en el mismo resultado y en **no poder reconstruirlas desde el codebase**.

---

## 3. Qué NO es (rúbrica para descartar)

- NO es un fallo de sincronización OHLCV ni de `freshness` (ibex35 carga con precio y `current`).
- NO es un bug de frontend de rendering (los datos del catálogo se sirven y el estado de listas viaja por API).
- NO lo causa el seed ni una migración destructiva (no hay DELETE/TRUNCATE de listas en el repo).
- NO es un problema de la cuenta activa (existe 1 cuenta; el problema es ausencia de membresías/listas).
- NO es un "re-Seed que borra": `db:ensure` es idempotente/no-destructivo sobre listas.

---

## 4. Estado real para la recuperación

**Recuperable desde el repo: NO.** Las listas propias y la membresía de 'estudio' no constan en git (sin fixture/seed/JSON de datos) ni en ningún volcado. Barrido en disco de candidatos de backup (`*.sql`/`*.dump`/`*.bak`/`pg_dump`/carpetas docker volume) en el repo y en `Informatica`/`.cursor`: **no existe ningún volcado de datos** de `bolsa_v1`.

La **única** vía de restauración sería un **backup/snapshot externo** del usuario (fuera del repo): snapshot del volumen docker `bolsa_pg_data`, Time Machine / File History, un `pg_dump` manual previo, o una copia del volumen previa al incidente.

---

## 5. Prevención recomendada (faena de código POSTERIOR, no esta tanda)

Para que esto no se repita sin copia:

1. Script `db:dump`/backup automático de `bolsa_v1` (pg_dump programado) o snapshot del volumen.
2. Plantilla/seed declarativa y opcional de las listas canónicas/custom (renombrable por el usuario) para regenerar 'estudio'/listas tras un reset.
3. Documentar el flujo de "volver a poblar" en el arranque por si toca reconstruir.

No se implementa ahora; queda registrada como deuda de robustez.

---

## 6. PASO SIGUIENTE — DECISIÓN DEL USUARIO (RESUELTA)

### 6.1 Comprobaciones externas (respuestas del usuario, 2026-09-08)

1. **Backup externo de `bolsa_v1`: NO.** No existe snapshot de `bolsa_pg_data`, pg_dump ni File History que cubra el volumen previo a la pérdida.
2. **Instancia**: las listas vivían en esta `bolsa_v1` local exacta (contenedor `bolsa-postgres`); no hay otra BD/checkout que las conserve.
3. Incidió la pérdida ligada al estado de datos mínimos del schema-drift V2.14 (BD quedó a "0 filas runtime" y el remedio solo reconstruyó catálogo IBEX + barras).

### 6.2 Decisión adoptada

> **No recuperable desde backup ⇒ se asume la pérdida y se recrean las listas propias y la lista 'estudio' a mano desde la UI.** (Catálogo IBEX y barras ya están correctos; la pérdida afecta solo a membresías custom/estudio creadas por el usuario.)

Esta tanda ha sido **solo diagnóstico**; la recreación la ejecuta el usuario en la UI (añadir instrumentos a su(s) lista(s) y a la lista `estudio`).

### 6.3 Prevención recomendada (faena de código POSTERIOR, pendiente)

Para no repetir la pérdida sin copia:

1. **Script `db:dump`/backup automático** de `bolsa_v1` (pg_dump programado o snapshot del volumen `bolsa_pg_data`).
2. **Plantilla/seed declarativa de arranque** para las listas canónicas/custom (regenerables por el usuario), de forma que un reset no borre la config de 'estudio'/listas sin aviso ni copia.
3. Documentar el flujo "volver a poblar" post-reset en el arranque.

Esta faena de prevención NO se implementa en el presente documento (pendiente de que el usuario la dispare); queda registrada como deuda de robustez para evitar recurrencia.

---

FIN DEL DOCUMENTO DE INCIDENTE — 2026-09-08. Diagnóstico confirmado. Decisión del usuario: asumir pérdida y recrear a mano desde la UI (§6). Prevención pendiente (§6.3). Cero mutaciones realizadas.
