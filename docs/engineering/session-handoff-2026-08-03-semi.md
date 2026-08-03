# Handoff — SEMI libro DEMO (2026-08-03)

> **Retomar aquí.** Padres: [demo-operating-modes-brief](./demo-operating-modes-brief-2026-08-03.md) · [semi-demo-book-impl-slice1](./semi-demo-book-impl-slice1-2026-08-03.md).

## Hecho

### Slice 1 (PR #23 · main)
- Libro DEMO MANUAL/SEMI · sizing · F3 lote · Radar/Finalistas gates.

### Slice 1.1 — geo ranker (esta rama)
- `demo-book-geo-rank`: óptimo primero, luego país→EU→mundo (suave).
- F3 cola ordenada + badge país; Libro DEMO selector preferencia geo.
- Home inferido de `account.currency` (EUR→ES).

## Pendiente

1. Smoke UI checklist slice 1 (+ comprobar orden geo en F3).  
2. Cola F3 → BD si sessionStorage duele.  
3. AUTO / Belief pesos — **no** hasta descongelar.  
4. Opcional: enriquecer payload propose con `country` (evitar mapa instrumentos).

## Rama

`stage/semi-demo-geo-rank-2026-08-03`
