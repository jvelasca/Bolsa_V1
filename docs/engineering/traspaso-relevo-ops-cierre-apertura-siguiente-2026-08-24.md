RELEVO / TRASPASO — Ops (deuda operativa, FUERA de repo) ejercida 2026-08-24 → apertura fase siguiente

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (Product / Ops).
> **Propósito:** texto de paso para el **NUEVO CHAT**. La rebanada **Ops** (backlog §4, checklist de R-1/F-WORKER-1, 100% manual/sin código) se **ejerció parcialmente** (2 de 5 ítems) y su hallazgo (9 instrumentos LSE corruptos re-insertados) se amplió a una **rebanada de código+BD** ya committeada. La fase siguiente **la decide el propietario**. Read-first antes de escribir código.
> **AsOf cierre:** 2026-08-24. **HEAD = `cd93f51`** sobre `main`; `main` está **2 commits por delante de `origin/main`** (`3c53f4e` fix + `cd93f51` docs — **pendiente push**). Working tree **limpio**.
> **SHA (esta rebanada Ops→código):** `b5942cc` (docs Ops deuda operativa, ya pusheada) · `3c53f4e` (fix saneo símbolos `/` + limpieza BD) · `cd93f51` (docs fijar SHA). El push de los 2 últimos queda **pendiente de decisión del propietario**.

---

## 1. Qué está hecho (alcance de esta rebanada — Ops, manual, sin código)

El propietario confirmó fase = **Ops** (backlog §4): checklist operativo de R-1/F-WORKER-1. Naturaleza 100% **manual/entorno**, sin cambios de código en el repo.

### Ítems HECHOS (2026-08-24)

- **BD — 9 instrumentos LSE corruptos corregidos** (hallazgo: era **9 filas**, no 1 como decía el doc):
  - Patrón slash en `symbol`+`yahoo_symbol`: `BP/.L`·`BA/.L`·`AV/.L`·`RR/.L`·`SN/.L`·`JD/.L`·`NG/.L`·`UU/.L`·`BT/A.L`→`BTA.L`.
  - Ejecutado en `bolsa_v1` (docker `bolsa-postgres`): `UPDATE instruments SET symbol=replace(symbol,'/',''), yahoo_symbol=replace(yahoo_symbol,'/','')` → `UPDATE 9`.
  - **Verificado:** 0 `/` restantes · 0 duplicados en `UNIQUE(symbol,exchange)`/`UNIQUE(yahoo_symbol)` · 0 refs denormalizadas (`symbol` en decision_sessions/strategy_tops/optimization_runs/pending_orders/price_alerts/signal_alert_subscriptions) con slash · FKs a `id` intactas (no se tocó `id`).
  - Backup en tabla `_backup_instruments_corrupt` (9 filas) — **se conserva** como red de seguridad (documentada en backlog §4 y ops §2.4).
- **Logs locales purgados:** **4811 archivos / 8.88 MB** bajo `logs/` (`dev`·`api`·`agent`·`startup`·`tests` + `.txt` raíz: `dev-repro.txt`/`dev-verify-fix.txt`/`tc.txt`), excluyendo `.gitkeep`. Verificado: `git status` limpio (0 cambios, todo gitignored).

### AMPLIACIÓN DE ALCANCE (hallazgo Ops → rebanada de código+BD, CERRADA)

El checklist Ops buscaba "verificar que el auto-sync de `BP.L` ya no emite warning 404". **Falló**: las 9 filas corruptas con slash habían sido **re-insertadas** tras el fix manual (10:14:40). Investigación read-only de causa raíz → provider remoto FTSE100 (CSV yfiua) suministra tickers mangled (`BP/`·`BT/A`·`BP/.L`·`BT/A.L`); `UNIQUE(symbol,exchange)` no los bloquea (strings distintos) y cada resincronización de `idx-ftse100` los re-inserta.

Rebanada de código acotada (aprobada por el propietario, commit único `3c53f4e` + docs `cd93f51`):

