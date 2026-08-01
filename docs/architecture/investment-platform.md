# Plataforma de inversión — arquitectura y plan de implementación

> **Estado:** diseño aprobado (ADR 008). **Siguiente paso:** Fase 0.  
> **Snapshot legacy:** [_snapshots/pre-phase0-2026-07-05.md](./_snapshots/pre-phase0-2026-07-05.md)

## 1. Visión

Bolsa V1 pasa de “simulador con una cartera fija” a **plataforma de gestión patrimonial** donde:

- Toda actividad cuelga de una **cuenta de inversión** (simulada hoy, real mañana).
- Las **carteras** organizan posiciones dentro de la cuenta.
- El **ledger** registra cada movimiento de forma inmutable.
- **Overview** es el centro de mando; **Configuración** unifica preferencias.
- Los **reportes** consumen ledger + snapshots de equity (futuro).

Inspiración: patrón **account-centric** de IBKR/XTB (balance, margen, equity, blotter, account history).

---

## 2. Modelo de dominio

### 2.1 InvestmentAccount

```typescript
interface InvestmentAccount {
  id: string;
  userId: string | null;           // null hasta auth multi-user

  name: string;                    // "Demo EUR", "Paper IBEX"
  type: 'simulated' | 'paper' | 'live';
  status: 'active' | 'suspended' | 'closed';

  currency: string;                // ISO 4217, ej. EUR
  baseCurrency: string;            // moneda de reporting

  // Balances (cache; fuente: ledger + posiciones)
  cash: number;
  equity: number;
  investedValue: number;
  unrealizedPnl: number;
  realizedPnl: number;

  // Margen (simulado Fase 3+)
  marginUsed: number;
  freeMargin: number;
  marginLevelPct: number | null;   // equity / marginUsed * 100
  leverage: number;                // default 1 (sin apalancamiento)
  marginCallLevelPct: number;    // ej. 100

  initialDeposit: number;
  brokerConnectionId: string | null;

  isDefault: boolean;              // cuenta activa por defecto en instalación
  createdAt: string;
  updatedAt: string;
  lastActivityAt: string | null;
}
```

### 2.2 InvestmentPortfolio

```typescript
interface InvestmentPortfolio {
  id: string;
  accountId: string;

  name: string;
  description?: string;
  strategyTag?: string;            // "core", "swing", "dividend"
  color?: string;
  sortOrder: number;
  isDefault: boolean;

  // Derivados (API summary)
  equity?: number;
  positionsCount?: number;
  cashAllocationPct?: number;
}
```

**Regla Fase 0:** cada cuenta nueva recibe **1 cartera default** (`isDefault: true`). Posiciones referencian `portfolioId`.

### 2.3 Position (evolución)

```typescript
interface Position {
  id: string;
  accountId: string;               // NUEVO — denormalizado para queries
  portfolioId: string;             // NUEVO
  instrumentId: string;
  quantity: number;
  avgCost: number;
  // P&L de mercado: calculado en read model
}
```

Unique: `(portfolioId, instrumentId)`.

### 2.4 Order (unifica pending + futuro)

```typescript
type OrderSide = 'buy' | 'sell';
type OrderType = 'market' | 'limit' | 'stop_limit';
type OrderStatus = 'pending' | 'partial' | 'filled' | 'cancelled' | 'expired';

interface Order {
  id: string;
  accountId: string;
  portfolioId: string;
  instrumentId: string;
  symbol: string;

  side: OrderSide;
  orderType: OrderType;
  quantity: number;
  limitPrice?: number;
  stopPrice?: number;

  status: OrderStatus;
  filledQuantity: number;
  avgFillPrice?: number;

  expiryAt?: string;
  createdAt: string;
  updatedAt: string;
  filledAt?: string;
}
```

Migración: `pending_orders` → `orders` con `status: pending`.

### 2.5 LedgerEntry (fuente de verdad)

```typescript
type LedgerEntryType =
  | 'deposit'
  | 'withdrawal'
  | 'buy'
  | 'sell'
  | 'fee'
  | 'dividend'
  | 'adjustment';

interface LedgerEntry {
  id: string;
  accountId: string;
  portfolioId: string | null;

  type: LedgerEntryType;
  amount: number;                  // signo: + entra caja, - sale (convención a fijar en Fase 0)
  currency: string;
  balanceAfter: number;            // caja tras movimiento

  instrumentId?: string;
  quantity?: number;
  price?: number;

  referenceType?: 'order' | 'manual' | 'migration' | 'fee';
  referenceId?: string;

  description?: string;
  executedAt: string;              // timestamp efectivo
  createdAt: string;               // timestamp registro
}
```

**Invariantes:**

- Append-only (sin UPDATE/DELETE salvo admin `adjustment`).
- Todo `buy`/`sell` tiene `referenceId` → order o legacy transaction id.
- `ExecuteTrade` escribe ledger + actualiza position + order en **una transacción SQL**.

### 2.6 PlatformSettings

