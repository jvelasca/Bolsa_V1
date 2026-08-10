# ADR 008: Cuentas de inversión, ledger y plataforma de gestión patrimonial

## Estado

**Aceptado** — jul 2026  
**Implementado (jul 2026):** Fase 0–2 con modelo XTB (cuenta = unidad UI; cartera interna única). Hub `/accounts`, ledger, fiscal, comisiones, custodia. Ver [PORTFOLIO_AND_CASH.md](../PORTFOLIO_AND_CASH.md) *(histórico: `PROJECT_STATE.md` eliminado; pendiente de borrar definitivamente cuando se confirme libre de uso).*

## Contexto

Bolsa V1 opera hoy con una **única cartera simulada implícita** (`Cartera principal`, 100 000 € en seed). Posiciones, transacciones y órdenes pendientes no están scoped a una **cuenta de inversión**. No hay ledger auditable, reportes patrimoniales ni separación entre “lista Cartera” (watchlist) y “cartera de inversión” (agrupación contable).

Se requiere evolucionar hacia una plataforma al nivel de XTB, IBKR o Trading212: multi-cuenta (simulada → real), margen, depósitos, historial completo y base para fiscal, backtesting comparativo y trading automático.

## Decisiones de producto (confirmadas)

| # | Pregunta | Decisión |
|---|----------|----------|
| 1 | ¿Multi-cuenta desde el inicio? | **Sí** — modelo multi-cuenta desde Fase 0 |
| 2 | ¿Sub-carteras? | **Modelo multi-cartera en BD desde Fase 0**; UI simple (1 cartera default) hasta Fase 2 |
| 3 | ¿Configuración? | **Modal 6 pestañas** desde Overview/top bar; `/settings` redirige o se depreca |
| 4 | ¿Transactions vs ledger? | **Ledger append-only como fuente de verdad**; `transactions` migra o pasa a ser vista derivada |
| 5 | ¿Multi-usuario? | **`userId` nullable** en cuentas hasta auth completo; diseño preparado |

## Decisiones técnicas

### 1. Jerarquía de dominio

```
InvestmentAccount (cuenta)
  └── InvestmentPortfolio (cartera lógica, N por cuenta)
        └── Position (instrumento + qty + coste)
        └── Order (pendiente / histórico)
        └── LedgerEntry (movimiento contable, append-only)
```

- **Cuenta** = contenedor patrimonial (caja, margen, equity, estado, depósitos).
- **Cartera** = agrupación de gestión (core, swing, dividendos…); opcional en UI inicial.
- **Ledger** = libro mayor; toda mutación de caja pasa por una entrada.

### 2. Tipos de cuenta (fase simulada)

```typescript
type InvestmentAccountType = 'simulated' | 'paper' | 'live';
type InvestmentAccountStatus = 'active' | 'suspended' | 'closed';
```

Fase 0–4: solo `simulated`. Fase 5+: `paper` / `live` con `brokerConnectionId`.

### 3. Ledger como fuente de verdad

Tipos de entrada iniciales:

`deposit` | `withdrawal` | `buy` | `sell` | `fee` | `dividend` | `adjustment`

Cada trade genera al menos una entrada `buy`/`sell` con `referenceType: 'order'` y `referenceId`. La caja (`cash`) de la cuenta se **recalcula** desde ledger o se mantiene `balanceAfter` denormalizado por rendimiento.

**Migración:** filas existentes en `transactions` → `ledger_entries` con `legacyTransactionId`. Tabla `transactions` deprecada en API v2 o eliminada tras migración.

### 4. Scope obligatorio en API

Todo endpoint de trading recibe o infiere `accountId` (header `X-Account-Id` o query; cuenta activa en sesión cliente).

Endpoints actuales `/api/portfolio/*` evolucionan a:

- `GET /api/accounts`
- `GET /api/accounts/{id}/summary`
- `GET /api/accounts/{id}/ledger`
- `POST /api/accounts/{id}/orders`
- etc.

Compatibilidad: `/api/portfolio` redirige a cuenta default durante transición (máx. 1 release).

### 5. Configuración — modal de pestañas

| Pestaña | Persistencia |
|---------|--------------|
| General | `PlatformSettings` (servidor) + cuenta activa |
| Perfil inversor / Cuenta (fees) | Servidor (cuenta + catálogo) |
| Notificaciones | Servidor / local |
| Sonidos | Local (+ sync opcional) |
| Confirmaciones | Local |
| Atajos de teclado | Workspace / servidor |
| **BD** | Solo lectura + acciones de mantenimiento (resumen PostgreSQL, huérfanos, purga) |
| Otras | Sync, proveedores |

ADR 006 (`/settings` página) queda **supersedido en UX** por este modal; sync automática en **Otras**; estado/purga de datos en **BD**.

### 6. Overview v2

Tarjetas: **Carteras de inversión**, **Mis operaciones**, **Historial**, **Configuración** + resumen de cuenta activa (patrimonio, margen, P&L).

### 7. Separación watchlist vs cartera de inversión

| Concepto | ID / ubicación | Propósito |
|----------|----------------|-----------|
| Lista virtual `__builtin:portfolio__` | `default-lists.ts` | Atajo UI en Trading |
| `InvestmentPortfolio` | BD | Agrupación contable real |

La lista virtual **lee** posiciones de la cuenta/cartera activa; no es fuente de verdad.

### 8. Auth y multi-usuario

- `InvestmentAccount.userId: string | null` — null = instalación single-user actual.
- Sin breaking change en auth JWT existente.
- Índice `(userId, status)` para listar cuentas por usuario en el futuro.

## Consecuencias

### Positivas

- Base sólida para reportes, fiscal y auto-trading.
- Multi-cuenta demo (estrategias paralelas, comparación).
- Auditoría completa vía ledger.
- Alineación con brokers profesionales.

### Negativas / coste

- Migración BD y refactor de `portfolio_repository`, `ExecuteTrade`, frontend stores.
- Riesgo de drift Prisma/SQLAlchemy — migración documentada en Fase 0.
- Curva de aprendizaje: cuenta vs cartera vs lista virtual.

### Riesgos mitigados

- Snapshot pre-Fase 0 en `docs/architecture/_snapshots/` (estado legacy).
- API legacy `/api/portfolio` mantenida temporalmente.
- Seed crea 1 cuenta + 1 cartera default equivalente a hoy.

## Fases (resumen)

Ver detalle en [../architecture/investment-platform.md](../architecture/investment-platform.md).

| Fase | Entregable |
|------|------------|
| **0** | Tablas, tipos shared, API accounts, scope trading, selector cuenta activa |
| **1** | Overview v2 + modal Config (shell) |
| **2** | Multi-cartera UI + Operaciones + Historial |
| **3** | Margen simulado + depósitos |
| **4** | Reportes v1 |
| **5** | Cuentas reales / broker |

## Referencias

- [Arquitectura detallada](../architecture/investment-platform.md)
- [Snapshot pre-Fase 0](../architecture/_snapshots/pre-phase0-2026-07-05.md)
- [ADR 006 — Settings legacy](./006-chart-platform-and-settings.md)
- [DATA_MODEL.md](../DATA_MODEL.md) — actualizar tras Fase 0

## Historial

| Fecha | Evento |
|-------|--------|
| 2026-07-05 | ADR creado; decisiones 1–5 confirmadas; snapshot legacy |
