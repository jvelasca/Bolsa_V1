# Audit Pack — V2.40.2 / Claves naturales únicas · reconciliación Prisma→Alembic + upsert atómico (2026-09-15)

> **Punto de entrada único para auditoría externa desde GitHub**, sin acceso al entorno.
> Fase: **v2.40.2** — completa la reconciliación de esquema que faltaba desde la degradación de
> Prisma a cliente de solo lectura (F3b): las **8 claves naturales** que Prisma declaraba y el
> baseline Alembic nunca creó pasan a existir como índice único, y las **tres escrituras** que
> podían violarlas pasan a ser atómicas.
>
> **Base auditada:** `v2.40.1-beta` (`1.65.1-beta`).
> **Bump:** `1.65.1-beta` → **`1.65.2-beta`**.
> **Alembic head:** `041_unique_natural_keys` (**una migración nueva**, ver §3).
> **Flags:** sin cambios. `AUTO_ENGINE_SIM_V2` sigue **OFF por defecto**.
> **Alcance del cambio:** DDL aditivo + 3 escrituras. **No** toca ledger, settlement, `RiskGate`,
> reconciliación ni el pipeline de decisión de AUTO.
> **Sello CI:** esta fase **no** reclama un run de GitHub (patrón honesto del repo: no se afirma CI
> de un commit aún no publicado). La evidencia de ejecución es **local** y está en §6, con la
> batería **exacta** de los jobs afectados.
> **Origen:** hallazgo en vivo, no en auditoría de escritorio — el error estaba en la consola del
> dev server mientras se cerraba la fase anterior.

---

## 0. Resumen ejecutivo

`GET /api/instrument-daily-opinions` (Estudio) devolvía **500 permanente**:

```
instrument_strategy_top_repository.py:60  row = (await self._session.execute(stmt)).scalar_one_or_none()
sqlalchemy.exc.MultipleResultsFound: Multiple rows were found when one or none was required
```

La causa raíz tenía **dos mitades**, y arreglar una sola no bastaba:

| Mitad              | Qué fallaba                                           | Por qué                                                                                                                                                                               |
| ------------------ | ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Backstop de BD** | La tabla no tenía `UNIQUE (instrument_id, timeframe)` | Prisma sí lo declaró, pero el baseline Alembic (003) solo copia columnas y constraints de FK/`UniqueConstraint` de `tables.py`; al no estar en el modelo, **el índice nunca se creó** |
| **Atomicidad**     | `upsert` era un _check-then-insert_                   | `get()` → `INSERT`: dos escritores concurrentes ven `None` e insertan ambos                                                                                                           |

Y lo que lo hacía **irrecuperable** (no un 500 transitorio): `get()` usa `scalar_one_or_none()` y el
propio `upsert` empieza llamando a `get()`, de modo que el instrumento duplicado quedaba envenenado
**para siempre** — ninguna petición posterior podía repararlo.

Evidencia en la BD de desarrollo: **12 grupos duplicados / 24 filas** en
`instrument_strategy_tops`, con pares de `created_at` a **7-8 ms** de distancia
(`19:32:20.065952` vs `19:32:20.071963`), del barrido del **2026-09-14 19:32**. Es exactamente la
firma de una carrera de inserción.

El diagnóstico no se quedó en una tabla: comparando los **10 `@@unique` de `schema.prisma`** contra
la BD viva, **8 tenían el mismo drift**. Este audit-pack documenta el inventario medido, el arreglo
de las 8 claves y las **3 escrituras no atómicas** del repo, y por qué solo una de esas claves se
deduplica automáticamente.

---

## 1. Inventario medido (antes de escribir la migración)

Medido contra la BD de desarrollo el 2026-09-15, con nombres de columna **reales** resueltos vía
`information_schema` (Prisma usa `camelCase`, PostgreSQL `snake_case` — la primera pasada del
inventario dio un falso "10/10 ausentes" precisamente por eso):

| tabla                          | clave natural                              |  filas | grupos dup | filas implicadas |
| ------------------------------ | ------------------------------------------ | -----: | ---------: | ---------------: |
| **`instrument_strategy_tops`** | `(instrument_id, timeframe)`               |     46 |     **12** |           **24** |
| `instruments`                  | `(symbol, exchange)`                       |    243 |          0 |                0 |
| `instrument_daily_opinions`    | `(instrument_id, as_of_bar_date, source)`  |    160 |          0 |                0 |
| `instrument_list_items`        | `(list_id, instrument_id)`                 |    112 |          0 |                0 |
| `ohlcv_bars`                   | `(instrument_id, timeframe, timestamp)`    | 95 224 |          0 |                0 |
| `positions`                    | `(portfolio_id, instrument_id)`            |      0 |          0 |                0 |
| `transactions`                 | `(portfolio_id, idempotency_key)`          |      0 |          0 |                0 |
| `data_snapshots`               | `(instrument_id, timeframe, data_version)` |      0 |          0 |                0 |
| `position_policies`            | `(account_id, instrument_id)`              |      0 |          0 |                0 |
| `instrument_narratives`        | `(instrument_id, scope)`                   |      0 |          0 |                0 |

