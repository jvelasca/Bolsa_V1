# Triage — P2 diferidos V2.10 (post tip v2.10.1-beta) (2026-09-05)

> **AsOf:** 2026-09-05 · **Tip:** [`v2.10.1-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.10.1-beta) → `a060af37` · package `1.39.1-beta`.  
> **Padre:** [audit pack V2.10](./audit-pack-v2-10-final-certification-2026-09-05.md) §3–§4 · [relevo V2.10.1 CI](./traspaso-relevo-v2-10-1-ci-green-2026-09-05.md) · [V2.9 visual](./traspaso-relevo-v2-9-visual-operational-certification-2026-09-05.md).  
> **Estado:** **TRIAGE DOCS ONLY** · **PRODUCT FREEZE** · **no implementar** · no tip/bump · no paneles.  
> **P2-04 provenance:** **cerrado** por tip `v2.10.1-beta` (fuera de esta lista).

## Freeze / honestidad (citas vigentes)

- CI GREEN ≠ pixel-perfect.
- Contraste = **Operational Contrast Smoke**, no auditoría WCAG completa.
- `text-[9px]` = metadata auxiliar, no verdad operacional.
- P2 diferidos **no bloquean BETA**.

---

## Tabla triage

| ID        | Tema                                      | Docs ancla                                                     | Evidencia código/test                                                                                                                                                                     | Política               | Reabrir solo si                                                                                         |
| --------- | ----------------------------------------- | -------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------- |
| **P2-01** | Pixel snapshots Win local · skip Linux CI | audit-pack §3–§4 · V2.10.1 matriz · V2.9 goldens `*-win32.png` | `apps/web/e2e/gp-e2e-v29-cabin-visual-mock.spec.ts` (`test.skip(…CI…)`) · snapshots `*-win32.png`                                                                                         | **Mantener diferido**  | Entorno render determinista (browser/fonts/OS) o ritual Linux `--update-snapshots`                      |
| **P2-02** | Contrast smoke ≠ WCAG Certification       | audit-pack scorecard · §4 «Nombrar smoke»                      | `apps/web/e2e/helpers/cabin-cert.ts` (`assertReadableContrast`) · suite contraste en `gp-e2e-v29` (sí en CI)                                                                              | **Mantener diferido**  | Programa a11y real (axe / AA completo / charts T1-T2). **Nunca** renombrar smoke → «WCAG Certification» |
| **P2-03** | Densidad `text-[9px]` en hints            | audit-pack §4 · V2.10.1 «metadata auxiliar»                    | Floor: `apps/web/src/features/trading/cabin-visual.ts` (`CABIN_TYPE` · meta ~12px · test prohíbe 9px en A–B) · residual 9px en hints adyacentes (`operativa-pulse`, drawers, mesa/charts) | **Mantener / vigilar** | Si 9px migra a ARM / Confirm / stop / PnL / labels operacionales (nivel A–B)                            |

---

## Non-goals (este triage)

- No goldens Linux sin pedido + entorno.
- No promover contraste a certificación WCAG.
- No mass restyle tipografía bajo freeze.
- No reabrir motor ni paneles «para arreglar P2».

---

## OUT

1. Auditor externo: P2-01/02/03 = **aceptados diferidos** bajo PRODUCT FREEZE.
2. Cadena post-freeze: [operational readiness](./audit-pack-v2-10-1-operational-readiness-2026-09-05.md) · [paper prep](./traspaso-relevo-paper-prep-post-v2101-2026-09-05.md).
3. Implementación solo con reopen gate explícito de la tabla.
