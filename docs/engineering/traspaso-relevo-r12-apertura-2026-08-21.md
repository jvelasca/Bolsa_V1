# RELEVO / TRASPASO — R-12 Track C + gates en origin/main (2026-08-22)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1.
> **Propósito:** texto de paso anti-alucinación. Leer este doc + backlog §0 + `PROJECT_STATE.md` §2ac + premisas ⭐§0 **antes de tocar nada**.
> **Fuente de coordinación:** GitHub [`jvelasca/Bolsa_V1`](https://github.com/jvelasca/Bolsa_V1) `origin/main`. SHA vivo = `git fetch` + `git rev-parse origin/main` (no asumir SHA de este fichero).
> **Firma de partida R-12:** `f7a86cc` · Track A+B **`48cc255`** · tag `v1.3.0` → `b778292`.
> **AsOf:** tag **`v1.5.0-beta` → `5e52bd6`** (R12-SCHED). SHA vivo = `git fetch` + `git rev-parse origin/main` (el stamp docs puede ir un commit por delante del tag; **el tag no se mueve**). Track C C1–C5 · copy E8 · leftover CORE-R · gates R12-409 / EXEC-B-CONC / R12-SCHED **cerrados**.

---

## 1. Qué está hecho

- Track A + B: **`48cc255`**. Track B **APROBADO** (mesa 5 puertas).
- Track C **C1–C5 en `origin/main`** (`5bc51ff`…`0eb8976`). Leftover CORE-R («Proponer F3» → `/confirm`) **hecho `8dd3caf`**. Copy E8 residual **`ce601c9`**.
- Gates: **R12-409** `eb24608` · **EXEC-B-CONC** `ca60d0a` · **R12-SCHED** `5e52bd6` (cierra también R-8C.2).

| Fase             | SHA       | Qué                                                            |
| ---------------- | --------- | -------------------------------------------------------------- |
| C1               | `5bc51ff` | `/confirm` + nav Confirmar + F3 → `bolsa:navigate`             |
| C2               | `01af9ff` | Nav diaria Trading · Señales · Confirmar vs Laboratorio/Asesor |
| C3               | `97e20ab` | AUTO cuenta «No disponible (BETA)»; sin thaw                   |
| C4               | `154fcd1` | Nav Libro (Operaciones + Historial)                            |
| C5               | `0eb8976` | HELP + Ayuda + tracker + frase SEMI                            |
| leftover CORE-R  | `8dd3caf` | `core-r-judgment.ts` Proponer F3 → Confirmar `/confirm`        |
| copy E8 residual | `ce601c9` | CTAs firma → Confirmar; atajos list-hub Señales/Laboratorio    |
| R12-409 B1       | `eb24608` | 409 OpenAPI deposit/withdraw/trade                             |
| EXEC-B-CONC      | `ca60d0a` | `ExecuteTrade` `balance_after` post-lock                       |
| R12-SCHED        | `5e52bd6` | scheduler=crons; queue_poll \| arq                             |

Mesa viva: **Trading · Señales · Confirmar · Libro** | herramientas | **Laboratorio · Asesor**.

## 2. NO tocar

`pending-delete` alto · gobernanza IA · `PAPER_D_EXECUTE` · `contract:gen` (salvo fase pactada) · split `accounts.py` · split `backtests-page` · fusión research/screeners · auth JWT (D4).

## 3. Texto de paso (pegar en chat nuevo)

> CONTEXTO: Bolsa_V1, R-12. Lee `docs/engineering/traspaso-relevo-r12-apertura-2026-08-21.md` · `plan-r12-track-c-frontend-2026-08-21.md` · `PROJECT_PREMISES.md` ⭐§0 · `PROJECT_STATE.md` §2ac · backlog §0.
> Firma: `git fetch` + `git rev-parse HEAD origin/main` · `git status`. Tag **`v1.5.0-beta` → `5e52bd6`** · tag `v1.3.0` → `b778292` intacto. Partida R-12 `f7a86cc`.
> Hecho: Track C C1–C5 (`0eb8976`) + leftover CORE-R `8dd3caf` + copy E8 `ce601c9` + gates **R12-409** `eb24608` · **EXEC-B-CONC** `ca60d0a` · **R12-SCHED** `5e52bd6`. Gates restantes (split accounts · auth · pending-delete) **no auto**. Fuente viva = `origin/main`.

## 4. Siguiente (decisión del propietario)

1. Gates **R12-409 / EXEC-B-CONC / R12-SCHED cerrados** (SHAs arriba). Leftover CORE-R **no** está pendiente.
2. Gates restantes si aplica (split `accounts.py`, auth) siguen en **decisión**; no auto-abrir.
3. **Abrir chat nuevo** si este hilo satura (documento manda).
