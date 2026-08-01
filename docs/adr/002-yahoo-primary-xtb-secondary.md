# ADR 002: Yahoo primario, XTB secundario

## Estado

Aceptado — vigente (implementación en Python `bolsa_market` + bridge HTTP).  
Doc operativo: [MARKET_DATA.md](../MARKET_DATA.md) · Ayuda sync **2026-07-23**.

## Contexto

XTB cerró su API pública retail. El usuario es suscriptor XTB pero el núcleo del proyecto debe ser estable y ampliable.

## Decisión

1. **Yahoo Finance** como proveedor principal para histórico OHLCV, perfil y fundamentales.
2. **XTB** como adaptador opcional vía **bridge HTTP local** (cotización live + validación vs cierre BD).
3. Toda lectura de gráficos/backtests/escáneres desde **PostgreSQL**, no desde proveedores en tiempo de ejecución del chart.

## Consecuencias

- Desarrollo desacoplado de cambios en xStation5.
- Riesgo aceptado: Yahoo no es API oficial; mitigado con BD local, throttle, sanity y logs.
- XTB no escribe histórico OHLCV ni sustituye Yahoo para backtesting.