```typescript
interface PlatformSettings {
  id: string;                      // 'default' o per-user
  userId: string | null;

  general: {
    locale: string;
    theme: 'system' | 'light' | 'dark';
    defaultAccountId?: string;
  };
  notifications: {
    orderFilled: boolean;
    priceAlerts: boolean;
    marginWarning: boolean;
    marginWarningThresholdPct: number;
  };
  sounds: {
    enabled: boolean;
    orderFilled: boolean;
    alertTriggered: boolean;
    error: boolean;
  };
  confirmations: {
    confirmOrders: boolean;
    confirmClosePosition: boolean;
    confirmDeleteDrawing: boolean;
  };
  shortcuts: Record<string, string>;  // action → key chord

  updatedAt: string;
}
```

Persistencia Fase 1: JSON en BD (`platform_settings` table) + overrides locales (sonidos) en localStorage.

---

## 3. Diagrama de capas

```mermaid
flowchart TB
  subgraph client [Web Client]
    OV[Overview v2]
    CFG[Config Modal]
    OPS[Mis operaciones]
    HIST[Historial]
    TR[Trading existente]
    ACC_STORE[activeAccountStore]
  end

  subgraph api [FastAPI v1]
    ACC_R[/accounts]
    PF_R[/portfolios]
    LED_R[/ledger]
    ORD_R[/orders]
    POS_R[/positions]
    REP_R[/reports - Fase 4]
    SET_R[/settings]
  end

  subgraph app [Application Layer]
    AccountSvc
    LedgerSvc
    OrderSvc
    TradeSvc
    ReportSvc
  end

  subgraph infra [PostgreSQL]
    investment_accounts
    investment_portfolios
    ledger_entries
    positions
    orders
    platform_settings
  end

  OV --> ACC_R
  TR --> ORD_R
  OPS --> ORD_R
  HIST --> LED_R
  ACC_STORE --> ACC_R

  ACC_R --> AccountSvc
  LED_R --> LedgerSvc
  ORD_R --> OrderSvc
  TradeSvc --> LedgerSvc
  TradeSvc --> OrderSvc

  AccountSvc --> investment_accounts
  LedgerSvc --> ledger_entries
```

---

## 4. API propuesta (v1 extendida)

### Cuentas

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/accounts` | Listar cuentas (filtro `userId` futuro) |
| POST | `/api/accounts` | Crear cuenta simulada |
| GET | `/api/accounts/{id}` | Detalle |
| PATCH | `/api/accounts/{id}` | Renombrar, suspender |
| GET | `/api/accounts/{id}/summary` | Equity, margen, posiciones agregadas |
| POST | `/api/accounts/{id}/deposits` | Depósito manual (Fase 3) |

### Carteras

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/accounts/{id}/portfolios` | Listar carteras |
| POST | `/api/accounts/{id}/portfolios` | Crear |
| PATCH | `/api/portfolios/{id}` | Editar |

### Ledger / Historial

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/accounts/{id}/ledger` | Paginado, filtros tipo/fecha/símbolo |
| GET | `/api/accounts/{id}/ledger/export` | CSV (Fase 2+) |

### Órdenes / Operaciones

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/accounts/{id}/orders` | `?status=pending` blotter |
| POST | `/api/accounts/{id}/orders` | Crear orden |
| DELETE | `/api/accounts/{id}/orders/{oid}` | Cancelar |
| POST | `/api/accounts/{id}/trade` | Market instant (compat) |

### Legacy (deprecación)

| Ruta actual | Reemplazo | Plazo |
|-------------|-----------|-------|
| `GET /api/portfolio` | `GET /api/accounts/{default}/summary` | 1 release |
| `GET /api/portfolio/transactions` | `GET /api/accounts/{id}/ledger?type=buy,sell` | 1 release |
| `POST /api/portfolio/trade` | `POST /api/accounts/{id}/trade` | 1 release |
| `GET/POST /api/pending-orders` | `/api/accounts/{id}/orders` | 1 release |

Header propuesto: `X-Account-Id: {uuid}` (opcional; default = cuenta `isDefault`).

---

## 5. Frontend

### 5.1 Store: cuenta activa

```typescript
// apps/web/src/stores/active-account-store.ts (nuevo)
interface ActiveAccountState {
  activeAccountId: string | null;
  setActiveAccountId: (id: string) => void;
}
```

Persistir en `localStorage` + sincronizar con `PlatformSettings.general.defaultAccountId`.

Todos los hooks (`usePortfolio`, `usePendingOrders`, `executeTrade`) pasan `accountId`.

### 5.2 Rutas nuevas (Fase 1–2)

| Ruta | Componente | Fase |
|------|------------|------|
| `/overview` | Overview v2 | 1 |
| `/accounts` | AccountsPage | 0–1 |
| `/accounts/:id` | AccountDetailPage | 2 |
| `/operations` | OperationsPage | 2 |
| `/history` | HistoryPage | 2 |
| `/settings` | Redirect → Config modal | 1 |

### 5.3 Modal Configuración

- Componente: `PlatformConfigDialog` (6 tabs).
- Apertura: Overview card, top bar “Configuración”, `/settings` redirect.
- Tabs vacías excepto General + Otras (migrar sync desde SettingsPage).

