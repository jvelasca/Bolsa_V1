# ARRANQUE — LIVE VIRTUAL design (2026-09-07)

> **Leer primero (este archivo):** [cierre sesión noche](./traspaso-relevo-cierre-sesion-pista-a-2026-09-06.md) · [audit pack LIVE venue](./audit-pack-live-venue-thaw-design-2026-09-06.md) · [diseño UI pasarela](./design-live-virtual-order-gateway-ui-2026-09-07.md) · [runbook gates](./runbook-live-venue-thaw-gates-2026-09-06.md) · tip [`v2.10.1-beta`](./traspaso-relevo-tag-v2-10-1-beta-2026-09-05.md).  
> **Tip vigente:** `v2.10.1-beta` → `a060af37` / package `1.39.1-beta`.  
> **Para quién:** owner o agente · **PRODUCT FREEZE** · **NO MÁS PANELES** · DESIGN_ONLY · no tip/bump · no motor · no flips capital.

## Premisas owner (inmutables hasta nueva palabra)

1. **LIVE VIRTUAL** hasta que la APP esté **100% probada** (puede tardar **meses**). No capital real / no thaw prod mientras tanto.
2. Destino conceptual del LIVE real: **pasarela VISUAL de órdenes** hacia el broker — **concepto UI (híbrido)** = [design doc](./design-live-virtual-order-gateway-ui-2026-09-07.md); **UI producto no implementada**; **no** inventar arquitectura de settlement.
3. Estudio ≠ autorización de capital · ≠ Accept LIVE · ≠ flip `brokerVenue=live` · ≠ `PAPER_D_EXECUTE=1`.
4. Auditoría GitHub limpia de producto = tip `v2.10.1-beta` (ortogonal a este estudio de docs).

## Decisión de sesión (2026-09-07)

**Foco:** diseño UI LIVE VIRTUAL (híbrido telegrama + por qué) bajo freeze — [design doc](./design-live-virtual-order-gateway-ui-2026-09-07.md) · [relevo cierre](./traspaso-relevo-design-live-virtual-ui-2026-09-07.md).  
**Fondo (no bloquea):** pista A = acumulación P1–P5 Camino D ([path pack](./audit-pack-thaw-estricto-path-post-v2101-2026-09-06.md) · [W+5](./traspaso-relevo-thaw-estricto-remeasure-2026-09-07.md) · **0/5** · gates planos vs W+4 · **NO** Accept).

## Prompt (pegar al chat)

> Lee `docs/engineering/arranque-agente-pista-a-estricto-2026-09-07.md`, `docs/engineering/traspaso-relevo-cierre-sesion-pista-a-2026-09-06.md` y `docs/engineering/audit-pack-live-venue-thaw-design-2026-09-06.md`. PRODUCT FREEZE. NO MÁS PANELES. Foco = LIVE VIRTUAL (DESIGN_ONLY). Premisas: VIRTUAL hasta APP 100% probada; destino = pasarela visual de órdenes (por definir). No inventes PASS. No flips live/execute. No inventes arquitectura de pasarela.

## Freeze (copiar)

NO LIVE capital · LIVE solo **VIRTUAL** hasta APP 100% · `PAPER_D_EXECUTE` default off · Confirm = firma · Ranking ≠ BUY · Arm ≠ Execute · **NO MÁS PANELES** · **PRODUCT FREEZE** · package `1.39.1-beta` · DESIGN_ONLY · no afirmar PASS sin evidencia local o `conclusion=success`.

## Checklist sesión (orden)

1. Identidad tip: `v2.10.1-beta` → `a060af37` · `1.39.1-beta` (no re-certificar cabina).
2. Releer premisas VIRTUAL + pasarela visual (arriba) · anclar en pack §0.1.
3. Estudiar [audit pack LIVE](./audit-pack-live-venue-thaw-design-2026-09-06.md) + [runbook gates](./runbook-live-venue-thaw-gates-2026-09-06.md) — inventario, scorecard, qué NO afirmar.
4. Cerrar concepto UI: [diseño pasarela híbrido](./design-live-virtual-order-gateway-ui-2026-09-07.md) (telegrama + por qué + VIRTUAL).
5. Gobernanza: `paperDExecuteEnv=false` · `brokerVenue=paper` · kill off · **no** flip.
6. Pista A: **W+5** ya sellado ([remeasure](./traspaso-relevo-thaw-estricto-remeasure-2026-09-07.md)); siguiente fila solo con delta natural vs W+5.
7. **No** código producto · **no** paneles · **no** tip/bump · **no** arquitectura de settlement.

## Qué NO afirmar al cerrar

- LIVE capital / Accept LIVE / thaw prod.
- Que VIRTUAL = mock FILL = dinero real.
- Que la pasarela UI está **Accepted** / **shipped** (solo concepto documentado).
- Que este estudio autoriza `brokerVenue=live` o `PAPER_D_EXECUTE`.
- Accept estricto / `strictAcceptReady` (sigue **W+5** **0/5**).
