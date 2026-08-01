# Auditoría de datos por instrumento

Documento vivo — primera pasada (2026-07-10). Objetivo: entender qué guardamos, qué derivamos y cómo evitar duplicar o pisar datos consolidados.

## Capas de datos

### 1. Datos crudos (persistidos)

| Tabla / campo | Contenido | Fuente actual | Rango temporal |
|---------------|-----------|---------------|----------------|
| `instruments` | Catálogo (símbolo, Yahoo, ISIN, sector…) | Import / seed | — |
| `instruments.profile_snapshot` | Perfil Yahoo (JSON) | Sync Yahoo | Snapshot; `fetchedAt` en JSON |
| `ohlcv_bars` | Velas OHLCV | Yahoo (sync + caché intradía) | Diario: incremental con solapamiento 7 días; intradía: TTL bajo demanda |
| `data_sync_log` | Auditoría de sync | Yahoo | Append-only |

**Clave única OHLCV:** `(instrument_id, timeframe, timestamp)` — una sola fila por vela; el campo `source` (`yahoo` \| `xtb`) existe pero hoy solo se escribe `yahoo`.

### 2. Datos derivados (no persistidos)

- Indicadores técnicos (SMA, EMA, RSI)
- Price summary (último, % día, min/max período)
- Frescura / sanity / desviación XTB (`GET /data-status`)
- Gráficos y estudios (config en workspace JSON)

### 3. Datos de la app (por instrumento)

- `positions`, `transactions`, `ledger_entries`
- `backtest_runs`, `price_alerts`, `pending_orders`
- Membresía en `instrument_list_items`

No duplican OHLCV; referencian `instrument_id`.

## Flujos de actualización

### Yahoo (`POST /api/instruments/{id}/sync`)

1. Si hay velas diarias → descarga desde `última vela − 7 días` hasta hoy.
2. Si no hay velas → histórico `years_back` (default 5).
3. Upsert en `ohlcv_bars` (sobrescribe en conflicto).
4. Metadatos: ISIN/sector si vacíos; `profile_snapshot` se reemplaza entero.

### XTB (estado actual)

- Bridge HTTP local (`XTB_BRIDGE_URL`).
- Cotización en vivo: **no se persiste**.
- `POST /api/instruments/{id}/validate-xtb`: contrasta `last` XTB vs último cierre BD **sin escribir**.

## Riesgos conocidos (a mejorar poco a poco)

1. **Upsert ciego** — el solapamiento de 7 días puede sobrescribir velas ya consolidadas.
2. **Sin prioridad por fuente** — no hay regla “no degradar calidad”.
3. **Sanity solo en lectura** — `run_sanity_checks` no bloquea escrituras.
4. **XTB no alimenta OHLCV** — solo validación visual por ahora.
5. **`profile_snapshot` siempre se reemplaza** — sin merge ni versionado.

## Principios para siguientes iteraciones

1. **Validar antes de escribir** — contrastar Yahoo/XTB/BD; registrar desviación. *(XTB validate implementado)*
2. **No duplicar** — una vela = una fila; metadatos en JSON separado.
3. **No pisar consolidado** — política de merge Δ≤2% para velas existentes. *(Implementado en sync Yahoo)*
4. **Sanity en sync** — errores bloquean escritura; warnings solo informan. *(Implementado)*
5. **Auditoría visible** — pestaña “Nuestra BD” + `data_sync_log` + `last_xtb_validation`.

## UI

- Diálogo (i) → pestaña **Nuestra BD**: inventario + botones *Actualizar Yahoo* / *Validar con XTB*.
- API: `GET /api/instruments/{id}/db-inventory`, `POST /api/instruments/{id}/validate-xtb`.

## Referencias

- `docs/MARKET_DATA.md`
- `docs/adr/002-yahoo-primary-xtb-secondary.md`
- `packages/py/application/src/bolsa_application/sync_instrument.py`
- `packages/py/application/src/bolsa_application/get_instrument_db_inventory.py`
