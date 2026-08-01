# Diseño profesional: Listas / Universos (pre–v1.0)

> **Estado:** estudio + plan · **no implementar aún** sin validación de fases.  
> **Contexto:** pausa de producto [`product-pause-audit-2026-07-30.md`](./product-pause-audit-2026-07-30.md).  
> **Objetivo:** cimientos de listas al nivel de apps TOP **antes** de FA, paper y GitHub formal.

---

## 1. Veredicto

Hoy las listas son **snapshots personales en BD** (+ un «IBEX 35» de catálogo mal definido).  
Las apps TOP separan:

1. **Watchlists personales** (tú decides los tickers).  
2. **Universos de mercado / índices vivos** (la composición la marca el índice; la app **se sincroniza**).  
3. **Listas virtuales / dinámicas** (cartera, órdenes, scanners) — derivadas.

Sin (2) vivo, cualquier embudo Lista AUTO sobre «IBEX» es **incoherente con la realidad** y no es producto serio.

**Decisión de producto propuesta:** reforzar listas ahora; **v1.0 = embudo AT estable + operativa de listas profesional**; luego GitHub/FA.

---

## 2. Qué tenemos hoy (auditoría técnica)

### 2.1 Modelo BD

```prisma
model InstrumentList {
  id, name, source @default("custom")  // "catalog" | "custom" | (UI: "virtual")
  items InstrumentListItem[]
}
```

- Sin `kind`, sin `provider`, sin `externalCode`, sin `lastSyncedAt`, sin historial de altas/bajas.
- Membresía = filas fijas. **No hay sync de constitutivos.**

### 2.2 Catálogo «IBEX 35» — corregido en L0/L1

`ensure_ibex_catalog_list` + `SubscribeMarketIndex`:

- Membresía = constitutivos **curados** (35), no todos los BME.
- Re-sync si diverge; suscribir importa faltantes.
- ID estable `ibex35` · `source=catalog` (etiqueta UI: **índice**).

### 2.3 Listas personales vs ops

| Tipo | Origen | Problema |
|------|--------|----------|
| `custom` | Usuario / API | Snapshot; no se actualiza solo |
| `catalog` | `ensure_ibex…` | Pseudo-índice estático |
| `virtual` | UI (cartera, pendientes, viz) | OK (derivadas; no en BD) |
| Ops «IBEX sin TOP» | Sesión auditoría | Confunde; no es producto |

### 2.4 Búsqueda

| Entidad | Hoy |
|---------|-----|
| **Valores** (hub Valores) | BD + Yahoo · import → a menudo Visualización, no auto-add a lista activa |
| **Listas** (hub / Backtests / Screener) | `<select>` / carrusel de BD · **sin búsqueda de índices** |
| Backtest universo «Valor» | Solo BD («No consulta Yahoo») |

### 2.5 Yahoo, sync OHLCV y constitutivos

- Yahoo **no** ofrece API oficial de constitutivos de índices.
- `^IBEX` / `^GSPC` sirven para **cotizar el índice**, no para listar componentes.
- Con `sync_settings.scope=lists`, el auto-OHLCV solo encola **miembros de alguna lista** → un universo linked bien sincronizado es también el **universo de datos**.
- Fuentes constitutivos v1: semilla versionada (+ Wikipedia/dataset); no venderlo como “listas de Yahoo”.

### 2.6 Inventario confirmado (código)

| Pieza | Ruta |
|-------|------|
| Schema | `packages/database/prisma/schema.prisma` |
| Seed 35 tickers | `packages/shared/src/constants.ts` · `prisma/seed.ts` |
| ID estable IBEX | `packages/shared/src/default-lists.ts` → `ibex35` |
| Repo + ensure | `packages/py/.../list_repository.py` |
| API | `apps/api-python/.../routes/lists.py` |
| UI hub | `apps/web/.../lists-tab/*` |
| Universo backtest | `backtest-universe-picker.tsx` |
| Docs sync | `docs/DATA_MODEL.md` · ADR-002 Yahoo |

**No existe** lista SP500 en BD (solo strings de política cognitiva). **No existe** pipeline de constitutivos.

---

## 3. Qué hacen las apps TOP (patrón a copiar)

| App / patrón | Personal | Índice / universo | Dinámica |
|--------------|----------|-------------------|----------|
| Fidelity / brokers | Watchlists manuales, límite N | Índices como instrumento cotizable; constitutivos aparte o research | — |
| IBKR | Watchlists + scanners | Universos de mercado / custom index | Scanners avanzados |
| Thinkorswim | Estáticas | Universo de scan (p. ej. S&P 500) | **Dynamic watchlists** = reglas |
| TradingView / research | Símbolos + listas | Índices y screener por exchange | Screener guardado |