- `remote_market_constituents.py::_symbol_parts`: sanea `/` en la fuente → `BP/.L`→`BP.L`, `BT/A.L`→`BTA.L`.
- `import_instrument.py`: chokepoint `normalize_yahoo_symbol`/`normalize_symbol` (quita `/`; fallback preserva `.MC/.MA`).
- Tests: `test_import_instrument.py` (nuevo) + casos en `test_remote_intl_constituents.py`.
- Limpieza BD en transacción (backup `_backup_instruments_corrupt`=27): 9 corruptas + su `sync_queue`/`data_sync_log` eliminadas; `idx-ftse100`=(100) re-mapeado a las limpias.
- Reinicio del stack dev (código stale) y **verificación read-only final APROBADA**. Detalles en backlog §0 RELEVO "FIX SANEADO SÍMBOLOS `/`".

### Ítems PENDIENTES del propietario (no ejecutables por el agente)

- **GitHub secret scanning nativo** en UI: `Settings → Code security and analysis` → Secret scanning + Push protection **Enable** (la CI `gitleaks.yml` ya escanea; esto es defensa de plataforma).
- **`TRUSTED_PROXIES` prod:** poblar env con las IP/CIDR del proxy de borde (formato `config.py:28`, `"10.0.0.1,203.0.113.0/24"`). **Bloqueado por valores reales del usuario**; default vacío es seguro (rate-limit usa `client.host`).
- **(Opcional) Purga valores dev** en historial git público (filter-repo/BFG) — diferida por decisión explícita.

## 2. Verificación / batería

| Check                                                                                     | Resultado      |
| ----------------------------------------------------------------------------------------- | -------------- |
| Rebanada **manual/ops** inicial (0 código), 2 de 5 ítems                                  | ✅             |
| **Ampliación código+BD**: fix saneo símbolos `/` + limpieza BD (CERRADA)                  | ✅             |
| BD `UPDATE 9` en transacción + backup previo `_backup_instruments_corrupt`                | ✅             |
| 0 filas con `/` · 0 duplicados UNIQUE · `idx-ftse100`=100 limpias · backup`=27            | ✅             |
| Batería código: ruff 0 · mypy 0 · pytest 35 passed · verificador read-only APROBADO       | ✅             |
| Logs purgados (4811 archivos) · solo `.gitkeep` restante · `git status` limpio            | ✅             |
| Docs de estado actualizados (`backlog §0` + `ops-r1-seguridad-operaciones` + este relevo) | ✅             |
| Lints (docs md)                                                                           | no aplica (md) |

## 3. Qué NO tocar (freeze) — sin cambios respecto al relevo D3 previo

- Motor money / ledger / `ExecuteTrade` internals · `order_intent.py` (fase dedicada con auditoría de call-sites).
- Belief / gobernanza IA · `contract:gen` salvo fase pactada · Track B B1–B12 · `pending-delete` (E8 N) · no `regen_full`.
- Fase 0 Decision Spine (F0.5/F0.6/D2/Esc.3/D1) · Cierre deuda confirm SEMI · **D3**: todas CERRADAS, no reabrir.
- (Nuevo aviso de esta fase) La tabla `_backup_instruments_corrupt` en `bolsa_v1` es **red de seguridad**; no es código de repo y puede eliminarse cuando se confirme que el auto-sync de `BP.L` no vuelve a generar el warning.
- **Push pendiente:** `main` está 2 commits por delante de `origin/main` (`3c53f4e` + `cd93f51`). Decisión del propietario si se empuja; hasta entonces ninguna otra rebanada debe depender de esos commits remotos.

## 4. Tarea del siguiente chat (fase nueva — SIN aprobar)

**PASO 0 (obligatorio, sin código):** el propietario decide qué fase sigue. El agente solo presenta opciones ancladas al backlog y espera decisión. NO abrir código antes.

Candidatos registrados (backlog §0 + PROJECT_STATE §3 + DEUDA §4):

- **Ops residual (manual, sin código):** los 2 ítems pendientes del propietario (secret scanning UI · `TRUSTED_PROXIES` prod). **NOTA 2026-08-24:** el tercer ítem (verificar que el auto-sync de `BP.L` ya no emite warning 404) quedó **RESUELTO por una rebanada de código+BD** (backlog §0 RELEVO "FIX SANEADO SÍMBOLOS `/`"): se saneó `_symbol_parts` (provider FTSE100) + `ImportInstrument`, y se limpió la BD (0 símbolos con `/`, `idx-ftse100`=100 limpias). Verificación abierta (entorno): confirmar que el auto-sync de `BP.L` ya no emite 404 (depende de disponibilidad del ticker en Yahoo); si se confirma, puede eliminarse `_backup_instruments_corrupt`.
- **Unificación Research→Radar** (`plan-unificacion-research-radar-2026-08-21.md`, DRAFT/APARCADO — requiere decisión; enlaza con D3: Lab/Radar universo laboratorio).
- **F-IND-1 residual** (causalidad indicadores chikou/fractals en research; NOTA en F2).
- **Limpieza residuos históricos dev** (`m7-win-*`, `M2 *`).
- **F9/V2** (requiere ADR + diseño + decisión explícita del propietario).

**Después (con fase aprobada):** rebanada acotada, path:line verificado, batería, verificador read-only (alcance disjunto), aprobación del propietario antes de commit.

## 5. Texto de arranque (pegar en el chat nuevo)

```
CONTEXTO: Fase 0 Decision Spine — TODAS las decisiones CERRADAS (D1, D2 f7b1f6c,
Esc.3/D1 7530556, D3 CONFIRMADA ea0c93f). Cierre deuda confirm SEMI CERRADA (2281903 + a264b60).
Rebanada D3 pusheada (ad8fd23 en origin/main). Ops ejercida 2026-08-24 (docs b5942cc pusheada):
9 instrumentos LSE BP/.L→BP.L corregidos en BD + logs purgados (4811 archivos, solo .gitkeep),
backup _backup_instruments_corrupt. Hallazgo Ops → REBANADA DE CÓDIGO CERRADA: fix saneo símbolos
'/' en import/índices (import_instrument.py normalize_yahoo_symbol/normalize_symbol + _symbol_parts
provider FTSE100) para evitar el 404 recurrente del auto-sync BP.L; limpieza BD (0 '/' , idx-ftse100=100
limpias); batería ruff 0 · mypy 0 · pytest 35 · verificador read-only APROBADO. COMMITS EN main SIN PUSH:
3c53f4e (fix) + cd93f51 (docs) — main > origin/main por 2. Working tree limpio, HEAD=cd93f51.
LEE (read-first, obligatorio): backlog §0 + PROJECT_STATE §3 + PROJECT_PREMISES ⭐§0.

