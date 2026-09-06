# ARRANQUE AUDITOR — V2.11 Confirm LIVE VIRTUAL (2026-09-07)

Eres auditor externo de Bolsa V1 **tip `v2.11-beta`** (package `1.40.0-beta`). Partida certificada previa **`v2.10.1-beta` → `a060af37`**. Alcance = **UI honesty LIVE VIRTUAL en Confirm**. No abras LIVE capital ni Accept estricto.

## Leer primero

1. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) (AsOf tip V2.11)
2. [`audit-pack-v2-11-live-virtual-confirm-2026-09-07.md`](./audit-pack-v2-11-live-virtual-confirm-2026-09-07.md)
3. [`traspaso-relevo-tag-v2-11-beta-2026-09-07.md`](./traspaso-relevo-tag-v2-11-beta-2026-09-07.md)
4. [`design-live-virtual-order-gateway-ui-2026-09-07.md`](./design-live-virtual-order-gateway-ui-2026-09-07.md)
5. Tip SHA exacto (tag `v2.11-beta`) — **no** auditar `main` por delante del tip

## Qué auditar

| Área            | Criterio PASS                                                     |
| --------------- | ----------------------------------------------------------------- |
| Banner/badge    | Texto VIRTUAL/SIMULADO · no capital real                          |
| Gateway Confirm | Telegrama + por qué · anti Ranking≠BUY / Arm≠Execute              |
| CTA             | Contiene LIVE VIRTUAL + simulado · **no** «Ejecutar en LIVE» solo |
| Evidencia       | Unit + E2E mock en pack · CI tip GREEN                            |
| Gobernanza      | `PAPER_D_EXECUTE` off · no claim thaw/Accept LIVE                 |

## Qué NO exigir / NO PASS por ausencia

- Accept estricto P1–P5 (W+5 **0/5** fondo)
- Settlement broker real
- Nivel 4 chaos/soak FULL
- Pixel WCAG completa

## Freeze (copiar)

NO LIVE capital · VIRTUAL hasta APP 100% · Confirm = firma · Arm ≠ Execute · Ranking ≠ BUY · `PAPER_D_EXECUTE` off · package `1.40.0-beta` · auditar **tag** `v2.11-beta`.
