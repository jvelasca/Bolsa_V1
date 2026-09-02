# Arranque auditor — V1.80 CI GREEN Tip Honesty (2026-09-02)

> **Padre:** [`spec-v180-ci-green-tip-honesty-2026-09-02.md`](./spec-v180-ci-green-tip-honesty-2026-09-02.md) · partida **V1.79** [`8228d1c3`](https://github.com/jvelasca/Bolsa_V1/commit/8228d1c3)  
> **Estado slice:** **CERRADA** (código + pre-flight local; **sin stamp CI GREEN remoto** until Actions).

## Punta de partida

- Producto previo: **V1.79** Stateful Position Lifecycle (E2E mock locales; **sin** stamp CI GREEN del arco V1.73–V1.79)
- Cierre V1.80: `release-tag-ci.yml` job `playwright-mock` corre **un filtro** alineado con CI:
  `gp-e2e|gp-v173|gp-v174|gp-v175|gp-v176|gp-v177|gp-v178|gp-v179`
- Honestidad: `frontend-ci.yml` **sin** Playwright by design; GREEN tip honesty vive en **release-tag certify**
- **Crítico:** expandir el gate mock ≠ tener check CI GREEN remoto aún — falta tag `v*` o `workflow_dispatch` exitoso en Actions

## Qué auditar

| Paso                  | Evidencia                                                                                        |
| --------------------- | ------------------------------------------------------------------------------------------------ |
| Partida tip           | HEAD / tip documentado = V1.79 `8228d1c3` (o descendiente)                                       |
| frontend-ci           | Workflow **sin** pasos Playwright / `e2e`                                                        |
| playwright-mock       | Un `run:`: `pnpm e2e -- "gp-e2e\|gp-v173\|…\|gp-v179"` (mismo filtro pre-flight)                 |
| playwright-integrated | Sigue opt-in (`run_e2e_integration`) · **no** en `needs` de certify                              |
| certify               | `needs` incluye `playwright-mock` · mock fail ⇒ no GREEN                                         |
| Pre-flight local      | Mismo filtro único que CI · esperado EXIT 0 (puede aún estar corriendo)                          |
| Remote GREEN          | **Pendiente** — no declarar stamp hasta Actions OK                                               |
| Freeze / OUT          | NO LIVE · sin bump · sin `dryRun=false` browser · sin fills ledger · sin T2 · sin fixtures split |

## Pre-flight (local 2026-09-02) — expectativa = CI

```bash
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- "gp-e2e|gp-v173|gp-v174|gp-v175|gp-v176|gp-v177|gp-v178|gp-v179"

pnpm --filter @bolsa/web exec tsc --noEmit
# → EXIT 0 esperado
```

## No declarar

- **Stamp CI GREEN remoto** solo porque el YAML del gate ya está expandido (falta run Actions)
- LIVE · bump `1.35.0-beta` · `dryRun=false` browser · scheduler prod · fills ledger
- “Playwright en cada PR” / integrated E2E obligatorio / T2 POV / split `fixtures.ts`
