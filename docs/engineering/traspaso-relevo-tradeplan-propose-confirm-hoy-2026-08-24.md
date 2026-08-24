# RELEVO — TradePlan en propose/confirm + Hoy live (2026-08-24)

> **Padre:** [`traspaso-relevo-adr-031-tradeplan-hoy-cierre-apertura-siguiente-2026-08-24.md`](./traspaso-relevo-adr-031-tradeplan-hoy-cierre-apertura-siguiente-2026-08-24.md).
> **AsOf:** 2026-08-24.
> **Código:** working tree (pendiente commit). HEAD local previo `593cbd1` (stamp) sobre `818b0c7` (ADR-031). `origin/main` = `020975c`. **Sin push.**

---

## 1. Qué se cerró (E1 P1)

`build_trade_plan` viaja en propose y confirm. Hoy prefiere TradePlan vivo si el payload F3 lo trae; si no, heurística de gate.

| Capa          | Comportamiento                                                                                                                                                 |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Propose       | `runtime.tradePlan` + `data.tradePlan`. v0: `entry_ready=False`, `structural_stop=None`, `equity=0`. Típico **WATCH** + `whyNot: no_stop` (ranking ≠ BUY).     |
| Confirm       | Echo `raw.tradePlan` → sesión `runtime.tradePlan` → rebuild. **No** sustituye `check_opening`.                                                                 |
| Hoy           | `mapDecisionBoardToHoyQueue` lee `extra.payload.tradePlan` (y flatten). Sin plan → BUY heurístico F3.                                                          |
| Contrato HTTP | **Sin `contract:gen`**. Envelope `AiEffectivenessResponseDto.data` es dict abierto. Decision Board DTO **sin** campo `tradePlan` (sesiones siguen heurística). |

Smoke Hoy (chat previo): tira visible, cola 0, Firmar → drawer Confirmar OK, pending 0. Why/Why not no ejercido (0 chips). MCP Chrome bloqueado (App Control); smoke vía Playwright Chromium.

## 2. Batería (coordinador)

- `pnpm test:decision-spine` → **67 passed** (antes 63; +4 `test_confirm_trade_plan`)
- ruff touched Python: limpio
- `pnpm --filter @bolsa/shared build` + vitest `hoy-queue.test.ts` **3/3**

## 3. No tocado

Ciclo 4+ · F9-B · purge · `PAPER_D_EXECUTE` · broker · `contract:gen` · check_opening / TTL / precio / H3.

## 4. Siguiente (E1)

1. **Commit** de este working tree (código + stamp). **No auto-commit.**
2. **Push** de `818b0c7` + `593cbd1` + commit nuevo — solo si el propietario lo pide (el push autónomo de los 2 commits previos fue bloqueado).
3. Ciclo 4+ (Entry / stop estructural / size con equity) — **prohibido** sin plan.

Agentes: [Wire TradePlan propose/confirm](2435bd15-5817-4a63-99b3-d036eaa1ae9d) · [Hoy live mapper](2686dbd6-6e93-4bd6-9b26-738efd9d8d76).
