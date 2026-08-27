# RELEVO — tag v1.17-beta → auditoría (2026-08-27)

> **Padre:** [`audit-pack-estado-global-2026-08-27-v117.md`](./audit-pack-estado-global-2026-08-27-v117.md) · [`traspaso-relevo-tag-v1-16-beta-2026-08-26.md`](./traspaso-relevo-tag-v1-16-beta-2026-08-26.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).
> **Estado:** **PUBLICACIÓN** — tag `v1.17-beta` → `_pendiente_stamp_`. **Release tag CI:** pendiente pin GREEN.
> **Arranque chat nuevo / auditor:** pack v117 + ADR-037 §7 + ADR-038/039 + `CURRENT_SYSTEM.md` + relevos P0/F1–F4 + este relevo.

---

## 0. Confirmación

- **P0 + F1…F4 + ops F5:** código + tests + relevos epic + pack v117.
- DEX-1…DEX-5 **intactos**. Confirm/DEX/SubmitIntent **sin cambios de contrato** (solo DI HTTP sanity).
- Accept estricto **NO**. `PAPER_D_EXECUTE` default **OFF**. LIVE **experimental**. AUTO **off**.
- Deuda AUTO/Lab **declarada** (no oculta): Router sanity · EdgeReport `paper_auto` · Redis SHA256 · backtest≠TradingPolicy.
- Planes nuevos de modelo: **ninguno** obligatorio tras este tag.

## 1. Release

| Pieza        | Valor                                                                                          |
| ------------ | ---------------------------------------------------------------------------------------------- |
| Tag          | `v1.17-beta` → `_pendiente_stamp_`                                                             |
| Previo       | `v1.16-beta` → `f16119b`                                                                       |
| Pack auditor | [`audit-pack-estado-global-2026-08-27-v117.md`](./audit-pack-estado-global-2026-08-27-v117.md) |
| Spine        | `pnpm test:decision-spine` **489** (2026-08-27)                                                |
| DoD mesa     | shared 53 · mesa-hoy 12 · opening+gated 19                                                     |
| CI tag       | `release-tag-ci.yml` (sin path-filter)                                                         |

### Owner: publicar

```bash
git tag v1.17-beta
git push origin main v1.17-beta  # Actions → GREEN → pin docs CI URL
```

## 2. Verificación pre-tag

```bash
pnpm --filter @bolsa/shared build
pnpm test:decision-spine
# expect: 489 passed

pnpm --filter @bolsa/shared exec vitest run portfolio-risk-metrics data-freshness investment-position-aggregate operational-priority portfolio-scenario mesa-next-action mesa-operable-ranking
pnpm --filter @bolsa/web test -- mesa-hoy

python -m pytest packages/py/application/tests/test_opening_permission.py packages/py/application/tests/test_execute_gated_portfolio_trade.py -q
# expect: 19 passed
```

## 3. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · Confirm = firma · `PAPER_D_EXECUTE` default off · mesa paper · LIVE experimental · Accept estricto parked · broker producción no · AUTO on no · sin HTTP nuevo Mesa · scenario ≠ permiso · BETA.

## 4. Limitaciones declaradas (v1.17-beta)

| ID     | Limitación                                   | Severidad           |
| ------ | -------------------------------------------- | ------------------- |
| AUTO-R | Router `check_opening` sin `sanity_warnings` | Deuda AUTO          |
| AUTO-E | EdgeReport no veta `paper_auto`              | Deuda AUTO          |
| LAB-R  | Redis pickle sin SHA256                      | Lab                 |
| LAB-B  | Backtest ≠ TradingPolicy                     | Lab (pre-AUTO)      |
| F3-D   | Scenario sin dry-run `check_opening`         | Post-estabilización |

## 5. E1 — Gate auditor

1. Auditar pack v117 + relevos P0/F1–F4 + ADR-037 §7 / 038 / 039.
2. Re-ejecutar verificación §2 en commit del tag.
3. CI GREEN → pin SHA en docs si hace falta.
4. No Accept estricto sin DoD thaw + palabra **thaw**.
5. No módulos thin nuevos · no reabrir DEX-1…5 ni OR a ciegas.
6. Candidatas post-tag: deuda AUTO §4 · dry-run gates · Lab backtest=policy.

## 6. Epics incluidos

| Epic              | Relevo                                                                                                                                   |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| P0 HTTP sanity    | [`traspaso-relevo-sesion-operativa-p0-http-sanity-2026-08-27.md`](./traspaso-relevo-sesion-operativa-p0-http-sanity-2026-08-27.md)       |
| F1 Mesa 3 niveles | [`traspaso-relevo-sesion-operativa-f1-mesa-3-niveles-2026-08-27.md`](./traspaso-relevo-sesion-operativa-f1-mesa-3-niveles-2026-08-27.md) |
| F2 Suitability    | [`traspaso-relevo-sesion-operativa-f2-suitability-2026-08-27.md`](./traspaso-relevo-sesion-operativa-f2-suitability-2026-08-27.md)       |
| F3 Scenario       | [`traspaso-relevo-sesion-operativa-f3-scenario-2026-08-27.md`](./traspaso-relevo-sesion-operativa-f3-scenario-2026-08-27.md)             |
| F4 Libro ruta     | [`traspaso-relevo-sesion-operativa-f4-libro-ruta-2026-08-27.md`](./traspaso-relevo-sesion-operativa-f4-libro-ruta-2026-08-27.md)         |