**Lección única:**  
**No mezclar** «mi lista Favoritos» con «el IBEX 35».  
El índice es un **universo enlazado** que se **refresca**; la personal es **editable** y nunca se pisa sola.

---

## 4. Modelo objetivo (v1 Listas)

### 4.1 Tres capas

```text
┌─────────────────────────────────────────────────────────┐
│  MarketUniverse (catálogo de índices / universos)         │
│  code=IBEX35 · provider · syncPolicy · lastSyncedAt       │
│  membership[] = constitutivos “verdad de mercado”         │
└───────────────────────────┬─────────────────────────────┘
                            │ link / materialize
┌───────────────────────────▼─────────────────────────────┐
│  InstrumentList (lo que ve el usuario en carrusel/BD)     │
│  kind = personal | linked_universe | virtual | snapshot   │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│  Instrument (BD) ← import Yahoo si falta símbolo          │
└─────────────────────────────────────────────────────────┘
```

### 4.2 `kind` (contrato de producto)

| kind | Quién edita miembros | Sync | Borrar |
|------|----------------------|------|--------|
| **personal** | Usuario | Nunca automático | Sí |
| **linked_universe** | Solo el job de sync | Sí (diff constitutivos) | Desuscribir (no “eliminar el IBEX del mundo”) |
| **snapshot** | Usuario tras “Congelar copia” | No | Sí (ya es personal) |
| **virtual** | Sistema | Derivado | No |

### 4.3 Campos nuevos (propuesta)

**MarketUniverse**

- `code` (único): `IBEX35`, `SPX`, `NDX`, `STOXX50E`, …
- `displayName`, `region`, `currency`
- `yahooIndexSymbol` (opcional, cotización del índice): `^IBEX`
- `constituentProvider`: `curated_v1` | `wikipedia` | `bme` | …
- `syncInterval`, `lastSyncedAt`, `constituentHash`, `status`

**MarketUniverseMember**

- `universeCode`, `yahooSymbol`, `name?`, `weight?`, `instrumentId?`, `asOf`

**InstrumentList** (extender)

- `kind`, `universeCode?` (si linked), `ownerScope` (local/single-user hoy)
- `source` legacy → migrar a `kind` (compat)

### 4.4 Búsqueda de listas (paridad con valores)

```text
Cuadro «Buscar lista / índice»
  → hits locales: personales + linked ya suscritas
  → hits catálogo MarketUniverse (IBEX 35, S&P 500, …) aunque no estén en BD aún
  → Acción: [Suscribir / Añadir al carrusel]
       → materializa InstrumentList kind=linked_universe
       → sync constitutivos → import instrumentos faltantes → membresía
```

Misma UX mental que Valores: **buscar → elegir → materializar en BD**.

### 4.5 Sync de constitutivos (operativa seria)

```text
Job (diario o al abrir linked stale):
  1. Fetch constitutivos (provider)
  2. Normalizar a yahooSymbol
  3. Diff vs membership anterior
  4. ImportInstrument para altas no en BD
  5. Upsert membership linked list
  6. Registrar changelog: joined[] / left[]
  7. Política producto ante bajas:
       - quitar de lista linked
       - NO borrar Finalistas ni velas automáticamente
       - badge “salió del índice el YYYY-MM-DD” en Monitor (fase 2)
```

**Coherencia:** la lista linked **siempre** refleja el último sync exitoso; el usuario ve `Últ. sync` + Δ altas/bajas.

### 4.6 Política IBEX en v1 (prioridad)

1. Semilla **curada** de 35 símbolos Yahoo (`.MC`) versionada en repo.  
2. Sync periódico (Wikipedia IBEX / dataset curado) con validación `count ∈ [33,37]` (alarma si absurdo).  
3. Sustituir `ensure_ibex_catalog_list` “todos los BME”.  
4. Migración: lista `ibex35` existente → `kind=linked_universe` + re-sync.

---

## 5. UX objetivo (hub Listas)

| Vista | Comportamiento |
|-------|----------------|
| Carrusel | Personales + linked + virtuales; badge `Índice` / `Personal` / `Live` |
| Hub Listas | Buscador de listas/índices (nuevo) + crear personal |
| Linked | Miembros **solo lectura** + «Actualizar ahora» + «Congelar copia personal» |
| Personal | CRUD actual |
| Ops | Prohibido crear listas tipo «IBEX sin TOP» como producto; gaps = filtro/auditoría |

