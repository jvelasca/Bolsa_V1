# Handoff — SEMI libro DEMO slice 1 (2026-08-03)

> **Retomar aquí.** Padre: [demo-operating-modes-brief-2026-08-03.md](./demo-operating-modes-brief-2026-08-03.md) · [semi-demo-book-impl-slice1-2026-08-03.md](./semi-demo-book-impl-slice1-2026-08-03.md).

## Hecho (GO)

- Decisiones producto cerradas (modo, N, 10 % cash, H≠M en Confirm, diversif. suave, aprender por fases).
- Prefs `demo-book-prefs` + panel **Libro DEMO** en rail Coach.
- Alarmas Radar respetan MANUAL vs SEMI + sizing/tope posiciones.
- F3: cola con checks · lote Confirm+ejecutar · qty≈% cash · execute solo SEMI.
- Copy Camino C = «SEMI · Confirm DEMO».
- Docs indexados (README · HELP · Engineering Index).

## Pendiente inmediato

1. Smoke UI checklist en impl brief.  
2. Ranker país→EU→mundo (preferencia; no bloquea).  
3. Cola F3 → BD si sessionStorage duele.  
4. AUTO / Belief pesos — **no** hasta descongelar.

## Rama

`stage/semi-demo-book-slice1-2026-08-03` (abrir PR al estabilizar smoke).
