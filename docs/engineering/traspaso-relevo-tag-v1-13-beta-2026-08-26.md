# RELEVO — tag v1.13-beta → auditoría (2026-08-26)

> **Padre:** [`audit-pack-estado-global-2026-08-26-v113.md`](./audit-pack-estado-global-2026-08-26-v113.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).
> **Estado:** **PUBLICACIÓN.** Stamp release en curso · tag `v1.13-beta` · pin SHA tras Release tag CI GREEN.
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
| Tag          | `v1.13-beta` → **TBD** (pin docs tras CI GREEN)                                                |
| Previo       | `v1.12-beta` → `369b5d1`                                                                       |
| Pack auditor | [`audit-pack-estado-global-2026-08-26-v113.md`](./audit-pack-estado-global-2026-08-26-v113.md) |
| Spine        | `pnpm test:decision-spine` **483** (2026-08-26)                                                |
| Alembic      | `013` + `014`                                                                                  |
| CI tag       | `release-tag-ci.yml` (sin path-filter)                                                         |

### Owner: publicar

```bash
git tag v1.13-beta
git push origin v1.13-beta   # Actions → GREEN → pin docs SHA (como v1.12)
```

## 2. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · Confirm = firma · `PAPER_D_EXECUTE` default off · mesa paper · LIVE experimental · Accept estricto parked · broker producción no · AUTO on no · UI Mesa incidente no · BETA.

## 3. E1

1. Auditar contra pack v113 + ADR-035 §8 + tag + Actions GREEN (tras publicar).
2. Opción operativa: SEMI TRIGGERED → Confirm → `Ejecutar en PAPER` · DEX-2/3/5 en spine.
3. No Accept estricto sin DoD §4 + palabra **thaw**.
4. No módulos thin nuevos · no reabrir OR-1/3/4/5/6 ni DEX-1…5 a ciegas.
5. Candidatas post-tag: UI Mesa incidente · OperationalPolicy · mass sim · thaw (solo con palabra explícita).
