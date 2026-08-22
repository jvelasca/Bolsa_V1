# RELEVO / TRASPASO — R-12 Track C + gates en origin/main (2026-08-22)

> **⚠️ HISTÓRICO — R-12 CERRADA.** Relevo vivo: [`traspaso-relevo-r13-apertura-2026-08-22.md`](./traspaso-relevo-r13-apertura-2026-08-22.md). SHA incrustado (`4e13746`) **no es HEAD**. Verificar `git rev-parse origin/main`.
>
> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1.
> **Propósito:** texto de paso anti-alucinación. Leer este doc + backlog §0 + `PROJECT_STATE.md` §2ac + premisas ⭐§0 **antes de tocar nada**.
> **Fuente de coordinación:** GitHub [`jvelasca/Bolsa_V1`](https://github.com/jvelasca/Bolsa_V1) `origin/main`. SHA vivo = `git fetch` + `git rev-parse origin/main` (no asumir SHA de este fichero).
> **Firma de partida R-12:** `f7a86cc` · Track A+B **`48cc255`** · tag `v1.3.0` → `b778292`.
> **AsOf:** `origin/main` = **`4e13746`**. Tag **`v1.5.0-beta` → `5e52bd6`**. Gates R12-ACCOUNTS + R12-AUTH **F1–F10 + F8b–F8e** · **F7b apply local** · **F7c** · **JWT-only** · `scan.completed` worker + cron stamp. D4 **Opción C** · ADR-027 **Aceptado**. Pending-delete E8 **N** (sin purge). Ventana purge V2 T+0 **19/19**.

---

## 1. Qué está hecho

- Track A + B: **`48cc255`**. Track B **APROBADO** (mesa 5 puertas).
- Track C **C1–C5 en `origin/main`** (`5bc51ff`…`0eb8976`). Leftover CORE-R («Proponer F3» → `/confirm`) **hecho `8dd3caf`**. Copy E8 residual **`ce601c9`**.
- Gates infra + auth base: **R12-409** `eb24608` · **EXEC-B-CONC** `ca60d0a` · **R12-SCHED** `5e52bd6` · **R12-ACCOUNTS** `3c958f1` · **R12-AUTH F1** `e52e016` · **F2** `9f3354f` · **F3** `5fe5ace`. Pending-delete E8 tests **`851b545`** (**sin purge**).
- D4 JWT (Opción C): **F4** `cdda80d` · **F5** `02c86fc` · **F6+F7a** `98b4986` · **F8** `5e7c67b` · **F9** `26494d8` · **F8b** `2cd20b0` · **F8c** `b44cf52` · **F8d** `c697bae` · **F8e** `905acee` · **F10** `837ec85`. **F7b script + JWT-only gate** **`a93ac9f`**. **F7c + scan.completed + cron stamp** **`4e13746`**.

| Fase              | SHA       | Qué                                                                             |
| ----------------- | --------- | ------------------------------------------------------------------------------- |
| C1                | `5bc51ff` | `/confirm` + nav Confirmar + F3 → `bolsa:navigate`                              |
| C2                | `01af9ff` | Nav diaria Trading · Señales · Confirmar vs Laboratorio/Asesor                  |
| C3                | `97e20ab` | AUTO cuenta «No disponible (BETA)»; sin thaw                                    |
| C4                | `154fcd1` | Nav Libro (Operaciones + Historial)                                             |
| C5                | `0eb8976` | HELP + Ayuda + tracker + frase SEMI                                             |
| leftover CORE-R   | `8dd3caf` | `core-r-judgment.ts` Proponer F3 → Confirmar `/confirm`                         |
| copy E8 residual  | `ce601c9` | CTAs firma → Confirmar; atajos list-hub Señales/Laboratorio                     |
| R12-409 B1        | `eb24608` | 409 OpenAPI deposit/withdraw/trade                                              |
| EXEC-B-CONC       | `ca60d0a` | `ExecuteTrade` `balance_after` post-lock                                        |
| R12-SCHED         | `5e52bd6` | scheduler=crons; queue_poll \| arq                                              |
| R12-ACCOUNTS      | `3c958f1` | paquete `bolsa_application/accounts/` + fachada                                 |
| R12-AUTH F1       | `e52e016` | principal `app`; stamp `user_id`; 404 cuenta ajena                              |
| R12-AUTH F2       | `9f3354f` | CORE-R/mandatos/F3/perfil + GET cartera/`X-Account-Id`                          |
| R12-AUTH F3       | `5fe5ace` | deposit/withdraw + `POST /portfolio/trade` mismo 404; motor intacto             |
| R12-AUTH F4       | `cdda80d` | ADR-027 **Aceptado** · Opción C · inventario gaps                               |
| R12-AUTH F5       | `02c86fc` | tabla `users` + login JWT + middleware `principal=sub`                          |
| R12-AUTH F6+F7a   | `98b4986` | list/get accounts scoped · legacy NULL solo bootstrap/admin                     |
| R12-AUTH F8       | `5e7c67b` | perfiles inversor scoped · job custodia filtra cuentas                          |
| R12-AUTH F8b      | `2cd20b0` | trackers + execution_policies scoped por `principal` (G6)                       |
| R12-AUTH F8c      | `b44cf52` | `platform_events` scoped por principal + stamp writes                           |
| R12-AUTH F8d      | `c697bae` | workspaces `user_id` migración 009 + CRUD scoped                                |
| R12-AUTH F8e      | `905acee` | list-for-list trackers + bulk schedule evaluate scoped                          |
| R12-AUTH F10      | `837ec85` | `session_version` · JWT `sv` · `/auth/refresh` · rate-limit user                |
| R12-AUTH F9       | `26494d8` | FE login con campo `login` opcional (JWT)                                       |
| purge V2 métricas | `0763700` | telemetría opt-in legacy storage; **E8 sigue N; sin purge**                     |
| kit monitor V2    | `a93ac9f` | log local `bolsa-legacy-storage-metrics-log` cap 200; E8 N; **sin purge**       |
| R12-AUTH F7b      | `a93ac9f` | script offline; **apply local 2026-08-22** (`bolsa_v1` 103→0 NULL; **no prod**) |
| JWT-only gate     | `a93ac9f` | SHA-256/HMAC → 401; `tokens.py` eliminado; env `APP_PASSWORD` = flag            |
| pending-delete E8 | `851b545` | tests migrador; E8 sigue N; **sin purge**                                       |
| monitor V2 T+0    | —         | batería 19/19; E8 N; **sin purge**                                              |
| R12-AUTH F7c      | `4e13746` | match estricto `user_id == principal`; NULL invisible incl. bootstrap           |
| scan.completed    | `4e13746` | worker `ownerUserId` + cron `EnqueueTrackerScanJob` estampa `tracker.user_id`   |

Mesa viva: **Trading · Señales · Confirmar · Libro** | herramientas | **Laboratorio · Asesor**.

## 2. NO tocar

`pending-delete` alto (purge) · gobernanza IA · `PAPER_D_EXECUTE` · `contract:gen` (salvo fase pactada) · split `backtests-page` · fusión research/screeners · money motor (`ExecuteTrade`, custodia apply) · apply F7b en **prod** sin ventana de mantenimiento.

## 3. Texto de paso (pegar en chat nuevo)

> CONTEXTO: Bolsa_V1, R-12. Lee `docs/engineering/traspaso-relevo-r12-apertura-2026-08-21.md` · `plan-r12-auth-d4-jwt-multiuser-2026-08-22.md` · ADR-027 · `PROJECT_PREMISES.md` ⭐§0 · `PROJECT_STATE.md` §2ac · backlog §0.
> Firma: `git fetch` + `git rev-parse origin/main` · `git status`. **`origin/main` `4e13746`**. Tag **`v1.5.0-beta` → `5e52bd6`** · tag `v1.3.0` → `b778292`. Partida R-12 `f7a86cc`.
> Hecho: … R12-AUTH F1–F10 + F8b–F8e · F7b script + **apply local** (103→0) · F7c hard close · JWT-only · ventana purge V2 T+0 19/19 (E8 N, sin purge) · `scan.completed` worker `ownerUserId` · cron `EnqueueTrackerScanJob` estampa `tracker.user_id`. **No auto.**

## 4. Siguiente (decisión del propietario)

1. **Seguir monitor ventana purge V2** — resto de 4–8 semanas (opt-in + log local; E8 N; T+0 hecho).
2. **Apply F7b** en staging/prod solo con ventana y URL explícita (ningún host remoto en el repo; local `bolsa_v1` ya aplicado).
