# RELEVO — tag v1.16-beta → auditoría (2026-08-26)

> **Padre:** [`audit-pack-estado-global-2026-08-26-v116.md`](./audit-pack-estado-global-2026-08-26-v116.md) · [`traspaso-relevo-tag-v1-15-beta-2026-08-26.md`](./traspaso-relevo-tag-v1-15-beta-2026-08-26.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).
> **Estado:** **PUBLICACIÓN** — tag `v1.16-beta` → `42469e7`. **Release tag CI:** pendiente pin GREEN.
> **Arranque chat nuevo / auditor:** pack v116 + ADR-037 + `CURRENT_SYSTEM.md` + relevos MD-1…MD-5 + este relevo.

---

## 0. Confirmación

- **MD-0 + MD-1…MD-5:** código + tests + relevos epic; feature **`11ee5ff`** + CI fix **`42469e7`** (tag).
- DEX-1…DEX-5 **intactos**. Confirm/DEX/SubmitIntent **sin cambios de contrato**.
- Accept estricto **NO**. `PAPER_D_EXECUTE` default **OFF**. LIVE **experimental**. AUTO **off**.
- Limitaciones P1/P2 **declaradas** (no ocultas): chip DS-05 · sanity E2E · what-if sin gates reales · Libro `showRoute`.
- Planes nuevos de modelo: **ninguno** obligatorio tras este tag.

## 1. Release (pendiente owner)

| Pieza        | Valor                                                                                          |
| ------------ | ---------------------------------------------------------------------------------------------- |
| Tag          | `v1.16-beta` → `42469e7`                                                                       |
| Previo       | `v1.15-beta` → `fc2ed753`                                                                      |
| Pack auditor | [`audit-pack-estado-global-2026-08-26-v116.md`](./audit-pack-estado-global-2026-08-26-v116.md) |
| Spine        | `pnpm test:decision-spine` **485** (2026-08-26)                                                |
| Backend F5   | pytest **72** passed (2026-08-26)                                                              |
| CI tag       | `release-tag-ci.yml` (sin path-filter)                                                         |

### Owner: publicado

```bash
git tag v1.16-beta          # 42469e7
git push origin main v1.16-beta  # Actions → GREEN → pin docs CI URL
```

## 2. Verificación pre-tag

```bash
pnpm --filter @bolsa/shared build
pnpm test:decision-spine
# expect: 485 passed

pnpm --filter @bolsa/shared exec vitest run mesa-next-action mesa-protection mesa-hoy mesa-operable-ranking decision-journal-relevant
pnpm --filter @bolsa/web test -- mesa-hoy mesa-position f3-trade-plan f3-risk-input-baseline

python -m pytest \
  packages/py/analytics/tests/test_lightgbm_checksum.py \
  packages/py/infrastructure/tests/test_config_production.py \
  packages/py/market/tests/test_sanity_opening_veto.py \
  packages/py/application/tests/test_execution_router.py \
  packages/py/application/tests/test_risk_engine.py \
  packages/py/application/tests/test_paper_d_propose.py \
  packages/py/application/tests/test_paper_auto_http_gate.py \
  packages/py/analytics/tests/test_lab_edge_report.py \
  apps/api-python/tests/test_auth.py -q
# expect: 72 passed
```

**Smoke browser (MD-1 / F6):** checklist 5/5 en [`traspaso-relevo-mesa-desk-v116-2026-08-26.md`](./traspaso-relevo-mesa-desk-v116-2026-08-26.md) §2.

## 3. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · Confirm = firma · `PAPER_D_EXECUTE` default off · mesa paper · LIVE experimental · Accept estricto parked · broker producción no · AUTO on no · sin HTTP nuevo Mesa · what-if read-only · BETA.

## 4. Limitaciones declaradas (v1.16-beta)

| ID   | Limitación                                        | Severidad      |
| ---- | ------------------------------------------------- | -------------- |
| F1-H | Chip datos DS-05 honesto (header + ops-self-eval) | P1 post-tag    |
| F5-G | `sanity_warnings` → runtime Confirm/AUTO          | P1 post-tag    |
| F4-C | What-if sin gates reales (proyección aritmética)  | P2 documentado |
| F2-B | `showRoute` solo `/mesa`; Libro fuera scope       | P1 post-tag    |

## 5. E1 — Gate owner

1. Auditar pack v116 + relevos MD-1…MD-5 + ADR-037.
2. Re-ejecutar verificación §2 en commit candidato.
3. Aprobar elevación → commit → tag → push → CI GREEN → pin SHA en docs.
4. No Accept estricto sin DoD §4 + palabra **thaw**.
5. No módulos thin nuevos · no reabrir DEX-1…5 ni OR a ciegas.
6. Candidatas post-tag: sanity E2E · chip DS-05 · Libro showRoute · gates what-if · `GET /api/mesa/today` · backtest TradingPolicy.

## 6. Epics incluidos

| Epic                           | Relevo                                                                                                 |
| ------------------------------ | ------------------------------------------------------------------------------------------------------ |
| MD-1 V1.16 Mesa desk           | [`traspaso-relevo-mesa-desk-v116-2026-08-26.md`](./traspaso-relevo-mesa-desk-v116-2026-08-26.md)       |
| MD-2 V1.17 Posición + ticket   | [`traspaso-relevo-mesa-desk-v117-2026-08-26.md`](./traspaso-relevo-mesa-desk-v117-2026-08-26.md)       |
| MD-3 V1.18 Evolución + alertas | [`traspaso-relevo-mesa-desk-v118-2026-08-26.md`](./traspaso-relevo-mesa-desk-v118-2026-08-26.md)       |
| MD-4 V1.19 What-if + operable  | [`traspaso-relevo-mesa-desk-v119-2026-08-26.md`](./traspaso-relevo-mesa-desk-v119-2026-08-26.md)       |
| MD-5 Backend paralelo          | [`traspaso-relevo-mesa-desk-backend-2026-08-26.md`](./traspaso-relevo-mesa-desk-backend-2026-08-26.md) |
