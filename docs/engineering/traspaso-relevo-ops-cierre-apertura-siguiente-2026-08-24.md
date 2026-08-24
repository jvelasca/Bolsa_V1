RELEVO / TRASPASO — Ops (deuda operativa, FUERA de repo) CERRADA (parte ejecutable) → apertura fase siguiente

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (Product / Ops).
> **Propósito:** texto de paso para el **NUEVO CHAT**. La rebanada **Ops** (backlog §4, checklist de R-1/F-WORKER-1, 100% manual/sin código) se **ejerció** y su **parte ejecutable por el agente quedó CERRADA** (pushes + verificación de entorno read-only). La **sub-verificación abierta se RESOLVIÓ 2026-08-24**: re-sync vivo `idx-ftse100` confirmado sin 404 → `_backup_instruments_corrupt` ELIMINADA. Quedan **2 ítems bloqueados en el propietario** (secret scanning UI · `TRUSTED_PROXIES` prod). La fase siguiente **la decide el propietario**. Read-first antes de escribir código.
> **AsOf cierre:** 2026-08-24. **HEAD/`main` == `origin/main` == `1cdac2b`**, working tree **limpio**. Todo pusheado: el fix saneo `/` (`3c53f4e` código) + docs (`cd93f51`·`3b708d0`·`5bf0469`·`7363ec6`) + relevo renovado (`1cdac2b`).
> **SHA (esta rebanada Ops):** `b5942cc` (docs Ops deuda operativa) · `3c53f4e` (fix saneo símbolos `/` + limpieza BD) · `cd93f51` (docs fijar SHA) · `3b708d0` (docs relevo renovado) · `5bf0469` (docs backlog update-last push + verif entorno) · `7363ec6` (docs backlog update-last cierre Ops). **Todos PUSHEADOS.**

---

## 1. Qué está hecho (alcance de esta rebanada — Ops, manual, sin código)

El propietario confirmó fase = **Ops** (backlog §4): checklist operativo de R-1/F-WORKER-1. Naturaleza 100% **manual/entorno**, sin cambios de código en el repo (la rebanada de código+BD del fix saneo `/` se amplió en el ciclo previo y quedó **CERRADA** en `3c53f4e`).

### Ítems HECHOS (2026-08-24)

- **BD — 9 instrumentos LSE corruptos corregidos** (hallazgo: era **9 filas**): patrón slash en `symbol`+`yahoo_symbol` (`BP/.L`·`BA/.L`·`AV/.L`·`RR/.L`·`SN/.L`·`JD/.L`·`NG/.L`·`UU/.L`·`BT/A.L`→`BTA.L`) vía `replace(symbol,'/','')`/`replace(yahoo_symbol,'/','')` en `bolsa_v1` → `UPDATE 9`. **Verificado:** 0 `/` restantes · 0 duplicados UNIQUE · 0 refs denormalizadas con slash · FKs a `id` intactas.
- **Logs locales purgados:** **4811 archivos / 8.88 MB** bajo `logs/`, excluyendo `.gitkeep`; `git status` limpio (todo gitignored).
- **Verificación de entorno read-only 2026-08-24 (sin código):** en `bolsa.postgres/bolsa_v1` → **0** instrumentos con `/` en `symbol`/`yahoo_symbol` · los **9 yahoo_symbols limpios** presentes (BP.L · BTA.L · BA.L · AV.L · RR.L · SN.L · JD.L · NG.L · UU.L) con exchange LSE · **`idx-ftse100` = (100) miembros, 0 con slash**. Fix de código confirmado en working tree (`_symbol_parts` en provider FTSE100 + `ImportInstrument.normalize_yahoo_symbol`/`normalize_symbol`). (La tabla `_backup_instruments_corrupt`, red de seguridad, se **ELIMINÓ** tras confirmarse el re-sync — ver Verificación abierta §1.)
- **Pushes ejecutados y verificados:** todos los commits de la rebanada quedaron **pusheados**; `main == origin/main == 7363ec6`, 0/0, working tree limpio.

### Ítems PENDIENTES del propietario (no ejecutables por el agente)

