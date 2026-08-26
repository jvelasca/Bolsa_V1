# RELEVO — tag v1.13-beta → auditoría (2026-08-26)

> **Padre:** [`audit-pack-estado-global-2026-08-26-v113.md`](./audit-pack-estado-global-2026-08-26-v113.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).
> **Estado:** **PUBLICACIÓN.** Tag `v1.13-beta` → `c8d5800`. **Release tag CI GREEN.**
> **Arranque chat nuevo / auditor:** pack v113 + ADR-035 §8 + `CURRENT_SYSTEM.md` + roadmap v1.13 + tag + Actions GREEN.

---

## 0. Confirmación

- D0 + **DEX-1…DEX-5**: código + tests + stamp docs.
- OR-2 cerrado vía DEX-1+DEX-2. Accept estricto **NO**. `PAPER_D_EXECUTE` default **OFF**. LIVE **experimental**. AUTO **off**.
- UI Mesa incidente / thaw / Redis multi-worker / mass sim = **fuera** de este tag.
- Planes nuevos de modelo: **ninguno** obligatorio tras este tag.

## 1. Release

| Pieza        | Valor                                                                                          |
| ------------ | ---------------------------------------------------------------------------------------------- |
| Tag          | `v1.13-beta` → `c8d5800`                                                                       |
| Previo       | `v1.12-beta` → `369b5d1`                                                                       |
| Pack auditor | [`audit-pack-estado-global-2026-08-26-v113.md`](./audit-pack-estado-global-2026-08-26-v113.md) |
| Spine        | `pnpm test:decision-spine` **483** (2026-08-26)                                                |
| Alembic      | `013` + `014`                                                                                  |
| CI tag       | `release-tag-ci.yml` (sin path-filter)                                                         |

### Owner: publicado

```bash
git tag v1.13-beta          # c8d5800
git push origin v1.13-beta  # Actions → GREEN → pin docs SHA
```

## 2. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · Confirm = firma · `PAPER_D_EXECUTE` default off · mesa paper · LIVE experimental · Accept estricto parked · broker producción no · AUTO on no · UI Mesa incidente no · BETA.

## 3. E1

1. Auditar contra pack v113 + ADR-035 §8 + tag + Actions GREEN. **Hecho** (2026-08-26) — A–K PASS · CI [32990245215](https://github.com/jvelasca/Bolsa_V1/actions/runs/32990245215) GREEN · spine 483 pre-tag.
2. Opción operativa: SEMI TRIGGERED → Confirm → `Ejecutar en PAPER` · DEX-2/3/5 en spine.
3. No Accept estricto sin DoD §4 + palabra **thaw**.
4. No módulos thin nuevos · no reabrir OR-1/3/4/5/6 ni DEX-1…5 a ciegas.
5. Candidatas post-tag: UI Mesa incidente · OperationalPolicy · mass sim · thaw (solo con palabra explícita).

## 4. Post-tag cerrado (no mezclar con DEX)

| Epic                                      | Estado                   | Relevo                                                                                                                                                                          |
| ----------------------------------------- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Decision Journal 2.0 Tesis** (ADR-036)  | **CERRADO** (2026-08-26) | [`traspaso-relevo-journal-20-tesis-2026-08-26.md`](./traspaso-relevo-journal-20-tesis-2026-08-26.md)                                                                            |
| **Journal Evolución** (ADR-036 §5)        | **CERRADO** (2026-08-26) | [`traspaso-relevo-journal-evolucion-2026-08-26.md`](./traspaso-relevo-journal-evolucion-2026-08-26.md)                                                                          |
| **Mesa incident UI** (DEX-3)              | **CERRADO** (2026-08-26) | [`traspaso-relevo-mesa-incident-ui-2026-08-26.md`](./traspaso-relevo-mesa-incident-ui-2026-08-26.md)                                                                            |
| **Operational Console**                   | **CERRADO** (2026-08-26) | [`traspaso-relevo-operational-console-2026-08-26.md`](./traspaso-relevo-operational-console-2026-08-26.md)                                                                      |
| **Journal hub UI** (Tesis ≈ Instrumentos) | **CERRADO** (2026-08-26) | [`traspaso-relevo-journal-hub-ui-2026-08-26.md`](./traspaso-relevo-journal-hub-ui-2026-08-26.md) · candidato tag [`v1.14-beta`](./traspaso-relevo-tag-v1-14-beta-2026-08-26.md) |

Solo lectura · sin Alembic · spine **483** tras J4 · DEX-1…5 **no reabiertos**.
