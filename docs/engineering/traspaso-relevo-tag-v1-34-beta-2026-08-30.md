# RELEVO — tag v1.34-beta (+ v1.27-beta) → auditoría / siguiente chat (2026-08-30)

> **Padre:** [`traspaso-relevo-v1-34-frente-b-drag-b-gamma-2026-08-30.md`](./traspaso-relevo-v1-34-frente-b-drag-b-gamma-2026-08-30.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** **PUBLICACIÓN** — tag `v1.34-beta` → tip; tag `v1.27-beta` → `3315b69a`.  
> **Deuda tag:** V1.28…V1.33.3 + V1.31.1 + V1.31.2 **absorbidos** en tip (sin SHA por epic).  
> **Fuera:** B-δ · OCO · entry/T1/T2 drag · flip execute · thaw.

---

## 0. Confirmación

- V1.27 POM en `3315b69a` + stack V1.28–V1.34 (cockpit → stop drag → Confirm `signedStop`): **código + tests**.
- Confirm = firma · gráfico no autoriza · sin PositionRevision desde chart · `PAPER_D_EXECUTE` default **OFF** · AUTO execute env off · nav L1 · LLM no ejecuta · H2 kill asimétrico.
- Cerrado vs v1.26: Position Operating Model + producto hasta Frente B-γ.
- Pre-flight local (2026-08-30): shared build · web `tsc` · `pnpm test:daily-ops:offline` OK · `pnpm test:decision-spine` **540**.

## 1. Release

| Pieza      | Valor                                                                                                                      |
| ---------- | -------------------------------------------------------------------------------------------------------------------------- |
| Tag tip    | `v1.34-beta` → `b5d6bc29`                                                                                                  |
| Tag POM    | `v1.27-beta` → `3315b69a`                                                                                                  |
| Previo     | `v1.26-beta` → `96c0d5d7`                                                                                                  |
| Feat tip   | `3340b0f3` V1.28–V1.34 product stack                                                                                       |
| Absorbidos | V1.28 · V1.29 · V1.30 · V1.31 · V1.31.1 · V1.31.2 · V1.32 · V1.33 · V1.33.1 · V1.33.2 · V1.33.3 (sin tag propio)           |
| Relevo tip | [`traspaso-relevo-v1-34-frente-b-drag-b-gamma-2026-08-30.md`](./traspaso-relevo-v1-34-frente-b-drag-b-gamma-2026-08-30.md) |
| Diseño     | [`diseno-operativa-auto-grafico-ACORDADO-2026-08-30.md`](./diseno-operativa-auto-grafico-ACORDADO-2026-08-30.md)           |
| Spine      | `pnpm test:decision-spine` **540**                                                                                         |
| Daily ops  | `pnpm test:daily-ops:offline` OK                                                                                           |
| Web tsc    | `pnpm --filter @bolsa/web exec tsc --noEmit` OK                                                                            |

### Owner: publicar

```bash
git push origin main
git push origin v1.27-beta v1.34-beta
```

## 2. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · Confirm = firma · `PAPER_D_EXECUTE` off · mesa paper · AUTO execute off · trail thin ≠ autoridad · stop drag = propose/Confirm only · nav L1 congelada · BETA.

## 3. Next

**Un** epic post-tag: entrada drag (aplazado) · UI histórico rico A6 · o B-δ — **solo con palabra explícita**. No thaw.
