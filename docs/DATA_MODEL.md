# Modelo de datos

## Diagrama ER (v1)

```
instruments ──┬──< ohlcv_bars
              └──< data_sync_log

investment_accounts ──┬──< investment_portfolios ──> portfolios (legacy)
                      │         │
                      │         └── legacy_portfolio_id
                      ├──< ledger_entries
                      └──< pending_orders

portfolios ──┬──< positions
             └──< transactions
```

## Tablas de mercado

> Detalle de ingesta / sync: [MARKET_DATA.md](./MARKET_DATA.md) · Ayuda sync **2026-07-23**.
> Mantenimiento: **Configuración → BD** — diagnóstico **read-only** (esquema/head, capacidad,
> vacuum/analyze, conexiones, integridad y estado de copias) más la acción «Crear copia
> ahora», huérfanos de instrumentos, demos cerradas y purga segura. El diagnóstico no
> escribe: ni VACUUM ni migraciones desde la UI; la copia solo lee la BD y escribe un fichero.

```
instruments ──┬──< ohlcv_bars
              ├──< data_sync_log
              └── (JSON) profile_snapshot, last_xtb_validation

sync_settings (singleton default)
sync_queue ──> instrumentos pendientes de sync
instrument_lists ──< instrument_list_items ──> instruments
```

### Ciclo de vida del instrumento

1. **Import / seed** → fila en `instruments` (+ sync OHLCV).
2. **Membresía** → `instrument_list_items` (listas catálogo o personalizadas). Las listas virtuales de UI no escriben aquí.
3. **Huérfano** → sin filas en `instrument_list_items`. Con `sync_settings.scope=lists` deja de encolarse; los datos permanecen.
4. **Purga** → `DELETE instruments` con cascade Prisma (OHLCV, alertas, sync log/queue, list items, backtests ligados, etc.). Bloqueada en app si hay posiciones u órdenes pendientes. Los rastreadores guardan IDs en JSONB (no FK): hay que editar su universo a mano si apuntaban al valor.

### `instruments`

Catálogo de acciones. Símbolo interno + símbolo Yahoo explícito.

| Campo | Tipo | Notas |
|-------|------|-------|
| symbol | string | Ej. `IBE` |
| yahoo_symbol | string unique | Ej. `IBE.MC` |
| exchange | string | `BME` para IBEX |
| country | string | Default `ES` |
| type | enum | Solo `stock` |
| is_active | bool | Para baja lógica |
| profile_snapshot | jsonb? | Perfil UI + `fundamentals` v3 (`yahoo_quote_summary_v3`) |
| last_xtb_validation | jsonb? | Última validación live vs cierre BD |

### `ohlcv_bars`

Velas OHLCV. Sync explícita escribe `1d`; otros TF se cachean bajo demanda (ADR-007).

| Campo | Tipo | Notas |
|-------|------|-------|
| instrument_id | FK | |
| timeframe | enum | `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1wk`, `1mo` |
| timestamp | timestamptz / date | Clave de vela |
| open/high/low/close | decimal | Precisión 18,6 |
| volume | bigint | |
| adj_close | decimal? | Ajuste splits/dividendos |
| source | enum | `yahoo` \| `xtb` (histórico actual: yahoo) |

**Índice único:** `(instrument_id, timeframe, timestamp)`

### `data_sync_log`

Auditoría de sincronizaciones Yahoo y validaciones XTB (`provider`, estado, mensajes).

### `sync_settings` / `sync_queue`

Knobs de sync automática (`auto_sync_enabled`, intervalos, backoff, `post_market_only`, …) y cola de trabajo con reintentos.

**Dos automatizaciones distintas (no confundirlas):**

| Columna | Automatización | Qué hace |
|---------|----------------|----------|
| `auto_sync_enabled` | Velas OHLCV | Escanea y encola instrumentos desfasados; descarga históricos |
| `provider_check_enabled` | Servidores (060) | Solo comprueba conectividad de los proveedores habilitados; **no** descarga datos |
| `provider_check_interval_seconds` | Servidores (060) | Cadencia de la comprobación, segundos (CHECK 15–3600, nombre `sync_settings_provider_check_interval_check`) |

La política de servidores se persiste en `sync_settings` porque es «automatización» (misma
fila, misma pantalla), pero el bucle de salud la lee con su propio caso de uso
(`GetProviderCheckPolicy`) y no arrastra la semántica de las velas.

### `market_provider_settings` (migración 059)

Registro de proveedores con configuración efectiva y **estado medido**:

| Campo | Tipo | Notas |
|-------|------|-------|
| id | PK | `yahoo`, `xtb` (registro cerrado en dominio) |
| enabled | bool | Deshabilitado ⇒ no se resuelve para ninguna capacidad (fail-closed) |
| priority | int | Orden de preferencia por capacidad |
| min_interval_seconds | int | Throttle del cliente (Yahoo) |
| base_url | string? | Override de la URL del bridge (XTB) |
| capabilities / description | jsonb / string | Qué sabe hacer el proveedor |
| last_check_at | timestamptz? | **Última medición persistida** (fuente de verdad del icono) |
| last_check_ok | bool? | Resultado de esa medición |
| last_check_message | text? | Motivo legible |

Regla del área: sin `last_check_at` el estado es «sin verificar»; un proveedor
deshabilitado no se pinta en rojo. `GET /api/market/providers/health` lee **solo** lo
persistido (nunca sondea); la comprobación real es el `POST .../health/check` o el monitor.

## Mantenimiento e integridad (head `060_provider_check_policy`)

`GET /api/database/maintenance` (Configuración → BD) publica, sin escribir:

