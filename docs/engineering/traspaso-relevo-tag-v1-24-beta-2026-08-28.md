# RELEVO — tag v1.24-beta → auditoría / mañana (2026-08-28)

> **Padre:** [`traspaso-relevo-v1-24-honesty-2026-08-28.md`](./traspaso-relevo-v1-24-honesty-2026-08-28.md) · [ADR-041](../adr/041-operational-coherence.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).
> **Estado:** **PUBLICACIÓN** — tag `v1.24-beta` → tip `c75b26a6`. **Release tag CI:** pin URL tras Actions GREEN.
> **Arranque chat nuevo:** este relevo + V1.24 honesty + freeze SEMI.

---

## 0. Confirmación

- **Allowlist fases · trailing honest · vocabulario · plan contract · Estudio unavailable · formatPrice:** código + tests locales.
- DEX-1…DEX-5 **intactos**. Confirm = firma.
- Accept estricto **NO**. `PAPER_D_EXECUTE` default **OFF**. LIVE **experimental**. AUTO **off**.
- Cerrado vs v1.23: **honestidad semántica** (misma palabra / mismo número / misma fase) **sin motores nuevos**.
- Deuda abierta: OpportunityScore · correlación/VaR · batch propose · promover trail · grid Cobertura 180 · thaw · backtest risk_policy · V1.25 sizing — **no mezclar**.

## 1. Release

| Pieza     | Valor                                                                                          |
| --------- | ---------------------------------------------------------------------------------------------- |
| Tag       | `v1.24-beta` → `c75b26a6`                                                                      |
| Previo    | `v1.23-beta` → `4bc7426c` (tip docs `76c09388`)                                                |
| Relevo    | [`traspaso-relevo-v1-24-honesty-2026-08-28.md`](./traspaso-relevo-v1-24-honesty-2026-08-28.md) |
| Daily ops | `pnpm test:daily-ops:offline` PASS (6/6; spine 497 en fase 5)                                  |
| Spine     | subset daily-ops **497**                                                                       |
| ADR       | [ADR-041](../adr/041-operational-coherence.md) · product-vocabulary                            |

### Owner: publicar

```bash
git push origin main
git tag v1.24-beta
git push origin v1.24-beta  # Actions → GREEN → pin docs CI URL
```

## 2. Verificación pre-tag

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/web exec tsc --noEmit
pnpm test:daily-ops:offline
pnpm test:decision-spine
```

## 3. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · Confirm = firma · `PAPER_D_EXECUTE` off · mesa paper · LIVE experimental · Accept estricto parked · AUTO on no · trail thin ≠ autoridad · OpportunityScore aparcado · BETA · nav L1 congelada.

## 4. Preguntas de foco (auditor mañana)

1. ¿BLOCKED/EXPIRED en Mercado muestran Bloqueada/Caducada (no Preparada)?
2. ¿«Calidad N/100» y ranking «Encaja» (no Prioridad/PREPARADA)?
3. ¿Barrido chip ≠ Datos OHLCV; marketDataAsOf no siempre «—»?
4. ¿T1 en Ruta: tocado ≠ ✓ gestionado?
5. ¿Estudio API error → No disponible (no «0 · Añade»)?

## 5. Next

Elegir **un** epic: V1.25 operational safety ([`contrato-confirm-v125-ticket-2026-08-28.md`](./contrato-confirm-v125-ticket-2026-08-28.md) · marco [`analisis-vs-apps-top-operative-flow-2026-08-28.md`](./analisis-vs-apps-top-operative-flow-2026-08-28.md) · ADR-040 §10) **o** Lab `risk_policy` wiring. No thaw/AUTO.
