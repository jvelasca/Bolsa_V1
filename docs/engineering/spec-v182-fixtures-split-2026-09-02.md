# Spec — V1.82 Fixtures Split (higiene E2E mock)

> **AsOf:** 2026-09-02 · **Estado:** **CERRADA** (código + pre-flight local) · **stamp CI GREEN remoto** pendiente tras tag `v1.82-beta`.  
> **Padre:** [`spec-v181-t2-pov-stages-2026-09-02.md`](./spec-v181-t2-pov-stages-2026-09-02.md) · relevo [`traspaso-relevo-v1-81-t2-pov-stages-2026-09-02.md`](./traspaso-relevo-v1-81-t2-pov-stages-2026-09-02.md).  
> **Partida tip:** **V1.81** CERRADA — tip código [`4fcfc9bb`](https://github.com/jvelasca/Bolsa_V1/commit/4fcfc9bb) (tag [`v1.81-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.81-beta)) · docs stamp [`4d7120cf`](https://github.com/jvelasca/Bolsa_V1/commit/4d7120cf) (+ handoff [`3fcc8ade`](https://github.com/jvelasca/Bolsa_V1/commit/3fcc8ade)) · CI GREEN [run 33648642728](https://github.com/jvelasca/Bolsa_V1/actions/runs/33648642728). **No** LIVE.

Higiene: modularizar [`apps/web/e2e/fixtures.ts`](../../apps/web/e2e/fixtures.ts) (~800 LOC) al estilo V1.79 (`integration.ts` → `e2e/helpers/*` + barrel). **Misma semántica mock** · **sin** cambiar asserts · **sin** nuevos stages/productos. Gate filtro CI **intacto** (sin `gp-v182`).

```text
fixtures.ts (barrel) → helpers/e2e-mock-*.ts
API pública exportada desde ./fixtures intacta
pre-flight = mismo filtro release-tag playwright-mock → 33 passed
```

```text
P0  GP-V182-00 — Split + barrel; specs importan ./fixtures sin cambios de semántica
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` **off** · **NO LIVE** · sin scheduler prod · sin bump `1.35.0-beta` · sin `dryRun=false` browser · sin fills ledger.  
V1.72–V1.81 intactos. **No** Playwright en `frontend-ci`. **No** integrated E2E obligatorio.

## 1. Contrato de split

| Pieza                      | Destino                          | Rol                                            |
| -------------------------- | -------------------------------- | ---------------------------------------------- |
| Runtime flags / enable     | `helpers/e2e-mock-runtime.ts`    | `e2eEnabled` · setters · workspace override    |
| HTTP helpers + `routeBody` | `helpers/e2e-mock-routes.ts`     | `jsonResponse` · `apiPath` · catálogo · bodies |
| Installers                 | `helpers/e2e-mock-installers.ts` | `installApiMocks` · Mercado/Hoy/lifecycle      |
| Barrel                     | `apps/web/e2e/fixtures.ts`       | Re-export API pública                          |

## 2. IN

| ID         | Pri | Comportamiento                                                     |
| ---------- | --- | ------------------------------------------------------------------ | ------------------- |
| GP-V182-00 | P0  | Split módulos + barrel · **0** cambio de asserts · filtro CI sin ` | gp-v182`. **DONE**. |

### Entregables técnicos

1. Tres módulos helpers — **DONE**
2. `fixtures.ts` → barrel — **DONE**
3. Docs: spec · plan · arranque · relevo · CURRENT_SYSTEM · engineering-index §51 — **DONE**
4. Pre-flight filtro V1.81 — **DONE** (33 passed · 3 skipped · tsc EXIT 0)
5. Stamp remoto vía tag `v1.82-beta` — **PENDING**

### Invariantes

```
export público ./fixtures estable (nombres + firmas)
semántica routeBody / install* idéntica
filtro playwright-mock intacto (sin gp-v182)
NO LIVE · no fills · no dryRun=false browser
```

## 3. OUT

- LIVE · scheduler · bump package · `dryRun=false` browser · fills ledger
- Cambiar asserts / stages / POV / desk CTA
- Playwright en `frontend-ci.yml`
- E2E integrado obligatorio
- Commitear `**/logs/`

## 4. Pre-flight (2026-09-02) — = CI

```bash
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- "gp-e2e|gp-v173|gp-v174|gp-v175|gp-v176|gp-v177|gp-v178|gp-v179|gp-v181"
# → 33 passed (3 integrated skipped)

pnpm --filter @bolsa/web exec tsc --noEmit
# → EXIT 0
```
