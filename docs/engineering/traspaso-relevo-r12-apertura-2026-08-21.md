# RELEVO / TRASPASO — R-12 Track C + gates en origin/main (2026-08-22)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1.
> **Propósito:** texto de paso anti-alucinación. Leer este doc + backlog §0 + `PROJECT_STATE.md` §2ac + premisas ⭐§0 **antes de tocar nada**.
> **Fuente de coordinación:** GitHub [`jvelasca/Bolsa_V1`](https://github.com/jvelasca/Bolsa_V1) `origin/main`. SHA vivo = `git fetch` + `git rev-parse origin/main` (no asumir SHA de este fichero).
> **Firma de partida R-12:** `f7a86cc` · Track A+B **`48cc255`** · tag `v1.3.0` → `b778292`.
> **AsOf:** `origin/main` = `git rev-parse origin/main` · tag **`v1.5.0-beta` → `5e52bd6`**. Gates R12-ACCOUNTS + R12-AUTH F1–F3 **cerrados**. D4 **Opción C** · **F4** ADR-027 **Propuesto** ([`027-auth-multi-user-jwt-hybrid.md`](./adr/027-auth-multi-user-jwt-hybrid.md)). Pending-delete E8 **N** (sin purge).

---

## 1. Qué está hecho

- Track A + B: **`48cc255`**. Track B **APROBADO** (mesa 5 puertas).
- Track C **C1–C5 en `origin/main`** (`5bc51ff`…`0eb8976`). Leftover CORE-R («Proponer F3» → `/confirm`) **hecho `8dd3caf`**. Copy E8 residual **`ce601c9`**.
- Gates: **R12-409** `eb24608` · **EXEC-B-CONC** `ca60d0a` · **R12-SCHED** `5e52bd6` · **R12-ACCOUNTS** `3c958f1` · **R12-AUTH F1** `e52e016` · **F2** `9f3354f` · **F3** `5fe5ace`. Pending-delete E8 tests **`851b545`** (**sin purge**).

| Fase              | SHA       | Qué                                                                 |
| ----------------- | --------- | ------------------------------------------------------------------- |
| C1                | `5bc51ff` | `/confirm` + nav Confirmar + F3 → `bolsa:navigate`                  |
| C2                | `01af9ff` | Nav diaria Trading · Señales · Confirmar vs Laboratorio/Asesor      |
| C3                | `97e20ab` | AUTO cuenta «No disponible (BETA)»; sin thaw                        |
| C4                | `154fcd1` | Nav Libro (Operaciones + Historial)                                 |
| C5                | `0eb8976` | HELP + Ayuda + tracker + frase SEMI                                 |
| leftover CORE-R   | `8dd3caf` | `core-r-judgment.ts` Proponer F3 → Confirmar `/confirm`             |
| copy E8 residual  | `ce601c9` | CTAs firma → Confirmar; atajos list-hub Señales/Laboratorio         |
| R12-409 B1        | `eb24608` | 409 OpenAPI deposit/withdraw/trade                                  |
| EXEC-B-CONC       | `ca60d0a` | `ExecuteTrade` `balance_after` post-lock                            |
| R12-SCHED         | `5e52bd6` | scheduler=crons; queue_poll \| arq                                  |
| R12-ACCOUNTS      | `3c958f1` | paquete `bolsa_application/accounts/` + fachada                     |
| R12-AUTH F1       | `e52e016` | principal `app`; stamp `user_id`; 404 cuenta ajena; **sin JWT**     |
| R12-AUTH F2       | `9f3354f` | CORE-R/mandatos/F3/perfil + GET cartera/`X-Account-Id`              |
| R12-AUTH F3       | `5fe5ace` | deposit/withdraw + `POST /portfolio/trade` mismo 404; motor intacto |
| pending-delete E8 | `851b545` | tests migrador; E8 sigue N; **sin purge**                           |

Mesa viva: **Trading · Señales · Confirmar · Libro** | herramientas | **Laboratorio · Asesor**.

## 2. NO tocar

`pending-delete` alto (purge) · gobernanza IA · `PAPER_D_EXECUTE` · `contract:gen` (salvo fase pactada) · split `backtests-page` · fusión research/screeners · auth JWT / multi-user (D4).

## 3. Texto de paso (pegar en chat nuevo)

> CONTEXTO: Bolsa_V1, R-12. Lee `docs/engineering/traspaso-relevo-r12-apertura-2026-08-21.md` · `plan-r12-track-c-frontend-2026-08-21.md` · `PROJECT_PREMISES.md` ⭐§0 · `PROJECT_STATE.md` §2ac · backlog §0.
> Firma: `git fetch` + `git rev-parse HEAD origin/main` · `git status`. HEAD local = **`5011ba5`** · `origin/main` = **`5011ba5`**. Tag **`v1.5.0-beta` → `5e52bd6`** · tag `v1.3.0` → `b778292` intacto. Partida R-12 `f7a86cc`.
> Hecho: … R12-AUTH F1–F3 · pending-delete E8 **`851b545`**. **F4:** ADR-027 **Propuesto** (Opción C). Siguiente = **Aceptar ADR-027** → F5 JWT bootstrap; opcional purge V2 métricas. **No auto.** Abrir chat nuevo si satura.

## 4. Siguiente (decisión del propietario)

1. Gates R12-409 … R12-AUTH F1–F3 **cerrados**. Pending-delete: E8 **N** (sin purge).
2. **F4 HECHO (docs):** ADR-027 **Propuesto** — Opción C híbrida. **Gate F5:** propietario marca ADR-027 **Aceptado** (+ política legacy F7a/b/c).
3. Opcional en paralelo: purge V2 métricas (plan `plan-r12-pending-delete-v2-purge-2026-08-22.md`). **Abrir chat nuevo** si satura.
