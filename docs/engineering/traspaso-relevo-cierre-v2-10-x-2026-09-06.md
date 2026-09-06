# RELEVO — cierre certificable V2.10.x (2026-09-06)

> **Padre:** [relevo tag v2.10.1-beta](./traspaso-relevo-tag-v2-10-1-beta-2026-09-05.md) · [relevo V2.10.1 CI](./traspaso-relevo-v2-10-1-ci-green-2026-09-05.md) · [audit pack V2.10](./audit-pack-v2-10-final-certification-2026-09-05.md) · [triage P2](./triage-p2-v2-10-deferred-2026-09-05.md).  
> **AsOf:** 2026-09-06 · **PRODUCT FREEZE** · **NO MÁS PANELES** · **sin** tip/bump · **sin** código de producto · auditoría contra el **tag**, no contra `main`.  
> **Veredicto:** **V2.10.x CERRADA** (certificación + provenance). Siguiente etapa = Nivel 4 operacional (LIVE sigue bloqueado).

## Definición

**V2.10.1-beta** = cierre técnico y certificación de **V2.10**, no una versión funcional nueva.

| Rol                                    | Tag            | SHA        | Package       | CI                                                                                                           |
| -------------------------------------- | -------------- | ---------- | ------------- | ------------------------------------------------------------------------------------------------------------ |
| Release funcional original (histórico) | `v2.10-beta`   | `6495dd5f` | `1.39.0-beta` | [33980277268](https://github.com/jvelasca/Bolsa_V1/actions/runs/33980277268) `failure`                       |
| Hotfix certificación (código)          | —              | `7156169f` | `1.39.0-beta` | [33981998373](https://github.com/jvelasca/Bolsa_V1/actions/runs/33981998373) `success` (`workflow_dispatch`) |
| Release certificada (tip vigente)      | `v2.10.1-beta` | `a060af37` | `1.39.1-beta` | [33983574346](https://github.com/jvelasca/Bolsa_V1/actions/runs/33983574346) `success` (push del tag)        |

**No** se afirma `v2.10.1-beta = 7156169f = 1.39.0-beta`. Esa igualdad es falsa: el tip aporta bump/docs de provenance; el código de comportamiento es el del hotfix.

## Cadena de provenance (inmutable)

```text
v2.10-beta (inmutable)
    ↓
6495dd5f · package 1.39.0-beta · CI tag FAILURE
    ↓ hotfix E2E / sr-only (no motor)
7156169f · package 1.39.0-beta · CI dispatch SUCCESS
    ↓ bump + docs tip (sin .py/.ts/.tsx)
a060af37 · package 1.39.1-beta
    ↓
v2.10.1-beta · CI tag SUCCESS
    ↓
V2.10.x CERRADA
```

- **No** retaguear `v2.10-beta`.
- **No** mover `v2.10.1-beta` a `7156169f` (rompería identidad tag ↔ package).
- **No** crear `v2.10.2` / `v2.10.3` «una última mejora».

## A. Identidad (auditor: ir al tag, no a main)

| Pieza                     | Valor                                                                                                                 |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Git tag                   | `v2.10.1-beta`                                                                                                        |
| Commit tip                | [`a060af37c7359351782486573b4e751620cc00f2`](https://github.com/jvelasca/Bolsa_V1/commit/a060af37)                    |
| `package.json` en tip     | `1.39.1-beta`                                                                                                         |
| Release                   | [v2.10.1-beta](https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.10.1-beta) · **prerelease** · Final Certification |
| Código de comportamiento  | `7156169f288832c25c45222fec745b2cc13cbc20`                                                                            |
| Prueba tip = docs/package | `git diff --stat 7156169f a060af37` → solo `CHANGELOG.md`, `package.json`, `docs/*` (ningún `.py`/`.ts`/`.tsx`)       |
| Tip histórico             | `v2.10-beta` → `6495dd5f` intacto                                                                                     |

HEAD de `main` puede ir docs por delante del tip; **certificar HEAD no certifica el tag**.

## B. CI GREEN job a job

### B1 — CI del tag exacto (cierre)

[run 33983574346](https://github.com/jvelasca/Bolsa_V1/actions/runs/33983574346) · evento `push` · `headBranch=v2.10.1-beta` · `headSha=a060af37` · `conclusion=success`

| Job                                                   | Conclusión                          |
| ----------------------------------------------------- | ----------------------------------- |
| security (gitleaks)                                   | success                             |
| shared (build/typecheck/test)                         | success                             |
| decision-spine                                        | success                             |
| frontend (typecheck/lint/test/build + contract:check) | success                             |
| python (ruff/imports/mypy/pytest offline)             | success                             |
| lifecycle-pg (Alembic + auth + golden restart)        | success                             |
| playwright (mock E2E)                                 | success                             |
| playwright (integrated E2E, opt-in)                   | **skipped** (opt-in; no es failure) |
| certify (aggregate + artifact)                        | success                             |

### B2 — CI del hotfix (código certificable)

[run 33981998373](https://github.com/jvelasca/Bolsa_V1/actions/runs/33981998373) · `workflow_dispatch` · `headSha=7156169f` · misma matriz · `conclusion=success`

## C. Hotfix no contaminó el motor (`6495dd5f` → `7156169f`)

Paths tocados (código):

- E2E: `gp-v175` / `gp-v176` / `gp-v178` / `gp-v179` + `apps/web/e2e/helpers/assertions.ts` (expand `no_operar`)
- Vitest copy: chart HUD, journal, mesa KPI/inbox, entry-operating-summary
- Producto UI (único): `apps/web/src/features/trading/decision-surface-compact.tsx` — `sr-only` `position-decision-stop` / t1 / t2 en rama Journey HUD

**Ausentes** en el diff: FSM / `TRANSITIONS` · `PositionState` · outbox · ledger · financial events · Decision Spine · Execution Router · risk gates · Alembic.

El tip `a060af37` no añade código de producto respecto a `7156169f` (AUDITORIA 2: coherente).

## D. P2 diferidos (no bloquean cierre)

Lectura alineada con [triage](./triage-p2-v2-10-deferred-2026-09-05.md) + AUDITORIA 2:

| ID        | Tema                                      | Política                                                     |
| --------- | ----------------------------------------- | ------------------------------------------------------------ |
| **P2-01** | Pixel snapshots Win local · skip Linux CI | Diferido razonable (determinismo de entorno). No bloquea.    |
| **P2-02** | Contrast smoke ≠ WCAG 2.2 AA              | **Nunca** renombrar smoke → «WCAG Certification».            |
| **P2-03** | `text-[9px]` metadata auxiliar            | Vigilar; reabrir solo si migra a ARM / Confirm / stop / PnL. |

Ninguno toca Decision Spine, dinero ni gates auditados.

## E. Scorecard de cierre (objetivo)

| Área                                                                                                     | Estado      |
| -------------------------------------------------------------------------------------------------------- | ----------- |
| Decision Spine / FSM / Lifecycle / Financial / Outbox / Alembic / Execution Router / Operating Truth     | Congelado   |
| Mercado / Position / AUTO / Confirm / Protection / Journal / Chart / Hoy / Touch / Keyboard / Responsive | Certificado |
| E2E + CI tag                                                                                             | GREEN       |
| LIVE                                                                                                     | Bloqueado   |
| `PAPER_D_EXECUTE`                                                                                        | OFF         |
| Arm ≠ Execute · Confirm = firma · Ranking ≠ BUY · NO MÁS PANELES                                         | Intactos    |

## Freeze (copiar)

NO LIVE · `PAPER_D_EXECUTE` default off · no `TRANSITIONS` · no segundo FSM · Confirm = firma · Ranking ≠ BUY · Arm ≠ Execute · **NO MÁS PANELES** · **PRODUCT FREEZE** · package `1.39.1-beta` · tip `v2.10.1-beta` → `a060af37` · **no** `v2.10.2+` · **no** retaguear · siguiente trabajo = resiliencia / rendimiento / observabilidad / PAPER realista (LIVE sigue bloqueado).

## Qué NO hacer

- Mover o borrar `v2.10-beta` / `v2.10.1-beta`.
- Afirmar CI de `main`/HEAD como CI del tip.
- Añadir paneles, FSM, reglas de trading, scheduler, LIVE, AUTO execute autónomo.
- Implementar P2 bajo este cierre.
- Mezclar working-tree sucio de otras sesiones en el stamp de cierre.

## Post-cierre (fuera de este stamp)

- [Operational readiness](./audit-pack-v2-10-1-operational-readiness-2026-09-05.md) · stamp [PARTIAL](./traspaso-relevo-stamp-v2-10-1-operational-readiness-2026-09-06.md) · residuales B1·B3·C3 cerrados · A6/C2 abiertos
- [PAPER prep flags OFF](./traspaso-relevo-stamp-paper-prep-post-v2101-2026-09-06.md) · PASS honesty
- [Nivel 4 PARTIAL](./traspaso-relevo-stamp-nivel4-ops-partial-2026-09-06.md) · offline failure-injection PASS · chaos/OR-01 DEFER · **sin** thaw LIVE
- [Diseño LIVE venue](./audit-pack-live-venue-thaw-design-2026-09-06.md) · DESIGN_ONLY · [runbook](./runbook-live-venue-thaw-gates-2026-09-06.md) · **LIVE bloqueado**
- [Camino Accept estricto](./audit-pack-thaw-estricto-path-post-v2101-2026-09-06.md) · [W+4 remasure](./traspaso-relevo-thaw-estricto-remeasure-2026-09-06.md) · **0/5** · **NO** Accept

## Handoff auditor externo

> `v2.10.1-beta` ya está publicado como prerelease en `a060af37` / `1.39.1-beta`. Código de hotfix = `7156169f`. CI de tag exacto = `33983574346` SUCCESS. `v2.10-beta` intacto en `6495dd5f`. Listo para auditoría de cierre contra el tag, no contra `main`.

Si se pide retaguear a `7156169f`: **abortar** — degrada provenance (package `1.39.0-beta` en un tip `v2.10.1`).