Copy claro:

- *«IBEX 35 (índice · sincronizado)»*  
- *«Mis favoritos (personal)»*  
- *«Copia IBEX 30-jul (snapshot)»*

---

## 6. Impacto en embudo / Lista AUTO / Finalistas

| Tema | Efecto |
|------|--------|
| Lista AUTO | Universo = membership **post-sync**; frescura v1.2 intacta |
| Valor sale del IBEX | Deja de entrar en campañas del linked; Finalistas del ticker **permanecen** hasta Eliminar |
| Valor entra | Aparece en cola; sin TOP → analizar (no Omitido) |
| Cap 40 | IBEX 35 OK; S&P 500 → paginar / sublistas / “solo sin TOP” como **filtro**, no lista ops |

---

## 7. Pipeline óptimo (tu idea, estructurada bien)

**Sí: la idea es correcta.** Dos familias de listas:

| Familia | Nombre de producto | Origen |
|---------|-------------------|--------|
| **Propias** | Listas personales | Tú creas / editas |
| **Públicas / genéricas** | **Índices** (IBEX 35, DAX, S&P 100, S&P 500, …) | Descubrimiento mercado → constitutivos → materializar en BD |

### 7.1 Lo que el usuario hace (flujo TOP)

```text
Buscar lista/índice: "SP500" | "IBEX" | "DAX" | "SP100"
        │
        ▼
Yahoo SEARCH → hits quoteType=INDEX  (^GSPC, ^IBEX, ^GDAXI, ^OEX, …)
        │
        ▼
Elegir índice → «Suscribir / Añadir»
        │
        ▼
Resolver CONSTITUTIVOS (capa aparte; ver 7.2)
        │
        ▼
Iterar cada símbolo → importar en BD si falta (throttled, como sync de valores)
        │
        ▼
InstrumentList kind=linked_universe  (miembros = constitutivos vivos)
```

Eso es exactamente: **búsqueda inicial del índice + iteración de componentes**.

### 7.2 Tres capas (no mezclar — estructura óptima)

```text
┌──────────────────────────────────────────────────────────────┐
│  A · Index Discovery                                           │
│  Entrada: texto usuario                                        │
│  Salida: IndexHit { yahooSymbol:^GSPC, name, quoteType:INDEX } │
│  Motor: Yahoo /v1/finance/search (ya tenemos search_quotes)    │
│  + ranking/alias locales ("SP500"→^GSPC, "IBEX"→^IBEX)         │
└────────────────────────────┬─────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────┐
│  B · Constituent Resolution  ← CUELLO DE BOTELLA / DISEÑO CLAVE │
│  Entrada: yahooIndexSymbol (^GSPC) o code canónico (SPX)       │
│  Salida: ConstituentSet { symbols[], provider, asOf, hash }    │
│  Interface: ConstituentProvider.resolve(index) → set           │
│  Implementaciones (plugin, en orden de confianza):             │
│    1. curated_registry  — semilla versionada (IBEX, popular)   │
│    2. yahoo_components  — página/API componentes si estable    │
│    3. wikipedia / dataset externo alineado a símbolos Yahoo     │
│  REGLA: si resolve falla → NO vaciar lista existente           │
└────────────────────────────┬─────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────┐
│  C · Materialization                                           │
│  Suscribir → InstrumentList linked + membership                │
│  Por cada símbolo: ensure Instrument (import Yahoo) + OHLCV    │
│  Diff sync: joined[] / left[]; changelog; badge Últ. sync      │
│  Personal lists: capa aparte, nunca pisadas por B/C            │
└──────────────────────────────────────────────────────────────┘
```

### 7.3 Matiz crítico (honestidad técnica)

| Capacidad | ¿Yahoo lo hace hoy? |
|-----------|---------------------|
| **Buscar** índices por nombre (`SP500` → `^GSPC`, `quoteType: INDEX`) | **Sí** — mismo search que valores; filtrar `INDEX` |
| **Cotizar** el índice | **Sí** — chart de `^GSPC` |
| **Devolver los 500 constitutivos** en el search | **No** de forma fiable/oficial |

Por eso la estructura óptima **no** es “todo es Yahoo search”, sino:

- **Yahoo = descubrimiento + símbolos + velas**  
- **ConstituentProvider = plugin** (Yahoo components cuando se pueda + registry curado + fallback)