**Presentes ya en la BD (2/10):** `ohlcv_bars` y `transactions` — precisamente los dos que alguien
ató 1:1 en una migración anterior (`ohlcv_bars` con el comentario _"Reconciliado en Alembic 023;
debe coincidir 1:1 con la migración para no re-driftar"_). El resto se quedó atrás.

**Consecuencia:** solo `instrument_strategy_tops` tenía duplicados ⇒ las otras 7 claves se pudieron
crear **sin borrar ni una fila**.

---

## 2. Qué se puede romper y qué no (revisión de los 8 escritores)

Crear un índice único convierte un duplicado silencioso en un `IntegrityError`. Por eso, antes de
crear los índices se revisó **quién escribe** en cada tabla:

| tabla                       | writer                | patrón                                                   | ¿cambio de código?                        |
| --------------------------- | --------------------- | -------------------------------------------------------- | ----------------------------------------- |
| `instrument_strategy_tops`  | `upsert`              | `get()` → INSERT/UPDATE                                  | **SÍ — `ON CONFLICT`** (el del incidente) |
| `instrument_narratives`     | `upsert`              | `get()` → INSERT/UPDATE                                  | **SÍ — `ON CONFLICT`**                    |
| `instrument_daily_opinions` | `upsert`              | `get()` → INSERT/UPDATE                                  | **SÍ — `ON CONFLICT`**                    |
| `positions`                 | `_apply_trade_writes` | `begin_nested()` + lock de cartera + idempotencia (R-8A) | No (backstop)                             |
| `position_policies`         | `create_policy`       | el caso de uso lanza `ValueError` si ya existe           | No (backstop)                             |
| `instruments`               | `create`              | guarda por `yahoo_symbol` (ya único) + import de usuario | No (backstop)                             |
| `instrument_list_items`     | `replace_all`         | dedupe en memoria + delete/insert en una transacción     | No (backstop)                             |
| `data_snapshots`            | `upsert_snapshot`     | upsert **por `id`** (`on_conflict_do_nothing`)           | No (backstop)                             |

El **mismo patrón tóxico** (`get()` → INSERT/UPDATE) estaba en **tres** repositorios. Los tres se
arreglaron; los otros cinco tenían guarda propia.

> **Nota de honestidad sobre `data_snapshots`:** su `upsert` resuelve el conflicto **por `id`**, no
> por la clave natural. El índice único le queda como backstop: insertar un snapshot con **otro
> `id`** pero la misma `(instrument_id, timeframe, data_version)` ahora falla en vez de duplicar.
> Es la dirección deseada (fail-closed) y no se cambió su writer porque la tabla tiene 0 filas y el
> camino es legacy; se documenta en vez de tocarlo a ciegas.

---

## 3. La migración `041_unique_natural_keys`

### 3.1 Las 8 claves, con los nombres canónicos de Prisma

| tabla                       | índice creado                                             | columnas                                 |
| --------------------------- | --------------------------------------------------------- | ---------------------------------------- |
| `instruments`               | `instruments_symbol_exchange_key`                         | `symbol, exchange`                       |
| `positions`                 | `positions_portfolio_id_instrument_id_key`                | `portfolio_id, instrument_id`            |
| `data_snapshots`            | `data_snapshots_instrument_timeframe_version_idx`         | `instrument_id, timeframe, data_version` |
| `position_policies`         | `position_policies_account_instrument_idx`                | `account_id, instrument_id`              |
| `instrument_daily_opinions` | `instrument_daily_opinions_instrument_id_asof_source_key` | `instrument_id, as_of_bar_date, source`  |
| `instrument_narratives`     | `instrument_narratives_instrument_id_scope_key`           | `instrument_id, scope`                   |
| `instrument_strategy_tops`  | `instrument_strategy_tops_instrument_timeframe_uq`        | `instrument_id, timeframe`               |
| `instrument_list_items`     | `instrument_list_items_list_id_instrument_id_key`         | `list_id, instrument_id`                 |

Se usan los **nombres de Prisma** a propósito: si una BD viniera del Prisma histórico, los guards
`_index_exists` los detectan como existentes y no se recrea nada (idempotencia entre orígenes).

### 3.2 El detalle que atrapó PostgreSQL, no el test

El primer `alembic upgrade head` **falló**:

```
sqlalchemy.exc.IdentifierError: Identifier
  'instrument_daily_opinions_instrument_id_as_of_bar_date_source_key' exceeds maximum length of 63 characters
```

El nombre que declaró Prisma tiene **65 caracteres** y PostgreSQL **lo habría truncado en
silencio** al crearlo (límite de 63). Se usa
`instrument_daily_opinions_instrument_id_asof_source_key` (55), explícito y sin truncamiento; es la
**única** clave que no converge al nombre de Prisma, y está comentada como tal en el modelo.

### 3.3 Dedupe conservador

- **`instrument_strategy_tops`** (única con duplicados): se conserva la fila más reciente
  `ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST, id DESC` (desempate
  determinista completo) y se borran las demás. Es una **caché derivada** del embudo coach: la más
  nueva es la vigente por construcción. Efecto medido: **46 → 34 filas**.
- **Las otras 7: cero borrados automáticos.** Si alguna tuviera duplicados al aplicar, la migración
  **aborta** nombrando tabla, columnas y hasta 5 filas de muestra. Razón explícita:
  `instruments`/`positions` cascadean a datos financieros
  (`OHLCV`, ledger, posiciones) y `position_policies`/`instrument_narratives` son contenido de
  usuario: **esa decisión no es de una migración**. Fail-closed: un bloqueo visible es mejor que una
  pérdida silenciosa.

### 3.4 Guards y reversibilidad

Patrón 028–040: `_table_exists` / `_columns_exist` / `_index_exists` antes de cada DDL (offline-safe
y no-op si la tabla aún no existe, p. ej. una BD anterior al baseline). El `downgrade` retira los 8
índices con el mismo guard. Cadena lineal `040 → 041`.

---

## 4. Las tres escrituras atómicas

`SELECT` + `INSERT`/`UPDATE` sustituido por un único `INSERT … ON CONFLICT DO UPDATE … RETURNING`:

| repositorio                                  | clave de conflicto                        | semántica preservada                                                                                                     |
| -------------------------------------------- | ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `instrument_strategy_top_repository.upsert`  | `(instrument_id, timeframe)`              | `version` = existente + 1; `symbol` se conserva si el llamante no aporta uno (`coalesce`); `id` no cambia                |
| `instrument_narrative_repository.upsert`     | `(instrument_id, scope)`                  | `version` = existente + 1; validaciones (`scope`/`source`/cuerpo) intactas                                               |
| `instrument_daily_opinion_repository.upsert` | `(instrument_id, as_of_bar_date, source)` | `idempotency_key` **no** se reescribe en conflicto (se fija al crear); sigue habiendo un `UNIQUE` propio sobre esa clave |

El `ON CONFLICT` infiere el índice por columnas, así que funciona tanto si el backstop es un
`UniqueConstraint` (modelo) como un `Index(..., unique=True)` creado por la migración.

**Por qué las mitades debían entrar juntas:** el índice solo (sin tocar los `upsert`) habría
cambiado el duplicado silencioso por un `IntegrityError`; el `ON CONFLICT` solo (sin índice) no
tiene nada contra lo que conflictuar y seguiría duplicando. Ninguna de las dos mitades es
suficiente por separado.

---

## 5. Cambio de comportamiento observable

1. **Un `INSERT` crudo duplicado sobre cualquiera de las 8 claves falla** con `IntegrityError`. Es
   el objetivo (fail-closed) y está certificado por un test que **no** pasa por el repositorio.
2. **Bases con duplicados en las 7 tablas no deduplicadas bloquean el `upgrade`** con un mensaje
   explícito. La BD de desarrollo está limpia (0 grupos en las 10 claves) y la migración se aplicó
   sin incidencias.
3. **Ningún cambio de contrato HTTP, de wire ni de flags.** El endpoint afectado deja de devolver
   500 y vuelve a devolver el dictamen.

---

## 6. Verificación (evidencia y batería exacta)

| Comprobación                       | Comando                                                                                                              | Resultado                                                          |
| ---------------------------------- | -------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| Lint                               | `uv run ruff check packages/py apps/api-python --config pyproject.toml`                                              | **0**                                                              |
| Formato                            | `uv run ruff format` sobre los ficheros tocados                                                                      | aplicado                                                           |
| Tipos                              | `uv run mypy packages/py/{domain,market,infrastructure,application}/src apps/api-python/src --follow-imports=silent` | **0 errores** (482 ficheros)                                       |
| Fronteras                          | `uv run lint-imports --config packages/py/.importlinter`                                                             | **4 kept, 0 broken**                                               |
| Batería offline (`quality`)        | `domain/market/analytics/application` + `apps/api-python` con los `--ignore` del job                                 | **2793 passed**                                                    |
| Infraestructura                    | `packages/py/infrastructure/tests`                                                                                   | **138 passed, 1 xfailed**                                          |
| Job `auto-v2-durable-pg` (PG real) | 4 ficheros abajo, `-rs`                                                                                              | **28 passed, 0 skipped**                                           |
| Migración en la BD de desarrollo   | `alembic upgrade head`                                                                                               | head **`041`**, 8 claves presentes, tops **46 → 34**, 0 duplicados |

Ficheros del job PG (equivalente local del job `auto-v2-durable-pg`):

```
apps/api-python/tests/test_unique_natural_keys_pg.py      (7 nuevos)
apps/api-python/tests/test_instrument_trade_context_pg.py
apps/api-python/tests/test_auto_v2_durable_pg.py
apps/api-python/tests/test_discovery_evidence_snapshot_pg.py   (_ALEMBIC_HEAD: 040 → 041)
```

---

## 7. Tests nuevos y qué certifica cada uno

`apps/api-python/tests/test_unique_natural_keys_pg.py` — gate fail-if-skipped
`UNIQUE_NATURAL_KEYS_PG_REQUIRED=1` (un skip silencioso es un fallo duro, patrón del repo):

| test                                                                   | qué certifica                                                                                                                                                                                        |
| ---------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `test_the_eight_natural_keys_have_a_unique_index`                      | **Anti-deriva**: las 8 claves existen como `UNIQUE INDEX` en `pg_indexes`. Sin este test, la reconciliación se vuelve a perder en la siguiente tabla que alguien añada "solo en Prisma"              |
| `test_concurrent_top_upsert_yields_a_single_row`                       | **Regresión del incidente**: dos `upsert` concurrentes del mismo `(instrument_id, timeframe)` ⇒ UNA fila, sin excepción                                                                              |
| `test_the_unique_index_rejects_a_raw_duplicate_row`                    | **Backstop real**: un `INSERT` crudo duplicado lanza `IntegrityError` (certifica fail-closed sin pasar por el repositorio)                                                                           |
| `test_top_upsert_keeps_symbol_and_bumps_version`                       | Semántica conservada: `id` estable, `version` 1→2, `symbol` previo conservado si no se aporta                                                                                                        |
| `test_concurrent_narrative_upsert_yields_a_single_row`                 | El mismo patrón tóxico en narrativas, cerrado                                                                                                                                                        |
| `test_concurrent_daily_opinion_upsert_yields_a_single_row`             | El dictamen diario (el que rompía la ruta): una fila por `(instrumento, día, fuente)`                                                                                                                |
| `test_migration_041_dedupes_existing_duplicates_and_recreates_indexes` | **Roundtrip con duplicados previos**: `downgrade` a 040, se insertan a mano dos filas de la misma clave con distinto `updated_at`, `upgrade` a `head` ⇒ queda **la más reciente** y el índice vuelve |

---

## 8. Tests de mutación sugeridos al auditor

Para verificar que los tests **no son decorativos** (deben FALLAR si se rompe el arreglo):

1. **Quitar el índice** (comentar un `op.create_index` de la 041) ⇒ debe fallar
   `test_the_eight_natural_keys_have_a_unique_index`.
2. **Revertir el `upsert` de tops** a `get()` + INSERT ⇒ debe fallar
   `test_concurrent_top_upsert_yields_a_single_row` (vuelven a quedar 2 filas).
3. **Cambiar el orden del dedupe** a `ASC` ⇒ debe fallar el roundtrip (quedaría `ist_old`).
4. **Convertir el índice en no-único** en la 041 ⇒ debe fallar
   `test_the_unique_index_rejects_a_raw_duplicate_row` (no habría `IntegrityError`).
5. **Añadir una tabla nueva con clave natural solo en `schema.prisma`** ⇒ el test anti-deriva no la
   conoce todavía (es una lista explícita): esto es una limitación **conocida y declarada**, no un
   bug — la lista debe crecer con cada tabla nueva hasta que exista un generador de drift que
   compare `schema.prisma` con `pg_indexes` (fuera de alcance de esta fase, ver §9).

---

## 9. Fuera de alcance (declarado, no olvidado)

- **Generador automático de drift** `schema.prisma` ↔ `pg_indexes`: el inventario de esta fase fue
  manual. Un test que derive las claves del propio `schema.prisma` cerraría el problema de raíz
  (toda tabla futura quedaría cubierta sin lista explícita). Es el candidato natural a la siguiente
  fase.
- **`data_snapshots.upsert_snapshot`**: sigue resolviendo por `id`; su backstop natural-key solo
  actúa como red.
- **Deuda de formato**: `ruff format --check` no es gate del CI y arrastra drift previo; solo se
  formatearon los ficheros tocados en esta fase.
