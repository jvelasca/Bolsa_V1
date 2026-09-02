# Spec — V1.80 CI GREEN Tip Honesty (mock certification gate)

> **AsOf:** 2026-09-02 · **Estado:** **CERRADA** (código + pre-flight local; **sin stamp CI GREEN remoto** until Actions — tag `v*` / `workflow_dispatch`).  
> **Padre:** [`spec-v179-stateful-position-lifecycle-2026-09-02.md`](./spec-v179-stateful-position-lifecycle-2026-09-02.md) · relevo [`traspaso-relevo-v1-79-stateful-position-lifecycle-2026-09-02.md`](./traspaso-relevo-v1-79-stateful-position-lifecycle-2026-09-02.md).  
> **Partida tip:** **V1.79** Stateful Position Lifecycle [`8228d1c3`](https://github.com/jvelasca/Bolsa_V1/commit/8228d1c3). **Commit:** TBD (parent). **No** LIVE.

Honestidad del tip **CI GREEN** en el gate de certificación por tag: el job `playwright-mock` de `release-tag-ci.yml` deja de certificar solo `gp-e2e` y pasa a exigir el **curado mock** V1.73–V1.79 (+ `gp-e2e`). Expanding the mock gate ≠ having a remote GREEN check yet: gate ready; remote stamp needs tag `v*` or `workflow_dispatch` after push. No es LIVE, no es Playwright en cada PR, no es E2E integrado con PostgreSQL obligatorio.

```text
frontend-ci (PR diario)
  → typecheck / lint / test / build / contract
  → SIN Playwright  (by design)

release-tag-ci (tag v* / certify)
  → security · shared · spine · frontend · python
  → playwright-mock: gp-e2e|gp-v173|…|gp-v179  (un solo filtro)
  → certify GREEN ⇔ todos los jobs required OK
```

Regla de honestidad: **GREEN tip = mock certification gate en release-tag**, no en `frontend-ci.yml`.  
`frontend-ci.yml` permanece **sin** Playwright a propósito (path-filters diarios intactos · costo/ruido de PR).

```text
P0  GP-V180-01 — Expandir job playwright-mock: gp-e2e + curado gp-v173…gp-v179
P0  GP-V180-02 — certify sigue needing playwright-mock; fallo mock ⇒ no GREEN
P1  GP-V180-03 — Documentar contrato: tip honesty ≠ Playwright-on-every-PR
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` **off** · **NO LIVE** · sin scheduler prod · sin bump `1.35.0-beta` · sin `dryRun=false` browser · sin fills ledger.  
V1.72–V1.79 intactos (WHY · multi-instrument · Paper Day · stale/UNKNOWN · session reliability · golden fixtures · lifecycle stateful).  
**No** mover Playwright a `frontend-ci.yml`.  
**No** hacer `playwright-integrated` (PG) obligatorio en cada run de tag.

## 1. Contrato de tip honesty

| Superficie                                   | Verdad                                                                                          |
| -------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `frontend-ci.yml`                            | **Sin** Playwright · PR diario sigue siendo barato                                              |
| `release-tag-ci.yml` `playwright-mock`       | Mock browser: un filtro `gp-e2e\|gp-v173\|gp-v174\|gp-v175\|gp-v176\|gp-v177\|gp-v178\|gp-v179` |
| `release-tag-ci.yml` `playwright-integrated` | Opt-in (`workflow_dispatch` · `run_e2e_integration`) · **no** required para certify             |
| `certify`                                    | `needs` incluye `playwright-mock` · fail any required ⇒ no artifact GREEN                       |

**Workflow diff (V1.80):** `.github/workflows/release-tag-ci.yml` job `playwright-mock` ahora ejecuta:

```bash
pnpm e2e -- "gp-e2e|gp-v173|gp-v174|gp-v175|gp-v176|gp-v177|gp-v178|gp-v179"
```

(antes solo `pnpm e2e -- gp-e2e`). Gate expandido; **sin stamp CI GREEN remoto** hasta que Actions corra con éxito.

## 2. IN

| ID         | Pri | Comportamiento                                                                                                                                     |
| ---------- | --- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| GP-V180-01 | P0  | En `.github/workflows/release-tag-ci.yml` job `playwright-mock`: además de `gp-e2e`, ejecutar el curado `gp-v173\|…\|gp-v179` (mismo `E2E_RUN=1`). |
| GP-V180-02 | P0  | `certify` no cambia de semántica: mock fail ⇒ Release tag CI not GREEN.                                                                            |
| GP-V180-03 | P1  | Spec/plan/auditor + relevo · CURRENT_SYSTEM · engineering-index dejan explícito: honesty en release-tag, no en frontend-ci.                        |

### Invariantes

```
frontend-ci.yml ↛ Playwright
playwright-mock corre gp-e2e ∧ curado V1.73–V1.79 (un filtro)
playwright-integrated sigue opt-in (no required en certify)
NO LIVE · dryRun honesto en mocks · sin fills ledger
V1.73–V1.79 mock siguen verdes en local pre-flight
expandir gate ≠ stamp CI GREEN remoto (pendiente Actions)
```

## 3. Entregables

1. Diff mínimo en `.github/workflows/release-tag-ci.yml` job `playwright-mock` (comando/curado) — **DONE**
2. Docs: spec · plan · arranque auditor · relevo · CURRENT_SYSTEM · engineering-index — **DONE** (este cierre)
3. Pre-flight local con el **mismo filtro** que CI — esperado EXIT 0 (puede aún estar corriendo en máquina local)

## 4. OUT

- LIVE · scheduler · bump package · `dryRun=false` browser · fills ledger
- T2 POV stages · rewrite motor · split `fixtures.ts`
- Playwright en **cada** PR vía `frontend-ci.yml`
- E2E integrado / PostgreSQL **obligatorio** en cada run de tag
- Cambiar semántica de productos V1.72–V1.79
- Declarar **stamp CI GREEN remoto** sin run exitoso de tag/`workflow_dispatch`

## 5. Pre-flight (local 2026-09-02)

Mismo curado que CI (`playwright-mock`):

```bash
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- "gp-e2e|gp-v173|gp-v174|gp-v175|gp-v176|gp-v177|gp-v178|gp-v179"

pnpm --filter @bolsa/web exec tsc --noEmit
# → EXIT 0 (esperado; pre-flight local puede aún estar en curso)
```

**Honestidad:** gate listo en YAML + evidencia local esperada. **Sin stamp CI GREEN remoto** hasta que `release-tag-ci` (tag `v*` o `workflow_dispatch`) complete en verde en Actions.
