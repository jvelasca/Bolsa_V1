# SEMI DEMO libro — implementación slice 1

> **AsOf:** 2026-08-03 · **Padre:** [demo-operating-modes-brief-2026-08-03.md](./demo-operating-modes-brief-2026-08-03.md)  
> **GO:** usuario 2026-08-03 · rama `stage/semi-demo-book-slice1-2026-08-03`  
> **Freeze intacto:** Belief auto · Camino D AUTO · CORE_R_CRON · Studio/F5

## Decisiones (no olvidar)

| # | Decisión |
|---|----------|
| Modo | MANUAL = aviso · SEMI = Confirm F3 · AUTO greyed |
| Canal | Un solo Confirm (Camino C); fuentes Finalistas + Radar |
| H≠M | Humano elige en Confirm |
| N | Solo `maxOpenPositions` (configurable) |
| Sizing | ~10 % cash DEMO por op (editable) |
| Diversif. | Óptimo primero; preferencia país→EU→mundo (suave) |
| Aprender | 5a audit+tenure ahora · 5c pesos cuando descongele Belief |
| Cola F3 | sessionStorage OK v1 · **BD** por `accountId` (slice 1.2) |
| Confirm | Lote + checks por valor |
| Capital | Cash DEMO (sin risk budget paralelo) |

## Entregables slice 1

1. **Prefs libro** (`demo-book-prefs`): mode · maxOpenPositions · defaultSizePctOfCash · countryPreferOrder  
2. **UI modo** en rail Trading / barra: MANUAL | SEMI | AUTO(disabled) + N + % sizing  
3. **Alarmas Radar:** SEMI → Proponer F3 con qty≈10 % cash; MANUAL → toast sin execute  
4. **F3 Confirm:** selección múltiple · qty desde cash% · callout H vs M si hay ambos hints · gate si mode≠SEMI  
5. **Copy** Camino C = «SEMI · Confirm DEMO»  
6. Docs: este brief + index + HELP + handoff corto

## Fuera de slice 1–1.2

AUTO execute · country hard veto · auto WeightRules · dual UI completa H/M slots · Belief

## Verificación automatizada

```bash
pnpm test:semi          # battery web + py + smoke API opcional
pnpm test:semi:smoke    # solo API live (SEMI_API_REQUIRED=1 para forzar)
```

Scripts: `scripts/research/verify_semi_demo_battery.mjs` · `verify_semi_demo_api_smoke.py`  
Migración: `python packages/py/infrastructure/scripts/apply_supervised_f3_account_state_migration.py`

## Slice 1.1 (geo)

- [x] `demo-book-geo-rank` + tests  
- [x] Orden cola F3: óptimo → geo  
- [x] Control preferencia en Libro DEMO  

## Slice 1.2 (cola BD + country)

- [x] Tabla + GET/PUT supervised-f3-queue  
- [x] Hydrate/push cliente  
- [x] `Recommendation.country` en propose  
- [x] Aplicar migración local  
- [x] Battery `pnpm test:semi` + smoke API  

- [x] H≠M emparejado en Confirm (Finalistas + Radar mismo valor)  
- [x] `strategyOrSignalRef` → tenure Mandato  

## Checklist prueba DEMO

- [x] Unit: prefs · geo · Finalistas path · queue store · operativa contract  
- [x] Battery `pnpm test:semi` (registrada)  
- [ ] Cuenta DEMO activa con cash ≥ 2k  
- [ ] Modo SEMI · N=10 · size 10 %  
- [ ] Finalistas → Proponer → aparece en cola F3  
- [ ] Alarma Radar → F3 (SEMI) / solo toast (MANUAL)  
- [x] Confirm+ejecutar → posición + tenure Mandato  
- [x] Coach rail: tenures abiertos + Learning (5b)  
- [ ] AUTO no clickable / no ejecuta (UI)  
- [x] Qty propuesta ≈ 10 % cash / precio (unit)  
- [x] Geo: orden cola con badge país (unit)  
- [x] Cola F3 BD roundtrip (`test:semi:smoke`)  

## Retomar

1. Leer brief de modos + este impl brief.  
2. `git checkout` rama slice o `main` tras merge.  
3. Continuar checklist pendiente / slice 1.1 cola BD si hace falta.
