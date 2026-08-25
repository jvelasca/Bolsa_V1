# Plan — Ciclo 7 Spine honesty (Composite stub + ExecuteTrade map)

> **Padre:** ADR-031 · relevo [`traspaso-relevo-ciclo-6-attribution-journal-thin-2026-08-25.md`](./traspaso-relevo-ciclo-6-attribution-journal-thin-2026-08-25.md) · síntesis E1 2026-08-25 (dual ExecuteTrade park · portfolioConstraints ship-now).
> **AsOf:** 2026-08-25 · HEAD **`59cdab6`** = `origin/main`; feat **`eef94ec`**.
> **Estado:** **CERRADO en origin** (`eef94ec` vía `59cdab6`).
> **Método:** higiene docs + copy UI; Ranking ≠ BUY; sin money path; sin `contract:gen`.

---

## 0. Objetivo

1. **Honesty Composite:** la pata `portfolioConstraints` sigue `not_evaluated` (peso 0); el Fit real vive en `check_opening`. Nota/UI no deben sugerir que «falta evaluar cartera en Composite».
2. **Honesty ExecuteTrade:** `CURRENT_SYSTEM` decía «dos call-sites» — en código son **3 spine** (Confirm · Router · FillPending) + **1 HTTP crudo** (`POST /portfolio/trade`). Convergencia pre-fill **parked M–L**.

### Incluye / Excluye

| Incluye                                             | Excluye                                           |
| --------------------------------------------------- | ------------------------------------------------- |
| Nota stub Composite + label UI `not_evaluated`      | Wire Fit dentro de Composite                      |
| Stamp CURRENT_SYSTEM call-sites 3+1 · park converge | Unificar ExecuteTrade / helper A↔C / tocar Router |
| Tests label + composite stub                        | Alembic · Shadow AUTO · Ciclo 5 · MFE             |

---

## 1. Defaults D1–D8

| Id  | Default                                             |
| --- | --------------------------------------------------- |
| D1  | Honesty Composite note + UI label + docs call-sites |
| D2  | Status sigue `not_evaluated` (no cambiar a ok)      |
| D3  | Sin wire Fit→Composite                              |
| D4  | Sin tocar ExecuteTrade / check_opening              |
| D5  | Docs: 3 spine + 1 raw; converge = park              |
| D6  | Sin `contract:gen`                                  |
| D7  | Sin Actionability/IO                                |
| D8  | Stamp + relevo 7; E1 ≠ PM / Shadow / converge       |

---

## 2. Arranque

```text
Implementar Ciclo 7 Spine honesty según este plan.
D1=note+label+docs · D2=status not_evaluated · D3=sin Fit en Composite · D4=sin ExecuteTrade · D5=map 3+1 park converge · D6=sin contract:gen · D7=sin IO server · D8=stamp.
```