### 5.4 Overview v2 (wireframe)

```
┌─ Cuenta activa [Demo EUR ▼] ─────────────────────────────────┐
│ Patrimonio 102.450 € │ Caja 45.200 € │ P&L día +1,2%          │
│ Margen libre 38.100 € │ Nivel 340%                          │
└──────────────────────────────────────────────────────────────┘
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ Carteras    │ │ Mis         │ │ Historial   │ │ Config      │
│ inversión   │ │ operaciones │ │             │ │             │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

---

## 6. Esquema BD (objetivo Fase 0)

### Tablas nuevas

```sql
-- investment_accounts
-- investment_portfolios (account_id FK)
-- ledger_entries (account_id FK, portfolio_id nullable)
-- platform_settings (JSON document)
-- orders (reemplazo pending_orders; account_id, portfolio_id)
```

### Tablas modificadas

```sql
-- positions: + account_id, portfolio_id (migrar desde portfolio_id legacy)
-- portfolios (legacy): renombrar o mapear → investment_portfolios
```

**Estrategia migración:**

1. Crear `investment_accounts`; insert 1 fila por cada `portfolios` legacy o 1 cuenta default global.
2. Crear `investment_portfolios`; 1:1 con portfolio legacy.
3. Copiar `transactions` → `ledger_entries`.
4. Añadir FKs a `positions`, migrar `pending_orders` → `orders`.
5. Mantener vista SQL `transactions_legacy` si hace falta rollback.

Ver script planificado en Fase 0: `packages/database/prisma/migrations/` (TBD).

---

## 7. Fases detalladas

### Fase 0 — Fundamentos (prioridad inmediata)

**Objetivo:** multi-cuenta en BD + API + selector UI; trading scoped.

| Tarea | Archivos afectados |
|-------|-------------------|
| Prisma + SQLAlchemy models | `schema.prisma`, `tables.py` |
| Tipos shared | `packages/shared/src/accounts.ts` (nuevo) |
| Repositorios | `account_repository.py`, refactor `portfolio_repository.py` |
| Use cases | `bolsa_application/accounts.py`, `ledger.py` |
| API routes | `routes/accounts.py` |
| Migración datos | seed + script one-shot |
| Frontend store | `active-account-store.ts` |
| API client | `api.ts` |
| Status bar / trading | pasar `accountId` |
| Tests py | `test_accounts.py`, `test_ledger_migration.py` |

**Criterios de aceptación:**

- [ ] Crear 2 cuentas simuladas; cambiar cuenta activa.
- [ ] Trade en cuenta A no afecta cuenta B.
- [ ] Ledger contiene movimientos migrados + nuevos trades.
- [ ] `/api/portfolio` sigue funcionando (shim → default account).
- [ ] Snapshot legacy intacto en docs.

### Fase 1 — Overview + Config shell

- Overview v2 cards + resumen cuenta.
- `PlatformConfigDialog` 6 tabs (General + Otras con contenido migrado).
- `/settings` → abre modal o redirect.

### Fase 2 — Carteras + Operaciones + Historial

- UI multi-cartera.
- `/operations` blotter.
- `/history` ledger paginado + filtros.

### Fase 3 — Margen y depósitos

- Depósitos/retiros UI.
- Motor margen simulado + alertas.

### Fase 4 — Reportes

- Equity curve, drawdown, export.
- Puente backtest vs cuenta real.

### Fase 5 — Cuentas reales

- Broker connection, reconciliación, paper/live.

---

## 8. Reportes (diseño anticipado)

| Reporte | Fuente datos | Fase |
|---------|--------------|------|
| Equity curve | Snapshots diarios `account_equity_snapshots` (tabla Fase 4) | 4 |
| Performance TWR/MWR | Ledger + snapshots | 4 |
| Activity blotter | `orders` + ledger | 2 |
| Fiscal plusvalías | Ledger `sell` + cost basis FIFO | 5+ |
| Backtest vs live | `backtest_runs` vs ledger mismo periodo | 4 |

Job nocturno (Fase 4): materializar snapshot equity por cuenta para gráficos rápidos.

---

## 9. Convenciones

- Código/identificadores en **inglés**; UI/docs en **español**.
- Decimal en BD (18,6); number en JSON API.
- Zona horaria: UTC en BD; display Europe/Madrid en UI.
- IDs: cuid (consistente con Prisma actual).

---

## 10. Checklist antes de Fase 0 (dev)

```bash
# Verificar baseline
pnpm db:ensure
pnpm --filter @bolsa/web typecheck
pnpm test:py

# Leer snapshot legacy
cat docs/architecture/_snapshots/pre-phase0-2026-07-05.md
```

---

## 11. Referencias cruzadas

- [ADR 008](../adr/008-investment-accounts-and-ledger.md)
- [Snapshot legacy](./_snapshots/pre-phase0-2026-07-05.md)
- [JSON snapshot máquina](./_snapshots/pre-phase0-schema.json)
