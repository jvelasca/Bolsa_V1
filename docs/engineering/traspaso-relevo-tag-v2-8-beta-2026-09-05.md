# RELEVO — tag v2.8-beta → tip Operator Cabin Certification (2026-09-05)

> **Padre:** [relevo V2.8 Operator Cabin Certification](./traspaso-relevo-v2-8-operator-certification-2026-09-05.md) · tip previo [`v2.7-beta`](./traspaso-relevo-tag-v2-7-beta-2026-09-05.md) `8e7a5f95`.  
> **Estado:** tip `v2.8-beta` · package `1.38.0-beta` (bump autorizado para auditoría externa).  
> **Partida código tip previo:** `v2.7-beta` → `8e7a5f95`.  
> **Código feat:** [`65d5844f`](https://github.com/jvelasca/Bolsa_V1/commit/65d5844f) (V2.42–V2.45).

## Release

| Pieza       | Valor                                                       |
| ----------- | ----------------------------------------------------------- |
| Tag tip     | `v2.8-beta` → bump commit (stamp tras tag)                  |
| Stamp docs  | este relevo + `CURRENT_SYSTEM` + arranque post-V2.44        |
| Package     | `1.38.0-beta` (**bump** desde `1.37.0-beta`)                |
| Pre-release | https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.8-beta |
| Código tip  | `65d5844f` (feat) + bump/docs tip                           |

## Hecho (código tip)

- **V2.42** A3 cabin standard (`CABIN_TOUCH_TARGET` + `CABIN_TYPE` + focus)
- **V2.43** AUTO ARM chrome (`AUTO DESARMADO`/`ARMADO` · `EJECUCIÓN: PAPER` · Arm ≠ autorización)
- **V2.44** Cert 3 res + a11y (`gp-e2e-v28`)
- **V2.45** CI honesty (V2.7 tag ≠ GREEN documentado · fixes shared/typecheck/mercado mocks/gitleaks)
- Pre-flight: shared tests PASS · web typecheck PASS · e2e v25+v28 **22/22 PASS** local
- **NO MÁS PANELES** · proyección display-only · sin segundo FSM · Arm ≠ Execute · Arm ≠ autorización de operación

## Freeze

NO LIVE · `PAPER_D_EXECUTE` default off · no `TRANSITIONS` · no segundo FSM · Confirm = firma · Ranking ≠ BUY · chrome DECISIÓN (ADR-042) · 5 puertas L1 (ADR-040) · ExitPolicy **30/30** · HOY strip congelado · AUTO sin controles de trading nuevos · `OperatorDecision` = proyección shared · **NO MÁS PANELES** · birth stop = Planificado + MANTENER · Chart Focus / RESTANTE / Protection honesty intactos · escalera T1→T2→trail · package `1.38.0-beta`.

## Next

- Release-tag CI sobre `v2.8-beta` — stamp GREEN solo con `conclusion=success`
- No reabrir V2.42–V2.45 salvo regresión display-only
- Seed ops: stop estructural / Journal MFE·MAE (paralelo)
- No reabrir motor FSM PAPER AUTO (`v2.0-beta`)
