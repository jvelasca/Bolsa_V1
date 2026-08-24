RELEVO / TRASPASO — Ops (deuda operativa, FUERA de repo) ejercida 2026-08-24 → apertura fase siguiente

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (Product / Ops).
> **Propósito:** texto de paso para el **NUEVO CHAT**. La rebanada **Ops** (backlog §4, checklist de R-1/F-WORKER-1, 100% manual/sin código) se **ejerció parcialmente** (2 de 5 ítems), con hallazgo de ampliación de alcance. La fase siguiente **la decide el propietario**. Read-first antes de escribir código.
> **AsOf cierre:** 2026-08-24. **Partida = `origin/main` == `HEAD` == `ad8fd23`** (la rebanada D3 `ea0c93f` ya está **pusheada** junto al relevo `ad8fd23`), working tree **limpio**. Ops = **0 cambios de código** en repo; solo 2 docs de estado actualizados (`backlog §4` · `ops-r1-...`).
> **SHA:** la rebanada D3 quedo pusheada por el propietario/coordinador (HEAD + relevo `ad8fd23`). Este hilo Ops no crea commits de código.

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

### Ítems PENDIENTES del propietario (no ejecutables por el agente)

- **GitHub secret scanning nativo** en UI: `Settings → Code security and analysis` → Secret scanning + Push protection **Enable** (la CI `gitleaks.yml` ya escanea; esto es defensa de plataforma).
- **`TRUSTED_PROXIES` prod:** poblar env con las IP/CIDR del proxy de borde (formato `config.py:28`, `"10.0.0.1,203.0.113.0/24"`). **Bloqueado por valores reales del usuario**; default vacío es seguro (rate-limit usa `client.host`).
- **(Opcional) Purga valores dev** en historial git público (filter-repo/BFG) — diferida por decisión explícita.

## 2. Verificación / batería

| Check                                                                                     | Resultado      |
| ----------------------------------------------------------------------------------------- | -------------- |
| Rebanada **manual/ops** (0 código, 0 contrato, 0 migración Alembic)                       | ✅             |
| BD `UPDATE 9` en transacción + backup previo `_backup_instruments_corrupt`                | ✅             |
| 0 filas con `/` · 0 duplicados UNIQUE · 0 deny refs denormalizadas                        | ✅             |
| Logs purgados (4811 archivos) · solo `.gitkeep` restante · `git status` limpio            | ✅             |
| Docs de estado actualizados (`backlog §4` + `ops-r1-seguridad-operaciones` + este relevo) | ✅             |
| Lints (docs md)                                                                           | no aplica (md) |

## 3. Qué NO tocar (freeze) — sin cambios respecto al relevo D3 previo

- Motor money / ledger / `ExecuteTrade` internals · `order_intent.py` (fase dedicada con auditoría de call-sites).
- Belief / gobernanza IA · `contract:gen` salvo fase pactada · Track B B1–B12 · `pending-delete` (E8 N) · no `regen_full`.
- Fase 0 Decision Spine (F0.5/F0.6/D2/Esc.3/D1) · Cierre deuda confirm SEMI · **D3**: todas CERRADAS, no reabrir.
- (Nuevo aviso de esta fase) La tabla `_backup_instruments_corrupt` en `bolsa_v1` es **red de seguridad**; no es código de repo y puede eliminarse cuando se confirme que el auto-sync de `BP.L` no vuelve a generar el warning.

## 4. Tarea del siguiente chat (fase nueva — SIN aprobar)

**PASO 0 (obligatorio, sin código):** el propietario decide qué fase sigue. El agente solo presenta opciones ancladas al backlog y espera decisión. NO abrir código antes.

Candidatos registrados (backlog §0 + PROJECT_STATE §3 + DEUDA §4):

- **Ops residual (manual, sin código):** los 2 ítems pendientes del propietario (secret scanning UI · `TRUSTED_PROXIES` prod) + verificar que el auto-sync de `BP.L` ya no emite warning 404.
- **Unificación Research→Radar** (`plan-unificacion-research-radar-2026-08-21.md`, DRAFT/APARCADO — requiere decisión; enlaza con D3: Lab/Radar universo laboratorio).
- **F-IND-1 residual** (causalidad indicadores chikou/fractals en research; NOTA en F2).
- **Limpieza residuos históricos dev** (`m7-win-*`, `M2 *`).
- **F9/V2** (requiere ADR + diseño + decisión explícita del propietario).

**Después (con fase aprobada):** rebanada acotada, path:line verificado, batería, verificador read-only (alcance disjunto), aprobación del propietario antes de commit.

## 5. Texto de arranque (pegar en el chat nuevo)

```
CONTEXTO: Fase 0 Decision Spine — TODAS las decisiones CERRADAS (D1, D2 f7b1f6c,
Esc.3/D1 7530556, D3 CONFIRMADA ea0c93f). Cierre deuda confirm SEMI CERRADA (2281903 + a264b60).
Rebanada D3 pusheada (HEAD = ad8fd23 = relevo; ea0c93f + ad8fd23 en origin/main). Ops ejercida
2026-08-24: 9 instrumentos LSE BP/.L→BP.L etc. corregidos en BD (backup _backup_instruments_corrupt)
+ logs purgados (4811 archivos/8.88MB, solo .gitkeep). Working tree limpio, main==origin==ad8fd23.
LEE (read-first, obligatorio): backlog §0 + PROJECT_STATE §3 + PROJECT_PREMISES ⭐§0.

IDENTIDAD: QROS (Lab) + Investment OS (mesa) + Decision Spine. No reconstruir.

TAREA: PRIMERO -> el propietario decide QUÉ FASE SIGUE. Candidatas: ops residual (secret scanning UI,
TRUSTED_PROXIES prod, verificar auto-sync BP.L sin warning — manual/sin código, bloqueado por cre-
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