- **GitHub secret scanning nativo** en UI: `Settings → Code security and analysis` → Secret scanning + Push protection → **Enable** (la CI `gitleaks.yml` ya escanea; esto es defensa de plataforma).
- **`TRUSTED_PROXIES` prod:** poblar env con las IP/CIDR del proxy de borde (formato `config.py:28`, `"10.0.0.1,203.0.113.0/24"`). **Bloqueado por valores reales del usuario**; default vacío es seguro (rate-limit usa `client.host`).
- **(Opcional) Purga valores dev** en historial git público (filter-repo/BFG) — diferida por decisión explícita.

### Verificación abierta (entorno) — RESUELTA 2026-08-24

- **Re-sync en vivo de `idx-ftse100` CONFIRMADO sin warning 404** (2026-08-24): con el stack dev activo (`run-dev`, terminal `3.txt`), se disparó un job de suscripción asíncrono `POST /api/market-indices/subscribe/jobs` (`indexKey=FTSE100`, `syncBars=false`) → **`completed` / `ready`** · `total=100` · `checked=100` · `imported=0` · **`failed=[]`** · listId `idx-ftse100` · contentHash `c100:...`. **Sin WARNING 404** para `BP.L` en el worker (`index_subscribe_worker`); sin líneas `404`/`WARN`/`Index subscribe` en el terminal. Como se confirmó, **`_backup_instruments_corrupt` fue ELIMINADA** (BD, aprobación del propietario; operación fuera de repo): se inspeccionó antes del drop (27 filas, las 27 con `/`, triplicados de los 9 símbolos corruptos) y se ejecutó `DROP TABLE` → `to_regclass` = None. Post-drop verificado: 507 instruments · 0 `/` · 9 yahoo_symbols LSE limpios · `idx-ftse100`=(100).

## 2. Verificación / batería

| Check                                                                                                                                                                                         | Resultado      |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------- |
| Rebanada **manual/ops**: checklist §4 — BP.L BD · logs · push · verif env (4/5; 2 pendientes del propietario)                                                                                 | ✅             |
| **Ampliación código+BD** previa: fix saneo símbolos `/` + limpieza BD (CERRADA)                                                                                                               | ✅             |
| BD: 0 `/` · 9 yahoo_symbols limpios · `idx-ftse100`=(100) sin slash · **backup ELIMINADA**                                                                                                    | ✅             |
| **Re-sync en vivo `idx-ftse100` SIN warning 404** (job `ready`, 100 checked, 0 failed) → `_backup_instruments_corrupt` DROPPED (27 filas corruptas) · post-drop intacto (507/0 · 9 LSE · 100) | ✅             |
| Batería de código de la ampliación (cierre previo): ruff 0 · mypy 0 · pytest 35 passed                                                                                                        | ✅             |
| Pushes: `main == origin/main == 1cdac2b`, working tree limpio                                                                                                                                 | ✅             |
| Update-last backlog + PROJECT_STATE + traspaso (verif env + drop backup)                                                                                                                      | pending commit |
| Lints (docs md)                                                                                                                                                                               | no aplica (md) |

## 3. Qué NO tocar (freeze) — sin cambios respecto al relevo Ops previo

- Motor money / ledger / `ExecuteTrade` internals · `order_intent.py` (fase dedicada con auditoría de call-sites).
- Belief / gobernanza IA · `contract:gen` salvo fase pactada · Track B B1–B12 (cerrado) · `pending-delete` (E8 N) · no `regen_full`.
- Fase 0 Decision Spine (F0.5/F0.6/D2/Esc.3/D1) · Cierre deuda confirm SEMI · **D3**: todas CERRADAS, no reabrir.
- **Aviso Ops (2026-08-24):** `_backup_instruments_corrupt` en `bolsa_v1` — **ELIMINADA** tras confirmarse el re-sync vivo de `idx-ftse100` sin warning 404 (ver §1 Verificación abierta). Ya no hay red de seguridad pendiente.

## 4. Tarea del siguiente chat (fase nueva — SIN aprobar)

**PASO 0 (obligatorio, sin código):** el propietario decide qué fase sigue. El agente solo presenta opciones ancladas al backlog y espera decisión. NO abrir código antes.

Candidatas registradas (backlog §0 + PROJECT_STATE §3 + DEUDA §4):

