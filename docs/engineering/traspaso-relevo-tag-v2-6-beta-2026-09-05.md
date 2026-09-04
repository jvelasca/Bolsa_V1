# RELEVO — tag v2.6-beta → tip Pixel Premium (2026-09-05)

> **Padre:** [relevo V2.6 Pixel Premium](./traspaso-relevo-v2-6-pixel-premium-2026-09-05.md) · tip previo [`v2.5-beta`](./traspaso-relevo-tag-v2-5-beta-2026-09-05.md) `df57f0a9`.  
> **Estado:** tip `v2.6-beta` → [`50abd31d`](https://github.com/jvelasca/Bolsa_V1/commit/50abd31d) · package `1.36.0-beta` (bump autorizado para auditoría externa).  
> **Partida código tip previo:** `v2.5-beta` → `df57f0a9`.

## Release

| Pieza       | Valor                                                                            |
| ----------- | -------------------------------------------------------------------------------- |
| Tag tip     | `v2.6-beta` → [`50abd31d`](https://github.com/jvelasca/Bolsa_V1/commit/50abd31d) |
| Stamp docs  | este relevo + `CURRENT_SYSTEM` + arranque post-V2.38                             |
| Package     | `1.36.0-beta` (**bump** desde `1.35.0-beta`)                                     |
| Pre-release | https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.6-beta                      |

## Hecho (código tip)

- **V2.36** AUTO timeline = `OperatorPositionPlan` (misma escalera que Mercado L3)
- **V2.37** Numbers-first · `CABIN_VISUAL_VERSION = v2.37`
- **V2.38** UI Truth Hoy↔Mercado (niveles Journey2 · CTA mesa mapeada · e2e mock)
- Pre-flight vitest shared+web **PASS** (implementación)
- Ops: unprotected honesty PASS · birth protegido live **BLOCKED** (sin opens con stop estructural) · Journal ficha cerrada **N/A**
- **NO MÁS PANELES** · proyección display-only · sin segundo FSM

## Freeze

NO LIVE · `PAPER_D_EXECUTE` default off · no `TRANSITIONS` · no segundo FSM · Confirm = firma · Ranking ≠ BUY · chrome DECISIÓN (ADR-042) · 5 puertas L1 (ADR-040) · ExitPolicy **30/30** · HOY strip congelado · AUTO sin controles nuevos · `OperatorDecision` = proyección shared · **NO MÁS PANELES** · birth stop = Planificado + MANTENER · escalera T1→T2→trail.

## Next

- No reabrir V2.33–V2.38 salvo regresión display-only
- Seed ops: posición con stop estructural para validar birth Planificado/MANTENER en live
- Seed Journal: ficha cerrada con MFE/MAE para smoke live
- No reabrir motor FSM PAPER AUTO (`v2.0-beta`)
