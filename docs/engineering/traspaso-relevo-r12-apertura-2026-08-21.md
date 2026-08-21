# RELEVO / TRASPASO — R-12 Track C en origin/main (2026-08-21)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1.
> **Propósito:** texto de paso anti-alucinación. Leer este doc + backlog §0 + `PROJECT_STATE.md` §2ac + premisas ⭐§0 **antes de tocar nada**.
> **Fuente de coordinación:** GitHub [`jvelasca/Bolsa_V1`](https://github.com/jvelasca/Bolsa_V1) `origin/main`. SHA vivo = `git fetch` + `git rev-parse origin/main` (no asumir SHA de este fichero).
> **Firma de partida R-12:** `f7a86cc` · Track A+B **`48cc255`** · tag `v1.3.0` → `b778292`.
> **AsOf:** leftover CORE-R **hecho** `8dd3caf`. Copy E8 residual (firma → Confirmar · atajos Señales/Laboratorio) en el mismo ciclo; SHA de ese commit = el de `origin/main` tras push.

---

## 1. Qué está hecho

- Track A + B: **`48cc255`**. Track B **APROBADO** (mesa 5 puertas).
- Track C **C1–C5 en `origin/main`** (`5bc51ff`…`0eb8976`). Leftover CORE-R («Proponer F3» → `/confirm`) **hecho `8dd3caf`**.

| Fase            | SHA local | Qué                                                            |
| --------------- | --------- | -------------------------------------------------------------- |
| C1              | `5bc51ff` | `/confirm` + nav Confirmar + F3 → `bolsa:navigate`             |
| C2              | `01af9ff` | Nav diaria Trading · Señales · Confirmar vs Laboratorio/Asesor |
| C3              | `97e20ab` | AUTO cuenta «No disponible (BETA)»; sin thaw                   |
| C4              | `154fcd1` | Nav Libro (Operaciones + Historial)                            |
| C5              | `0eb8976` | HELP + Ayuda + tracker + frase SEMI                            |
| leftover CORE-R | `8dd3caf` | `core-r-judgment.ts` Proponer F3 → Confirmar `/confirm`        |

Mesa viva: **Trading · Señales · Confirmar · Libro** | herramientas | **Laboratorio · Asesor**.

## 2. NO tocar

`pending-delete` alto · gobernanza IA · `PAPER_D_EXECUTE` · scheduler-vs-worker · `contract:gen` · `ExecuteTrade` cash_before · split `accounts.py` · split `backtests-page` · fusión research/screeners.

## 3. Texto de paso (pegar en chat nuevo)

> CONTEXTO: Bolsa_V1, R-12. Lee `docs/engineering/traspaso-relevo-r12-apertura-2026-08-21.md` · `plan-r12-track-c-frontend-2026-08-21.md` · `PROJECT_PREMISES.md` ⭐§0 · `PROJECT_STATE.md` §2ac · backlog §0.
> Firma: `git fetch` + `git rev-parse HEAD origin/main` · `git status`. Partida `f7a86cc` · tag `v1.3.0` → `b778292`.
> Track C **C1–C5** (`0eb8976`) + leftover CORE-R **hecho `8dd3caf`**. Fuente viva = `origin/main`. Gates 409/EXEC-B/scheduler no auto. Tag `v1.5.0-beta` solo si el propietario lo pide.

## 4. Siguiente (decisión del propietario)

1. Tag `v1.4.0` / `v1.5.0-beta` **solo** si lo pide.
2. Gates R-12 (409, EXEC-B-CONC, scheduler) siguen en decisión.
3. **Abrir chat nuevo** si este hilo satura (documento manda).
