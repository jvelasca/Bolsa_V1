# Evidencia `v2.88.86-beta` — `MANUAL · H1 UX`: **la CTA de salida conduce de verdad a Vender directo**

**Producto:** `V2.88.86-beta` · **Package:** `2.11.86-beta` · **AsOf:** 2026-10-07. **Sin migración nueva** (head `052_top3_opportunities`). **`Δ motor = 0`** y **contrato HTTP sin cambio**: la venta de una posición `HUMAN_MANUAL` ya estaba autorizada en `v2.88.85-beta` (`row_is_human_manual`); este sello solo cierra la **UX** que aún no la ofrecía. **Tag anotado `v2.88.86-beta`**.

**Padre de producto:** [`v2.88.85`](../v2.88.85/README.md). Auditoría que motivó el slice:
[`auditoria-manual-modo-demo-2026-10-07.md`](../../auditoria-manual-modo-demo-2026-10-07.md) (§H1, §10 opción 1 y §11 addendum).

## Qué cambia

Cierra el tramo **UX** del hallazgo H1 (P1) que `v2.88.85-beta` dejó abierto: el backend ya
autoriza la venta HTTP de una posición nacida por el canal manual, pero la superficie de posición
solo mostraba el copy «usa Vender» sin ofrecer el flujo real.

1. **La CTA de salida abre Vender directo.** En
   [`position-exit-drawer-actions.tsx`](../../../../apps/web/src/features/trading/position-exit-drawer-actions.tsx),
   con el libro en **MANUAL** y una posición `HUMAN_MANUAL`, **Reducir/Salir** llaman a
   [`open-sell-position-order.ts`](../../../../apps/web/src/features/trading/open-sell-position-order.ts),
   que resuelve el instrumento con el caché canónico (`["instrument", id]`) y abre el
   `OrderDialog` (lado venta + cantidad de desriesgo). La **firma humana** sigue en el diálogo
   (`Confirm`), igual que el resto de la vía manual: **no ejecuta sola**.
2. **Detección de origen manual en cliente.** `positionIsHumanManual` /
   `HUMAN_MANUAL_TRADE_PLAN_PREFIX` en
   [`propose-position-exit.ts`](../../../../apps/web/src/features/operations/propose-position-exit.ts),
   espejo de la tercera evidencia de `row_is_human_manual` (el `PositionDto` solo expone el prefijo
   `manual-{tx}`; el wire no trae `birth_override_reason` ni `trade_plan_snapshot.origin`).
3. **Preset del diálogo.** [`trading-ui-store.ts`](../../../../apps/web/src/stores/trading-ui-store.ts)
   gana `orderPreset` (lado + cantidad) y `openOrderDialog(instrument, preset?)`; `OrderDialog` lo
   aplica al abrir (volumen precargado + `TradeConfirmPanel` pre-armado).

## Invariantes de honestidad (no negociables)

- **SEMI/AUTO intactos:** en MANUAL una posición **no** `HUMAN_MANUAL` conserva el bloqueo actual
  (el fence backend sigue vetando su venta HTTP); SEMI sigue encolando Confirm.
- **No hay bypass:** la autorización de cierre manual se sigue leyendo de la **fila real** de la
  posición en backend (`row_is_human_manual`); el cliente solo enruta a la superficie correcta.
- **La venta no se dispara sola:** la CTA abre el diálogo con la firma humana pre-armada, no ejecuta.

## Verificación

- **Frontend (vitest):**
  - `apps/web/src/features/trading/position-exit-drawer-actions.test.tsx` — MANUAL + `HUMAN_MANUAL`
    pulsa Reducir y **abre Vender** (no encola); MANUAL + no manual mantiene el bloqueo; SEMI
    sigue encolando Confirm.
  - `apps/web/src/features/operations/propose-position-exit.test.ts` — `positionIsHumanManual`
    (prefijo `manual-`, `tradePlanId` normal, ausente).
- **Local:** `typecheck`, `lint`, `prettier --check` y la suite web completa verdes; el guardián
  `test_dia_d_bump_guard` verde (los 9 CLIs `v2_89`…`v2_97` sellan `2.11.86-beta` junto al
  `package.json`).
- **Contrato:** sin regeneración (`contract:check` no cambia).

## Qué no cambia

Motor AUTO de decisión/ejecución (`Δ motor = 0`), ledger, posiciones, settlement, el fence de venta
HTTP y el contrato HTTP. El TOP3 y su contrato web (T1) quedan como en `v2.88.85-beta`.

## Cita POST-TAG

**Tag anotado `v2.88.86-beta`** (objeto `bb6438e3` → commit `067cbaad`). `Release tag CI` [`37666847381`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37666847381) **VERDE** (`11` jobs `success` + `playwright` integrado `skipped`; `certify` `success`; `python` `4594 passed / 45 skipped`; `frontend` `1528 passed` (`258` ficheros); `replay-repro` **`REPRODUCIDO`** `1E3ADAC2…` ⇒ `Δ motor = 0` confirmado por CI).