- **Ops residual (manual, sin código, bloqueado por valores del propietario):** solo los **2 pendientes** del checklist §4 (secret scanning UI · `TRUSTED_PROXIES` prod). ~~confirmar re-sync vivo `idx-ftse100` sin 404 → eliminar `_backup_instruments_corrupt`~~ → **HECHO 2026-08-24** (re-sync confirmado `ready`/0 failed · backup DROPPED).
- **Unificación Research→Radar** (`plan-unificacion-research-radar-2026-08-21.md`, DRAFT/APARCADO — requiere decisión; enlaza con D3: Lab/Radar universo laboratorio).
- **F-IND-1 residual** (causalidad indicadores chikou/fractals en research; NOTA en F2).
- **Limpieza residuos históricos dev** (`m7-win-*`, `M2 *`).
- **F9/V2** (requiere ADR + diseño + decisión explícita del propietario).

**Después (con fase aprobada):** rebanada acotada, path:line verificado, batería, verificador read-only (alcance disjunto), aprobación del propietario antes de commit.

## 5. Texto de arranque (pegar en el chat nuevo)

```
CONTEXTO: Ops (deuda operativa FUERA de repo) CERRADA en su parte ejecutable + sub-verificación de
entorno RESUELTA 2026-08-24. HEAD = 1cdac2b, main == origin/main == 1cdac2b, working tree limpio,
TODO PUSHEADO (incluye relevo renovado 1cdac2b).
La ampliación código+BD del hallazgo Ops quedó CERRADA: fix saneo símbolos '/' (compile a
import_instrument.py normalize_yahoo_symbol/normalize_symbol + _symbol_parts provider FTSE100; evita el
404 recurrente del auto-sync BP.L). Verificación entorno read-only: 0 '/' en instruments · 9 yahoo_symbols
limpios (BP.L/BTA.L/BA.L/AV.L/JD.L/NG.L/RR.L/SN.L/UU.L) · idx-ftse100=(100) sin slash.
RE-SYNC VIVO CONFIRMADO 2026-08-24 (job POST /api/market-indices/subscribe/jobs : indexKey=FTSE100,
syncBars=false) -> completed/ready, 100 checked, imported=0, failed=[], SIN warning 404 de BP.L.
En consecuencia, y con aprobación del propietario, se ELIMINÓ la tabla `_backup_instruments_corrupt`
(BD bolsa_v1; 27 filas corruptas; operación fuera de repo); post-drop intacto (507/0 · 9 LSE · 100).
Batería código ampliación: ruff 0 · mypy 0 · pytest 35. Logs purgados (4811 archivos).
LEE (read-first, obligatorio): backlog §0 + PROJECT_STATE §3 + PROJECT_PREMISES ⭐§0.

IDENTIDAD: QROS (Lab) + Investment OS (mesa) + Decision Spine. No reconstruir.

TAREA: PRIMERO -> el propietario decide QUÉ FASE SIGUE (E1). Candidatas: ops residual (solo secret
scanning UI + TRUSTED_PROXIES prod — manual/sin código, bloqueado por credenciales/IPs del propietario;
la confirmación del re-sync vivo idx-ftse100 y el drop de `_backup_instruments_corrupt` ya están HECHOS);
Unificación Research->Radar (DRAFT/APARCADO, requiere decisión); F-IND-1 residual (causalidad
indicadores); limpieza residuos dev (m7-win-*, M2 *); F9/V2 (ADR+decisión).
NO lanzo agentes ni código hasta aprobar la fase y su alcance.
DESPUÉS -> rebanada acotada, path:line verificado, batería, verificador read-only (alcance disjunto),
aprobación del propietario antes de commit.

NO TOCAR: money/ledger/ExecuteTrade internals, gobernanza IA, contract:gen salvo fase pactada,
Track B B1-B12 (cerrado), pending-delete (E8 N), regen_full sin decisión,
order_intent.py (mapping default exit/reduce->sell, fase dedicada con auditoría de call-sites).
NO REABRIR: Fase 0 Decision Spine (F0.5/F0.6/F0.6-UI/D2/Escalón 3/D1) ni Cierre deuda confirm SEMI.
Aviso Ops: `_backup_instruments_corrupt` ELIMINADA 2026-08-24 (confirmado re-sync vivo idx-ftse100 sin
404; drop aprobado). No recrear.

Protocolo: subagente acotado + verificador read-only, alcance disjunto, batería,
aprobación del propietario antes de commit.
```
