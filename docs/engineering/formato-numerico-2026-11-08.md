# Formato numérico localizado — Fase 3.3 — 2026-11-08

Cierre de `p3-format` (Fase 3 / 3.3 del plan de remediación). Los importes y porcentajes
visibles para el usuario se pintan con `es-ES`; las entradas de texto se parsean con la
misma convención. Los cálculos y los ejes de charts conservan su precisión fija.

## Qué se cambió

- `apps/web/src/lib/format.ts` gana tres helpers, todos `es-ES` y con la regla del
  backend de que «no medido» no es un cero:
  - `formatMoney(value, currency = "EUR")` → `"1.234,50 €"`. Normaliza el NBSP
    (U+00A0) que inserta `Intl` a un espacio normal, para que el texto sea copiable y
    los tests no dependan de un carácter invisible. `null`/`NaN`/`Infinity` → `"—"`.
  - `formatPct(value, fractionDigits = 2)` → `"12,34 %"`. Recibe **puntos**, no
    fracciones: no usa `style: "percent"` porque los campos `*_pct` del dominio ya
    vienen multiplicados por 100.
  - `formatBps(value, fractionDigits = 2)` → `"22 bps"`.
- `formatPrice` (`features/charts/chart-utils.ts`), que ya era la función de las
  superficies de precio, pasa de `toFixed(2)` a `formatNumberWith` con 2 decimales y
  locale `es-ES`. Mantiene el símbolo por divisa (`€`, `$`, `£`, código ISO) y el guion
  largo para ausencia.
- Componentes de usuario migrados de `toFixed(2)` a los helpers: tablas y tarjetas de
  cuenta, dashboard, historial, mesa, operaciones, fiscal, AUTO (cifras, hoja de
  operación, ticket virtual), decision board y paneles de settings. **No** es un
  reemplazo ciego: ejes de charts, marcas internas y cálculos que necesitan precisión
  fija siguen con `toFixed`.
- Entradas de usuario migradas de `Number()`/`parseFloat` a `parseLocalizedNumber`
  (`@/lib/format`) en: alta de cuenta (depósito inicial), alertas, backtests
  (cash inicial y optimización), trading/F3 (precio y cantidad), panel F3 supervisado.
  Los datos que ya llegan numéricos de la API siguen con `Number()`.

## Ratchet

`apps/web/src/lib/format-ratchet.test.ts` cuenta `.toFixed(2)` en `src/features`
(ficheros no-test) y falla si supera la línea base fijada en **131**. No prohíbe la
llamada —hay usos legítimos en charts y cálculos—, impide que el número crezca. Si se
baja el conteo, se ajusta `BASELINE` en el mismo PR para no perder el suelo.

## Nota sobre `es-ES`

`Intl` para `es-ES` no agrupa millares en números de cuatro cifras: `3200` →
`"3200,00"`, mientras que `12500` → `"12.500,00"`. No es un bug del helper; si una
superficie necesita agrupar siempre, se pasa una opción explícita de `Intl`, no se
duplica el formateo.

## Verificación

```bash
cd apps/web
pnpm run typecheck
pnpm exec vitest run
pnpm run contract:check
```

- `typecheck`: OK.
- Tests: 371 ficheros / 2.771 tests en verde (incluye el ratchet y los tests de
  componentes que fijaban los formatos anteriores, actualizados a `es-ES`).
- `contract:check`: OK — el cambio es solo de presentación; no toca el contrato HTTP.

## Efecto declarado

Los textos visibles cambian de `10000.00 €` a `10.000,00 €` y de `100.00` a `100,00`.
Cualquier test, snapshot o manual que fijara el formato inglés debe actualizarse; el
valor numérico subyacente no cambia.
