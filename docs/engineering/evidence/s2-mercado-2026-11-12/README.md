# Evidencia S2 — Estructura de mercado y niveles calculados · 2026-11-12

> Alcance: metodología, dominio puro, vocabulario, capa de gráfico, readout en Instrumento y
> OPERATIVA. Sin commit, sin bump, sin migración, sin `contract:gen`.
>
> Estado: **implementado y verificado**. Pendiente de aprobación de producto. `PROJECT_STATE.md`
> **no** se toca hasta que S2 esté aprobado (regla del plan).

## 1 · Invariantes

| Invariante | Comprobación | Resultado |
| --- | --- | --- |
| `Δ motor = 0` | `git diff --stat -- packages/py/application/src/bolsa_application/daily_opinion_stance.py` | Sin cambios (archivo ausente del diff) |
| Sin migración | Última revisión en `packages/py/**/versions` | `067_opinion_account_scope` (sin cambios) |
| Sin `contract:gen` | `git diff -- market`… en `openapi.json` / `schema.d.ts` | Sin referencias a `market-structure`, `soporte` ni `resistencia` |
| S0 intacto | `git status` | Nada añadido al índice; no hay commit ni `git add` |
| Cálculo puro | `packages/shared/src/market-structure.ts` | Sin React, sin IO, sin `Date.now`, sin locale, sin redondeos |

**Nota de honestidad sobre el contrato:** `apps/web/api/openapi.json` y `apps/web/src/api/schema.d.ts`
ya estaban modificados **antes** de S2 por el trabajo de F4-067 / dictamen por cuenta. S2 no los
toca: su delta habla de `opinion telemetry`, `ensureDays` y `hints` deprecados, nunca de estructura
de mercado. No se revierte trabajo previo ajeno a este slice.

## 2 · Pruebas ejecutadas

```text
pnpm --filter @bolsa/shared test -- market-structure
  ✓ src/market-structure.test.ts (34 tests)

pnpm --filter @bolsa/web test -- chart-market-structure
  ✓ src/features/charts/chart-market-structure-levels-layer.test.tsx (5 tests)

pnpm --filter @bolsa/web test -- market-structure
  ✓ src/features/charts/market-structure-chart-levels.test.ts (10 tests)
  ✓ src/features/charts/chart-market-structure-levels-layer.test.tsx (5 tests)
  ✓ src/features/market-structure/market-structure-readout.test.tsx (10 tests)

pnpm --filter @bolsa/web test -- market-structure-readout
  ✓ src/features/market-structure/market-structure-readout.test.tsx (10 tests)

pnpm --filter @bolsa/shared test -- market
  ✓ src/market-vocabulary.test.ts (40 tests)   [incluye guardas S2]
  ✓ src/market-structure.test.ts (34 tests)
```

Cobertura declarada y falsable:

- pivotes con empates, bordes y ventana mínima;
- agrupación dentro/fuera de `0,75 × ATR` y medición contra el centro;
- 1 toque ⇒ no fiable; 2 recientes ⇒ detectado; 2 antiguos ⇒ no fiable; 3 antiguos ⇒ detectado;
- `en_precio`, `roto` en soporte y en resistencia; precedencia fiabilidad → posición;
- 79 vs 80 velas, sin ATR, sin pivotes, barra inválida;
- absorción por un nivel más fuerte;
- estructura ascendente / descendente / en rango / contradictoria;
- firma estable, no mutación de la entrada, normalización temporal;
- gráfico: solo `detectado` produce línea; estilo distinto del preset manual;
- readout: hueco declarado, motivos traducidos, fuerza del estudio separada, procedencia.

## 3 · Tipos y lint

```text
pnpm --filter @bolsa/shared typecheck   → OK
pnpm --filter @bolsa/web typecheck      → OK (tsc -b --noEmit)
pnpm --filter @bolsa/shared lint        → OK
pnpm --filter @bolsa/web lint           → 0 errores (23 warnings preexistentes)
pnpm --filter @bolsa/web test -- ohlcv-chart      → 5/5 (la capa nueva no rompe el gráfico)
pnpm --filter @bolsa/web test -- trading-layout   → 15/15 (OPERATIVA sigue montando)
```

## 4 · Archivos de S2

**Nuevos**

- `docs/engineering/metodologia-soportes-resistencias-tendencia-2026-11-12.md`
- `packages/shared/src/market-structure.ts`
- `packages/shared/src/market-structure.test.ts`
- `apps/web/src/features/charts/market-structure-chart-levels.ts`
- `apps/web/src/features/charts/market-structure-chart-levels.test.ts`
- `apps/web/src/features/charts/chart-market-structure-levels-layer.tsx`
- `apps/web/src/features/charts/chart-market-structure-levels-layer.test.tsx`
- `apps/web/src/features/charts/market-structure-prefs.ts`
- `apps/web/src/features/charts/use-market-structure-prefs.ts`
- `apps/web/src/features/market-structure/market-structure-readout.tsx`
- `apps/web/src/features/market-structure/market-structure-readout.test.tsx`
- `docs/engineering/evidence/s2-mercado-2026-11-12/README.md`

**Modificados (solo lo imprescindible)**

- `packages/shared/src/index.ts` — exporta el dominio nuevo.
- `packages/shared/src/market-vocabulary.ts` — etiquetas de estado, motivo y estructura.
- `packages/shared/src/market-vocabulary.test.ts` — guardas de vocabulario S2.
- `apps/web/src/features/charts/ohlcv-chart.tsx` — prop `showMarketStructureLevels` y montaje de la capa.
- `apps/web/src/features/charts/chart-workspace-page.tsx` — activa la capa en Mercado.
- `apps/web/src/features/instruments/instrument-detail-page.tsx` — tarjeta «Estructura y niveles calculados».
- `apps/web/src/features/trading/trading-operativa-panel.tsx` — readout junto a `OperativaAnalisisDiario`.

## 5 · Decisiones que se apartan de la letra del plan (y por qué)

1. **Clasificación por tipo de pivote**, no por posición respecto al cierre: un soporte roto se
   sigue llamando «soporte roto» en vez de renombrarse a resistencia. El nombre describe qué
   estructura era; el estado describe qué le pasó.
2. **La fiabilidad va antes que la posición**: un pivote aislado no puede estar «roto» ni «en
   precio» porque nunca fue estructura. Se declara `no_fiable` con su motivo.
3. **Lectura de fuerza**: el productor del estudio publica `strength` (0–10) y `strengthBand`, no
   ADX numérico. El readout muestra esa fuerza y cae a ADX/DI si algún día llegan, o a «Sin dato de
   fuerza». Nunca inventa un ADX.

## 6 · Pendiente, fuera de este slice

- Aprobación de producto de S2.
- Actualizar `PROJECT_STATE.md` **solo tras** esa aprobación.
- S0 y la integración de F4-067 siguen pendientes y sin tocar.
- Asesor, listas y Estudio: fuera de alcance de S2 v1.
