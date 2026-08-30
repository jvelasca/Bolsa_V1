# RELEVO — tag v1.34.1-beta → auditoría externa (2026-08-31)

> **Padre:** [`traspaso-relevo-tag-v1-34-beta-2026-08-30.md`](./traspaso-relevo-tag-v1-34-beta-2026-08-30.md) · [`traspaso-relevo-v1-34-frente-b-drag-b-gamma-2026-08-30.md`](./traspaso-relevo-v1-34-frente-b-drag-b-gamma-2026-08-30.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** **PUBLICACIÓN** — tag tip certificado `v1.34.1-beta` (producto V1.34 B-γ + CI tip GREEN).  
> **Arranque auditor:** [`arranque-auditor-v1-34-1-beta-2026-08-31.md`](./arranque-auditor-v1-34-1-beta-2026-08-31.md).  
> **Fuera:** B-δ · OCO · entry/T1/T2 drag · flip execute · thaw · nuevos epics.

---

## 0. Confirmación

- Producto **igual** que `v1.34-beta` (`b5d6bc29`): stop drag → Confirm `signedStop` (B-γ).
- Tip CI cerrado post-auditoría interna: ruff I001/B009 · mypy `_OpinionQuery` · fixtures `fetchedAt` relativos (stale 30d).
- Confirm = firma · gráfico no autoriza · `PAPER_D_EXECUTE` off · AUTO execute off · nav L1 · H2 kill asimétrico.
- Pre-flight: `pnpm test:decision-spine` **540** · `pnpm test:daily-ops:offline` OK · web `tsc` OK · Python CI tip [GREEN](https://github.com/jvelasca/Bolsa_V1/actions/runs/33339216149).

## 1. Release

| Pieza      | Valor                                                                                                                      |
| ---------- | -------------------------------------------------------------------------------------------------------------------------- |
| Tag tip    | `v1.34.1-beta` → tip docs pin (este commit)                                                                                |
| Código CI  | `ed84a717` (ruff `afe56506` · mypy `3fb63871` · fixtures stale)                                                            |
| Previo tip | `v1.34-beta` → `b5d6bc29` (CI tag RED)                                                                                     |
| Tag POM    | `v1.27-beta` → `3315b69a`                                                                                                  |
| Previo     | `v1.26-beta` → `96c0d5d7`                                                                                                  |
| Feat       | `3340b0f3` V1.28–V1.34 product stack                                                                                       |
| Relevo tip | [`traspaso-relevo-v1-34-frente-b-drag-b-gamma-2026-08-30.md`](./traspaso-relevo-v1-34-frente-b-drag-b-gamma-2026-08-30.md) |
| Diseño     | [`diseno-operativa-auto-grafico-ACORDADO-2026-08-30.md`](./diseno-operativa-auto-grafico-ACORDADO-2026-08-30.md)           |
| Spine      | `pnpm test:decision-spine` **540**                                                                                         |
| Python CI  | [GREEN](https://github.com/jvelasca/Bolsa_V1/actions/runs/33339216149)                                                     |
| CI tag     | pendiente post-push                                                                                                        |

### Owner: publicar

```bash
git push origin main
git push origin v1.26-beta v1.34.1-beta
# Actions Release tag CI → GREEN → pin URL en este relevo + CURRENT_SYSTEM
```

## 2. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · Confirm = firma · `PAPER_D_EXECUTE` off · mesa paper · AUTO execute off · trail thin ≠ autoridad · stop drag = propose/Confirm only · nav L1 congelada · BETA.

## 3. Next (post-auditoría externa)

**Un** epic: entrada drag · UI histórico rico A6 · o B-δ — **solo con palabra explícita**. No thaw.
