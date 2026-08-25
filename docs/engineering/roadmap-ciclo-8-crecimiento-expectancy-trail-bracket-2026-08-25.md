# Roadmap — Ciclo 8 · Crecimiento nombrado (expectancy · trail · bracket)

> **Padre:** [`traspaso-relevo-cierre-integridad-i1-i3-2026-08-25.md`](./traspaso-relevo-cierre-integridad-i1-i3-2026-08-25.md) §2 E1.4 · ADR-031 §6.
> **AsOf:** 2026-08-25.
> **Estado:** fase **cerrada (thin)** · **8.0 Expectancy thin CERRADO**; **8.1 Trail thin CERRADO**; **8.2 Bracket thin CERRADO**. Plena parked.
> **Método:** rebanadas finas tipo 5.0–5.3 / Ciclo 6. **No** reabrir Wyckoff 4.x · **no** re-hacer mappers 5.0–5.3 · **no** thaw AUTO.

---

## 0. Por qué esta fase

Integridad I1–I3 + RX1 cerraron honesty de execute. El dueño **nombró** crecimiento: expectancy · trail continuo · bracket. Eso **no** es I4 ni reopen 5.x.

| Slice   | Nombre               | Qué                                                                                      | Estado      |
| ------- | -------------------- | ---------------------------------------------------------------------------------------- | ----------- |
| **8.0** | Expectancy thin      | Mapper agregado thin (setup + R) → `runtime.expectancy` · Hoy/Board advisory · ≠ permiso | **CERRADO** |
| **8.1** | Trail continuo       | Advisory ratchet `trailPlan` (peak MFE−1R); **no** muta stop · alinea Exit Radar tip     | **CERRADO** |
| **8.2** | Bracket / T1 picture | Advisory picture entry/stop/T1/T2 + leg fracs; **no** OCO · **no** broker                | **CERRADO** |

---

## 1. Frontera 8.0 (solo)

| Incluye                                                         | Excluye (8.1 / 8.2 / otros)                                    |
| --------------------------------------------------------------- | -------------------------------------------------------------- |
| Pure `mapExpectancy` / `map_expectancy` sobre samples setup+R   | Trail continuo broker / mutar `structuralStop`                 |
| Eco `runtime.expectancy` + Board + Hoy «Expectativa» (métricas) | Bracket / T1 parcial fill / EvaluatePositionExits product wire |
| Live proxy desde Attribution (entrySetup) + MFE `currentR`      | Expectancy **plena** (scan journal histórico / fills cerrados) |
| Tests mapper + spine battery · stamp · relevo                   | Thaw / Shadow AUTO / `PAPER_D_EXECUTE` · fuse Router+Confirm   |

**Invariant:** expectancy thin ≠ permiso · ≠ auto-exit · ≠ thaw.

---

## 2. Secuencia

1. ~~Plan D1–D8 8.0~~ → feat 8.0 → stamp → relevo 8.0.
2. ~~Plan D1–D8 8.1~~ → feat 8.1 → stamp → relevo 8.1.
3. ~~Plan D1–D8 8.2~~ → feat 8.2 → stamp → relevo 8.2.
4. Expectancy / trail / bracket **plena** = fases posteriores si se piden.

---

## 3. Freeze de fase

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · SETUP Wyckoff cerrada · 5.x advisory intactos · Attribution 6 intacta · I1–I3 + RX1 intactos · Shadow AUTO **off** · `PAPER_D_EXECUTE` **off** · 8.0–8.2 thin ≠ permiso · plena parked.
