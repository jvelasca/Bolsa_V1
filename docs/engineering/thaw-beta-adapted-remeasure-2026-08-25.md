# Thaw BETA adaptado — remediación P1–P5' · 2026-08-25

> **AsOf:** 2026-08-25 · DB live `bolsa_v1` · API health `paperDExecuteEnv: false` pre-flip.  
> **Padres:** triage §2.3 [Informe 2](./audit-ext-round3-triage-estudio-motor-2026-08-04.md) · medición estricta [`thaw-p1-p5-measurement-2026-08-25.md`](./thaw-p1-p5-measurement-2026-08-25.md) (**FAIL**) · palabra **thaw** + «adapta y repite».  
> **Perfil:** **BETA-D parcial / condicionado** — no broker live · no producción.

---

## 0. Por qué adaptar

La barra **estricta** (60d · 50 SEMI · Prec≥70% · Rec≥55%) **FAIL** en DEMO actual:

| Estricto           | Medido                                            |
| ------------------ | ------------------------------------------------- |
| P1 60d             | 28d                                               |
| P2 50 SEMI Confirm | 0 (49/50 ledger buys = cuentas test)              |
| P3/P4 buy-alarma   | 0 filas `stance=buy` → precision null · recall 0% |
| P5 trading MaxDD   | 0 trades seed                                     |

El proyecto es **`v1.7.0-beta`**. Informe 2 del triage ya proponía barra más corta (≈30d · Prec≥60% · Rec≥50% · DD&lt;10%). Aquí se **adapta** esa columna a la realidad BETA con waivers explícitos (no se inventan %).

---

## 1. Umbrales adaptados (P1'–P5')

| #       | Adaptado BETA-D                                                                    | Medido 2026-08-25                                  | Pass  |
| ------- | ---------------------------------------------------------------------------------- | -------------------------------------------------- | ----- |
| **P1'** | ≥**25** días distintos con dictámenes (≈Informe 2 / 30d flojo)                     | **28** (`2026-07-22`…`2026-08-25`)                 | ✅    |
| **P2'** | SEMI path **probado en batería** + código Confirm; fills live ≥50 **waived** (W2)  | `pnpm test:decision-spine` **159**; 0 confirm live | ✅ W2 |
| **P3'** | Precisión BUY **diferida** (W3) — sin claim de ≥70% hasta haya `stance=buy` maduro | `buyPrecision5d=null` · `alarmaBuyCount=0`         | ✅ W3 |
| **P4'** | Recall BUY **diferido** (W4) — sin claim de ≥55%                                   | `buyRecall5d=0.0`                                  | ✅ W4 |
| **P5'** | MaxDD cash seed DEMO **≤10%** (sin exigir 1.2× Lab hasta haya trades)              | **0.2%** (deposit+fee)                             | ✅    |

### Waivers (firma producto = chat «adapta y repite» + thaw)

| Id        | Texto                                                                                                                                                   |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **W2**    | No exigir ≥50 fills SEMI live en BETA-D. Sustituto: spine SEMI Confirm + Gate en tests. Acumular fills reales **sigue** como deuda hacia thaw estricto. |
| **W3**    | No hay muestra buy-alarma. Thaw **no** afirma precisión Estudio. Camino D sigue `check_opening` / Risk Engine.                                          |
| **W4**    | Igual recall. Re-medir A0 cuando existan `stance=buy`.                                                                                                  |
| **Scope** | Solo cuenta **DEMO simulated** · `PAPER_D_EXECUTE` opt-in local · **no** broker · **no** demo compartida sin anotar.                                    |

---

## 2. Remeasure A0 (misma API)

```text
daysWithOpinions=28  alarmaBuyCount=0  buyPrecision5d=null  buyRecall5d=0.0
```

Health pre-thaw: `Kill switch off; PAPER_D_EXECUTE off`.

---

## 3. Gate adaptado

| Gate                         | Result                             |
| ---------------------------- | ---------------------------------- |
| P1'–P5' BETA-D               | **PASS** (con W2–W4)               |
| P6–P8 prep→producto          | UI AUTO on + kill/arm ya en código |
| P9 ADR-023                   | **Accepted — BETA parcial**        |
| P10 Freeze                   | Amend thaw parcial BETA-D          |
| Thaw estricto (60d/50/70/55) | **Sigue FAIL** — deuda abierta     |

**Verdict:** **READY TO THAW (BETA-D only).**

---

## 4. Acciones de thaw (este ciclo)

1. ADR-023 → Accepted BETA parcial.
2. Freeze §8 amend.
3. `DEMO_BOOK_AUTO_UI_ENABLED=true` + copy condicionado.
4. Default repo: `PAPER_D_EXECUTE` **sigue off** en código; opt-in local documentado (owner pone `=1` en env de API DEMO).
5. Re-auditar estricto cuando P1≥60 · P2 live≥50 · buy-alarma madura.

---

## Freeze residual

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · broker live **no** · thaw estricto **no** sustituido · W3/W4 = sin claim de precisión Estudio.