Si metemos constitutivos dentro de `InstrumentList` sin capa B, o asumimos que search trae los 500, la arquitectura se rompe al primer índice grande o cuando Yahoo cambie el HTML.

### 7.4 Alias de producto (UX)

El buscador debe entender lenguaje humano, no solo `^GSPC`:

| Query usuario | Hit preferido |
|---------------|---------------|
| IBEX, IBEX35, IBEX 35 | `^IBEX` · IBEX 35 |
| SP500, S&P 500, SPX | `^GSPC` |
| SP100, OEX | `^OEX` |
| DAX | `^GDAXI` |
| NASDAQ 100, NDX | `^NDX` |

Tabla de alias en shared (versionada) + hits Yahoo INDEX.

### 7.5 Universos grandes (S&P 500)

- **Suscribir + hidratar** los ~500: sí (job con throttle; progreso en UI).  
- **Lista AUTO completa** de 500: no por defecto (cap / filtro “sin Finalistas” / muestreo).  
- Sync de membresía ≠ lanzar embudo AT sobre todo el índice.

---

## 8. Plan de desarrollo (fases → v1.0)

### Fase L0 — Contrato + spike — **HECHO 2026-07-30**
- Tres capas documentadas (§7).
- `bolsa_market.indices`: aliases, registry, discovery, `ConstituentProvider` curado IBEX35.
- API: `GET /api/market-indices/search`, `GET /api/market-indices/{key}/constituents`.
- Shared TS + client web + tests L0.

### Fase L1 — Suscribir + hidratar + UX — **HECHO 2026-07-30**
- `POST /api/market-indices/subscribe` → import faltantes + lista `catalog`.
- Hub: buscador + Suscribir/Sync · Desuscribir índice.
- GET `/lists` **no** recrea IBEX si lo borraste; sí **sincroniza** índices suscritos (join/leave + import).

### Membresía índice (join / leave) — política fija

1. **Suscribir** o **abrir Listas** (GET `/api/lists`) sincroniza índices `catalog` con provider listo.  
2. Por cada constitutivos: si no está en BD → **import**; si está → reutilizar.  
3. Membresía de la lista = **exactamente** el set actual (replace).  
4. **Leave:** ticker sale del índice → se quita de `instrument_list_items`; el `Instrument` **sigue en BD** (velas/Finalistas intactos).  
5. **Join:** entra al índice → import si falta + vínculo a la lista.  
6. Desuscribir borra la lista, no los instrumentos.

### Fase L2 — Schema linked-universe + job+poll — **HECHO 2026-07-30**
- `InstrumentList`: `kind`, `universeCode`, `lastSyncedAt`, `contentHash`, `membershipChangelog`.
- `index_subscribe_jobs` + worker inline (poll Postgres).
- `POST /market-indices/subscribe/jobs` (202) + `GET .../jobs/{id}`; sync POST se mantiene para índices pequeños.
- UI: catálogo chips + job+poll si ≥40 constitutivos.
- `GET /market-indices/catalog` — lista de listas (índices estándar).

### Fase L3 — UX buscador de listas/índices — **HECHO 2026-07-30**
- Cuadro en hub Listas (espejo Valores) — chips catálogo + búsqueda.
- Suscribir → progreso vía job poll.
- Congelar copia personal · badge Últ. sync · familias **Sistema / Índices / Personales**.

### Fase L4 — Índices internacionales populares — **HECHO 2026-07-30**
- Misma tubería A→B→C; providers: `curated` · `remote_us` · `remote_intl`.
- DAX / NDX / DJI / FTSE100 / FTSEMIB / HSI (CSV yfiua) · STOXX50E (wiki/mirror).
- Soft-cap Lista AUTO: máx. 40 + **confirmación explícita** si N>40 (S&P 500 no lanza 500 embudos).
- Prefill `?listId=` desde atajo hub → Backtesting.
- Filtro opcional «Solo sin Finalistas» antes del cap.
- Columna VALOR: quotes de lista (no IDs truncados tras suscribir índices).

### Catálogo mundial (lista de listas) — decisión 2026-07-30

**Sí conviene** un catálogo fijo de índices bursátiles estándar (como apps profesionales),
además del buscador Yahoo:

| Capa | Qué es | Ejemplo |
|------|--------|---------|
| **Catálogo** | Lista curada de índices conocidos (`KNOWN_INDICES`) | IBEX, DAX, STOXX50E, FTSE100, FTSEMIB, SPX, OEX, NDX, DJI, HSI |
| **Suscripción** | El usuario elige cuáles materializar en su BD | Chip Suscribir / Sync |
| **Provider** | Plugin de constitutivos genérico | curated / remote_us / remote_intl (yfiua CSV + wiki STOXX) |

No hay “flujo DAX” vs “flujo IBEX”: hay **un** pipeline A→B→C; solo cambia el plugin B.
Índices intl (DAX, NDX, DJI, FTSE100, FTSEMIB, HSI) usan CSV Yahoo-aligned (yfiua);
STOXX50E usa Wikipedia/mirror. Pendientes sin fuente estable: CAC40, AEX, SMI, N225.

**L3–L4 hecho:** badge sync · congelar copia · familias hub · soft-cap AUTO con confirmación ·
resumen estado backtesting por miembro en Universo Lista · clic → pestaña Valor.

### Cierre v1.0 listas (2026-07-30) — HECHO

Operativa cerrada para producto. Documentación canónica:

| Artefacto | Rol |
|-----------|-----|
| Este doc | Diseño A→B→C + fases L0–L4 + aceptación |
| `list-auto-ops-2026-07-29.md` | Lista AUTO / frescura / keep-alive |
| Ayuda → Watchlist | `watchlist-lists-tracker.ts` |
| Ayuda → Backtesting | `backtesting-tracker.ts` (universo lista + resumen) |
| `fundamental-analysis-readiness-2026-07-30.md` | Siguiente tramo: FA |

### Luego (fuera de listas)
- Análisis Fundamental (FA) — planificar operativa completa.  
- GitHub formal · scanners dinámicos.

---

## 9. Criterios de aceptación v1.0 (Listas)

- [x] Dos familias claras en UI: **Personales** vs **Índices** (más Sistema).  
- [x] Buscar «IBEX» / «SP500» / «DAX» encuentra hits INDEX (Yahoo + alias).  
- [x] Suscribir hidrata constitutivos (iteración + import) sin mezclar con personales.  
- [x] «IBEX 35» = constitutivos reales (± tolerancia), no “todos BME”.  
- [x] Sync no vacía lista si el provider falla.  
- [x] Personal no se pisa. Congelar copia disponible.  
- [x] S&P 500 suscribible; AUTO no obliga a 500 embudos (cap 40 + confirm).  
- [x] Tests discovery + resolve + materialize.

---

## 10. Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| Confundir search INDEX con constitutivos | Capas A/B/C separadas; tests de contrato |
| Yahoo components scrape frágil | Provider curado primero; scrape opcional; fallback |
| Rate limit al hidratar S&P 500 | Cola + `YAHOO_MIN_INTERVAL`; UI progreso; reanudar |
| Schema prematuro | Spike L0 antes de migración grande |
| Lista AUTO sobre 500 | Cap/filtros; producto explícito |

---

## 11. Decisiones de producto — CONFIRMADAS (2026-07-30)

| # | Decisión | Estado |
|---|----------|--------|
| 1 | Modelo `personal` / `linked_universe` (índice) / `snapshot` / `virtual` | **Sí** |
| 2 | IBEX v1 con semilla/curado + sync (no esperar BME de pago) | **Sí** |
| 3 | Índices internacionales populares (S&P 500, DAX, SP100…) vía **buscador** + hidratar constitutivos | **Sí** (visión completa; IBEX primero en código, misma tubería) |
| 4 | Congelar copia personal desde índice | **Sí** |

**Clarificación usuario:** S&P 500 = índice EE.UU. análogo al IBEX español; el buscador debe descubrir índices mundiales (Yahoo INDEX) y luego completar la lista iterando componentes — no una lista personal más.

**Próximo paso de ingeniería:** spike L0 (search INDEX + `ConstituentProvider` + IBEX curado) **antes** de congelar el schema definitivo.

---

## 12. Referencias código actual

- `packages/database/prisma/schema.prisma` — `InstrumentList`  
- `packages/shared/src/constants.ts` — `IBEX35_INSTRUMENTS` (semilla real)  
- `packages/py/.../list_repository.py` — `ensure_ibex_catalog_list` (a sustituir)  
- `packages/py/market/.../yahoo_client.py` — `search_quotes` (capa A)  
- `packages/py/.../search_instruments.py` — patrón UI a espejar  
- `apps/web/.../list-values-panel.tsx` — búsqueda de valores  
- `apps/web/src/lib/default-lists.ts` — virtuales + `ibex35`  
