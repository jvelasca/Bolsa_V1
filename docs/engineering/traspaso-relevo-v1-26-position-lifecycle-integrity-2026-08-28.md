# RELEVO — V1.26 Position Lifecycle Integrity (2026-08-28)

> **AsOf:** 2026-08-28 · **Estado:** **CÓDIGO** — producto V1.26-beta, **sin tag todavía**.
> **Padre:** [`traspaso-relevo-v1-25-operational-safety-2026-08-28.md`](./traspaso-relevo-v1-25-operational-safety-2026-08-28.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).
> **Estudio abierto (auditorías):** [`estudio-operativa-auto-y-grafico-2026-08-28.md`](./estudio-operativa-auto-y-grafico-2026-08-28.md) · arranque [`arranque-auditor-estudio-operativa-auto-grafico-2026-08-28.md`](./arranque-auditor-estudio-operativa-auto-grafico-2026-08-28.md).
> **Tag certificado previo:** `v1.25-beta` → `d3c2fd6b` (CI GREEN). Tip de `main` = este trabajo de docs+código hasta publicar `v1.26-beta`.

---

## Versionado (no deducir)

| Capa            | Valor                                                                             |
| --------------- | --------------------------------------------------------------------------------- |
| Producto        | **V1.26-beta** (Position Lifecycle Integrity)                                     |
| Tag certificado | **`v1.25-beta` → `d3c2fd6b`** hasta publicar `v1.26-beta`                         |
| Tip de main     | commits de V1.26 (código + este relevo); no es el commit certificado hasta el tag |

## 0. Qué cierra V1.26

| Pieza                                                                                          | Estado                 |
| ---------------------------------------------------------------------------------------------- | ---------------------- |
| `validateOperationalLevels` / `validate_operational_levels` (TS+PY)                            | CÓDIGO + tests         |
| Firma: pérdida con `adverse_exposure` (no `abs`); DENY `stop_wrong_side`                       | CÓDIGO + tests paridad |
| `signedStop` en Confirm API → RiskGate → snapshot PositionState                                | CÓDIGO + tests         |
| Stop inválido (0 / negativo) DENY `stop_invalid` (no sustituye en silencio)                    | CÓDIGO + tests         |
| Test SEMI TRIGGERED → Confirm → Fill → Position (identidad + stop firmado)                     | CÓDIGO                 |
| HTTP `POST /portfolio/trade` `trade_plan_snapshot=None` = HUMAN_MANUAL (no es el agujero SEMI) | DOCUMENTADO + test     |
| What-if fila Sector = `candidateSector` actual→después                                         | CÓDIGO + tests         |

## 1. Freeze heredado (intactos)

Confirm = firma · `PAPER_D_EXECUTE` off · AUTO off · Ranking ≠ BUY · trail thin ≠ autoridad · LLM no ejecuta · LAB ≠ TRADING · OpportunityScore aparcado · DEX-1…5 · nav L1 congelada · shell Mercado LISTAS\|GRÁFICO\|OPERATIVA · sin drag gráfico · sin móvil · BETA.

PositionStatus durable sigue `OPEN \| PARTIAL \| PROTECTED \| CLOSED`. T1 tocado ≠ gestionado (`target1AchievedAt`) **no** se promociona a status.

## 2. Lectura corregida (auditoría HTTP None)

`ExecuteGatedPortfolioTrade` pasa `trade_plan_snapshot=None` **a propósito**: es apertura HUMAN_MANUAL. El camino SEMI es Confirm → `PositionSyncCoordinator` (pasa el TradePlan, ahora con niveles firmados). No reabrir ese `None` como P0 de pérdida de plan IA.

## 3. Fuera de V1.26 (no mezclar)

| Prioridad                              | Tema                                                                                                                                                                        |
| -------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **ESTUDIO (auditorías)**               | Operativa AUTO + operativa gráfico — [`estudio-operativa-auto-y-grafico-2026-08-28.md`](./estudio-operativa-auto-y-grafico-2026-08-28.md) · **sin código** hasta acuerdo §8 |
| V1.26b / V1.27 UX operativa (sin drag) | Toast DISPARADA / T1 tocado · punto de fase en Listas · cockpit «¿qué hago?»                                                                                                |
| P1                                     | `EffectiveTradingPolicy` (eliminar default sector 40 como mandato)                                                                                                          |
| P1                                     | ExitPolicy por perfil                                                                                                                                                       |
| V1.27                                  | Mercado operativo (drag → Confirm, órdenes en gráfico) — **tras** estudio acordado                                                                                          |
| V1.28                                  | UX 10/10 (command palette, hotkeys, densidad)                                                                                                                               |
| Lab                                    | Backtest `risk_policy`                                                                                                                                                      |
| Producto                               | Grid Cobertura 180 · batch propose · OpportunityScore · VaR · thaw estricto · móvil                                                                                         |

## 4. Arranque siguiente chat

1. Leer este relevo + [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).
2. Verificar tests: `pnpm --filter @bolsa/shared test` · `pnpm test:decision-spine` (incluye `test_v126_semi_position_birth.py` + `test_operational_levels.py`).
3. No saltar a drag / AUTO ampliado / Mercado 2.0 visual sin **acuerdo de diseño** ([`estudio-operativa-auto-y-grafico-2026-08-28.md`](./estudio-operativa-auto-y-grafico-2026-08-28.md) §8). Siguiente rebanada código: tag `v1.26-beta` si CI GREEN **o** V1.26b (toast + fase en listas).
4. Auditorías externas: usar [`arranque-auditor-estudio-operativa-auto-grafico-2026-08-28.md`](./arranque-auditor-estudio-operativa-auto-grafico-2026-08-28.md).
5. No reabrir sizing paralelo ni tratar HTTP None como pérdida de TradePlan SEMI.

## 5. Verificación local

```bash
pnpm --filter @bolsa/shared test
pnpm --filter @bolsa/web exec tsc --noEmit
pnpm test:decision-spine
```

Tests focalizados V1.26: `operational-levels` · `risk-signature` (stop_wrong_side / stop_invalid) · `test_confirm_risk_signature` (signed_stop) · `test_v126_semi_position_birth` · `portfolio-scenario` (candidateSectorExposurePair) · `f3-risk-signature-block` geometría.