- **Esquema**: revisión de `alembic_version` frente al head del código; tablas/columnas y
  constraints que faltan; tablas fuera del contrato y **allowlist de divergencias históricas**
  declaradas (`bolsa_infrastructure.database.schema_contract.KNOWN_SCHEMA_DIVERGENCES`).
  `alembic check` usa la misma lista vía `include_object`, así que vuelve a ser un gate: una
  diferencia nueva falla.
- **Capacidad**: `pg_database_size` + top de tablas por `pg_total_relation_size`.
- **Mantenimiento**: `autovacuum`, `naptime`, tuplas muertas por tabla y transacciones abiertas.
- **Conexiones**: reparto por estado frente a `max_connections`.
- **Copias**: manifest de `db-backups/`, edad, checksum (`.sha256`) y revisión de la copia.
- **Integridad**: fila única de `sync_settings` y `alembic_version`, velas huérfanas o
  duplicadas, asientos sin cuenta y filas de proveedores sin medición.

Un dato no medido se publica `unknown` con su motivo; nunca como cero. El diagnóstico es
**read-only**: no ejecuta VACUUM/ANALYZE, no aplica migraciones y no restaura copias.

La única acción de escritura de la ventana es **«Crear copia ahora»**
(`POST /api/database/backup`): exige escribir `COPIAR`, admite una sola copia a la vez
(advisory lock `774104254`), pide rol `admin` si `APP_PASSWORD` está activo y registra cada
intento en `logs/agent/db-maintenance.jsonl`. No escribe en PostgreSQL —`pg_dump` solo
lee— pero sí crea el fichero, su `.sha256` y poda por `DB_BACKUP_KEEP`.

## Tablas de inversión (ADR 008)

### `investment_accounts`

Contenedor de cuenta de inversión.

| Campo | Tipo | Notas |
|-------|------|-------|
| id | cuid | |
| user_id | string? | Multi-tenant futuro |
| name | string | |
| type | enum | **`simulated` = Demo (único operativo hoy)** · `paper` = broker real futuro · `live` = reservado |
| status | enum | `active`, `suspended`, `closed` |
| currency | string | Ej. `EUR` |
| base_currency | string | |
| initial_deposit | decimal | Depósito al crear cuenta |
| leverage | decimal | |
| settings_json | json | Comisiones + fiscal |
| is_default | bool | Espejo de última cuenta Activa (UI) |
| active_profile_id | FK? | → `investor_profiles` |

**Premisa producto (2026-07-31):** una sola cuenta **Activa**; operación solo DEMO. Tipo Paper ≠ paper-trading: será enlace a operador bursátil. Ver [account-premises-demo-vs-paper-2026-07-31.md](./engineering/account-premises-demo-vs-paper-2026-07-31.md).

**Ciclo de vida demo:** `status=closed` = soft (sigue en BD). `DELETE` solo si `type=simulated` y cerrada → hard delete de cuenta + carteras/posiciones/ledger/órdenes. Perfiles del catálogo se conservan. Mantenimiento en lote: **Configuración → BD** (`/api/database/closed-accounts`).

### `investment_portfolios`

Cartera lógica dentro de una cuenta.

| Campo | Tipo | Notas |
|-------|------|-------|
| id | cuid | Usado en API scope |
| account_id | FK | |
| legacy_portfolio_id | FK | → `portfolios.id` (efectivo/posiciones) |
| name | string | |
| strategy_tag | string? | Ej. `core` |
| sort_order | int | |
| is_default | bool | Cartera principal de la cuenta |

### `portfolios` (legacy operativo)

| Campo | Tipo | Notas |
|-------|------|-------|
| id | cuid | |
| name | string | |
| currency | string | |
| cash | decimal | **Efectivo operativo** |

### `positions`

| Campo | Tipo | Notas |
|-------|------|-------|
| portfolio_id | FK | → legacy `portfolios` |
| instrument_id | FK | |
| quantity | decimal | |
| avg_cost | decimal | |

### `transactions`

Historial de compras/ventas por cartera legacy.

| Campo | Tipo | Notas |
|-------|------|-------|
| portfolio_id | FK | |
| type | enum | `buy`, `sell` |
| quantity, price, total | decimal | |

### `ledger_entries`

Libro mayor append-only.

| Campo | Tipo | Notas |
|-------|------|-------|
| account_id | FK | |
| portfolio_id | FK? | Cartera lógica (`investment_portfolios`) |
| type | string | `deposit`, `withdrawal`, `buy`, `sell`, `fee`, … |
| amount | decimal | Signo: + entra, − sale |
| balance_after | decimal | Saldo efectivo **de esa cartera** tras el movimiento |
| reference_type | string? | `transfer`, `external`, `transaction`, `custody`, `migration`, `manual` |
| reference_id | string? | ID correlacionado (transfer id, transaction id, …) |
| description | string? | |

Ver [PORTFOLIO_AND_CASH.md](./PORTFOLIO_AND_CASH.md) para reglas de movimientos.

### `pending_orders`

| Campo | Tipo | Notas |
|-------|------|-------|
| account_id | FK? | Scope cuenta (sin portfolio_id aún) |

## Convenciones

- IDs: `cuid()` vía Prisma.
- Fechas diarias OHLCV: tipo `Date` @db.Date.
- Schema Prisma: `packages/database/prisma/schema.prisma`.
- Migración runtime legacy → cuentas: `SqlAlchemyAccountRepository.ensure_migrated()`.

## Futuro

- Baseline Alembic con tablas `investment_*` y `ledger_entries`
- Posiciones con `account_id` + `portfolio_id` lógicos
- Ledger-first reconciliation
