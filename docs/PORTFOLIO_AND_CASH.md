# Cuentas de inversión y efectivo

Modelo estilo XTB: la unidad visible para el usuario es la **cuenta de inversión**. Internamente existe una cartera legacy implícita (puente técnico).

## Jerarquía

```
InvestmentAccount (cuenta simulada — unidad UI)
  └── InvestmentPortfolio default (cartera interna, no expuesta en UI)
        └── legacy Portfolio (efectivo operativo + posiciones + trades)
              ├── positions
              └── transactions
LedgerEntry[] (auditoría append-only, por cuenta)
```

## Scope HTTP

| Header | Efecto |
|--------|--------|
| `X-Account-Id` | Cuenta activa (default si omitido). Trades, resumen `/api/portfolio`, transacciones y ledger usan la cartera default de esa cuenta. |

El frontend envía el header desde Zustand (`active-account-store`).

## Tipos de movimiento de efectivo

| Kind | API | Conserva total cuenta | Ledger |
|------|-----|----------------------|--------|
| **Depósito externo** | `POST /api/accounts/{id}/deposits` | No (inyecta capital) | `deposit`, `referenceType: external` |
| **Retirada externa** | `POST /api/accounts/{id}/withdrawals` | No (extrae capital) | `withdrawal`, `referenceType: external` |
| **Depósito inicial cuenta** | `POST /api/accounts` | No (creación) | `deposit`, `referenceType: manual` |
| **Operación** | `POST /api/portfolio/trade` | — | `buy`/`sell` + `fee` |
| **Custodia anual** | automático en summary/tax | — | `fee`, `referenceType: custody` |

## Reglas de negocio

1. **Una cuenta = una cartera operativa.** No hay subcarteras ni transferencias internas en la UI/API.
2. **Efectivo operativo:** vive en `portfolios.cash` (legacy). El ledger registra cada movimiento con `balanceAfter`.
3. **Depósito/retirada externa:** simulan capital entrante/saliente del “mundo exterior” (cuenta simulada).
4. **Cerrar cuenta:** `status: closed`. Conserva ledger, historial y fiscal.
5. **Eliminar cuenta (solo demo):** solo `type=simulated` y `status=closed`. Borra posiciones, transacciones, ledger, carteras y órdenes pendientes.
6. **Posiciones y trades:** scoped a la cartera legacy de la cuenta.

## API resumida

| Método | Ruta |
|--------|------|
| GET | `/api/accounts` |
| POST | `/api/accounts` |
| GET | `/api/accounts/{id}` |
| PATCH | `/api/accounts/{id}` |
| POST | `/api/accounts/{id}/close` |
| DELETE | `/api/accounts/{id}` |
| POST | `/api/accounts/{id}/deposits` |
| POST | `/api/accounts/{id}/withdrawals` |
| GET | `/api/accounts/{id}/ledger?limit=&offset=` |
| GET | `/api/accounts/{id}/summary` |

## Tipos TypeScript

Ver `packages/shared/src/portfolio-cash.ts` y `packages/shared/src/accounts.ts`.

## UI

| Pantalla | Funcionalidad |
|----------|---------------|
| `/accounts` | Hub master-detail: lista de cuentas + detalle (resumen, posiciones, movimientos, configuración) |
| `/history` | Ledger y operaciones de la cuenta activa |
| Barra trading | Selector de cuenta (scope global) |

## Pendiente (fuera de alcance actual)

- Transferencias entre cuentas distintas
- Ledger como única fuente de verdad (reconciliación cash vs ledger)
- Posiciones referenciando `investment_portfolios.id` directamente