IDENTIDAD: QROS (Lab) + Investment OS (mesa) + Decision Spine. No reconstruir.

TAREA: PRIMERO -> el propietario decide (a) si se EMPUJAN los 2 commits pendientes (3c53f4e + cd93f51)
de main a origin/main, y (b) QUÉ FASE SIGUE. Candidatas: ops residual (secret scanning UI,
TRUSTED_PROXIES prod, confirmar auto-sync BP.L sin warning — manual/sin código, bloqueado por cre-
denciales/IPs del propietario); Unificación Research->Radar (DRAFT/APARCADO, requiere decisión);
F-IND-1 residual (causalidad indicadores); limpieza residuos dev (m7-win-*, M2 *); F9/V2 (ADR+decisión).
NO lanzo agentes ni código hasta aprobar la fase y su alcance.
DESPUÉS -> rebanada acotada, path:line verificado, batería, verificador read-only (alcance disjunto),
aprobación del propietario antes de commit.

NO TOCAR: money/ledger/ExecuteTrade internals, gobernanza IA, contract:gen salvo fase pactada,
Track B B1-B12 (cerrado), pending-delete (E8 N), regen_full sin decisión,
order_intent.py (mapping default exit/reduce->sell, fase dedicada con auditoría de call-sites).
NO REABRIR: Fase 0 Decision Spine (F0.5/F0.6/F0.6-UI/D2/Escalón 3/D1) ni Cierre deuda confirm SEMI.
Aviso Ops: `_backup_instruments_corrupt` (BD bolsa_v1) = red de seguridad del fix BP.L; puede
eliminarse al confirmar que el auto-sync de BP.L ya no genera warning 404.

Protocolo: subagente acotado + verificador read-only, alcance disjunto, batería,
aprobación del propietario antes de commit.
```
