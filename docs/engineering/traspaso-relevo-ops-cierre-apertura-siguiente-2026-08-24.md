RELEVO / TRASPASO — Ops (deuda operativa, FUERA de repo) CERRADA (parte ejecutable) → apertura fase siguiente

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (Product / Ops).
> **Propósito:** texto de paso para el **NUEVO CHAT**. La rebanada **Ops** (backlog §4, checklist de R-1/F-WORKER-1, 100% manual/sin código) se **ejerció** y su **parte ejecutable por el agente quedó CERRADA** (pushes + verificación de entorno read-only). Quedan **2 ítems bloqueados en el propietario** (secret scanning UI · `TRUSTED_PROXIES` prod) y una **sub-verificación de entorno abierta** (re-sync vivo `idx-ftse100` sin 404). La fase siguiente **la decide el propietario**. Read-first antes de escribir código.
> **AsOf cierre:** 2026-08-24. **HEAD = `7363ec6`** sobre `main`; **`main == origin/main == 7363ec6`**, working tree **limpio**. Todo pusheado: el fix saneo `/` (`3c53f4e` código) + docs (`cd93f51`·`3b708d0`·`5bf0469`·`7363ec6`).
> **SHA (esta rebanada Ops):** `b5942cc` (docs Ops deuda operativa) · `3c53f4e` (fix saneo símbolos `/` + limpieza BD) · `cd93f51` (docs fijar SHA) · `3b708d0` (docs relevo renovado) · `5bf0469` (docs backlog update-last push + verif entorno) · `7363ec6` (docs backlog update-last cierre Ops). **Todos PUSHEADOS.**

---

## 1. Qué está hecho (alcance de esta rebanada — Ops, manual, sin código)

El propietario confirmó fase = **Ops** (backlog §4): checklist operativo de R-1/F-WORKER-1. Naturaleza 100% **manual/entorno**, sin cambios de código en el repo (la rebanada de código+BD del fix saneo `/` se amplió en el ciclo previo y quedó **CERRADA** en `3c53f4e`).

### Ítems HECHOS (2026-08-24)

- **BD — 9 instrumentos LSE corruptos corregidos** (hallazgo: era **9 filas**): patrón slash en `symbol`+`yahoo_symbol` (`BP/.L`·`BA/.L`·`AV/.L`·`RR/.L`·`SN/.L`·`JD/.L`·`NG/.L`·`UU/.L`·`BT/A.L`→`BTA.L`) vía `replace(symbol,'/','')`/`replace(yahoo_symbol,'/','')` en `bolsa_v1` → `UPDATE 9`. **Verificado:** 0 `/` restantes · 0 duplicados UNIQUE · 0 refs denormalizadas con slash · FKs a `id` intactas.
- **Logs locales purgados:** **4811 archivos / 8.88 MB** bajo `logs/`, excluyendo `.gitkeep`; `git status` limpio (todo gitignored).
- **Verificación de entorno read-only 2026-08-24 (sin código):** en `bolsa.postgres/bolsa_v1` → **0** instrumentos con `/` en `symbol`/`yahoo_symbol` · los **9 yahoo_symbols limpios** presentes (BP.L · BTA.L · BA.L · AV.L · RR.L · SN.L · JD.L · NG.L · UU.L) con exchange LSE · **`idx-ftse100` = (100) miembros, 0 con slash** · backup **`_backup_instruments_corrupt` conservada**. Fix de código confirmado en working tree (`_symbol_parts` en provider FTSE100 + `ImportInstrument.normalize_yahoo_symbol`/`normalize_symbol`).
- **Pushes ejecutados y verificados:** todos los commits de la rebanada quedaron **pusheados**; `main == origin/main == 7363ec6`, 0/0, working tree limpio.

### Ítems PENDIENTES del propietario (no ejecutables por el agente)

- **GitHub secret scanning nativo** en UI: `Settings → Code security and analysis` → Secret scanning + Push protection → **Enable** (la CI `gitleaks.yml` ya escanea; esto es defensa de plataforma).
- **`TRUSTED_PROXIES` prod:** poblar env con las IP/CIDR del proxy de borde (formato `config.py:28`, `"10.0.0.1,203.0.113.0/24"`). **Bloqueado por valores reales del usuario**; default vacío es seguro (rate-limit usa `client.host`).
- **(Opcional) Purga valores dev** en historial git público (filter-repo/BFG) — diferida por decisión explícita.

### Verificación abierta (entorno)

- Confirmar el **re-sync en vivo de `idx-ftse100` sin warning 404** (auto-sync de `BP.L`). Requiere **stack dev (`run-dev`)** activo + **disponibilidad del ticker en Yahoo live**. Si se confirma, puede **eliminarse `_backup_instruments_corrupt`** (red de seguridad del fix; documentada en backlog §4 y §2.4).

## 2. Verificación / batería

| Check                                                                                     | Resultado      |
| ----------------------------------------------------------------------------------------- | -------------- |
| Rebanada **manual/ops**: 4 de 5 ítems del checklist §4 (BP.L BD, logs, push, + verif env) | ✅             |
| **Ampliación código+BD** previa: fix saneo símbolos `/` + limpieza BD (CERRADA)           | ✅             |
| BD: 0 `/` · 9 yahoo_symbols limpios · `idx-ftse100`=(100) sin slash · backup conservado   | ✅             |
| Batería de código de la ampliación (cierre previo): ruff 0 · mypy 0 · pytest 35 passed    | ✅             |
| Pushes: `main == origin/main == 7363ec6`, working tree limpio                             | ✅             |
| Update-last backlog (push + verif entorno + cierre Ops) committed                         | ✅             |
| Lints (docs md)                                                                           | no aplica (md) |

## 3. Qué NO tocar (freeze) — sin cambios respecto al relevo Ops previo

- Motor money / ledger / `ExecuteTrade` internals · `order_intent.py` (fase dedicada con auditoría de call-sites).
- Belief / gobernanza IA · `contract:gen` salvo fase pactada · Track B B1–B12 (cerrado) · `pending-delete` (E8 N) · no `regen_full`.
- Fase 0 Decision Spine (F0.5/F0.6/D2/Esc.3/D1) · Cierre deuda confirm SEMI · **D3**: todas CERRADAS, no reabrir.
- **Aviso Ops:** la tabla `_backup_instruments_corrupt` en `bolsa_v1` es **red de seguridad** (no es código de repo); puede eliminarse cuando se confirme que el re-sync vivo de `BP.L` ya no genera warning 404.

## 4. Tarea del siguiente chat (fase nueva — SIN aprobar)

**PASO 0 (obligatorio, sin código):** el propietario decide qué fase sigue. El agente solo presenta opciones ancladas al backlog y espera decisión. NO abrir código antes.

Candidatas registradas (backlog §0 + PROJECT_STATE §3 + DEUDA §4):

- **Ops residual (manual, sin código, bloqueado por valores del propietario):** los 2 pendientes del checklist §4 (secret scanning UI · `TRUSTED_PROXIES` prod) + confirmar re-sync vivo `idx-ftse100` sin 404 (entorno; si se confirma → eliminar `_backup_instruments_corrupt`).
- **Unificación Research→Radar** (`plan-unificacion-research-radar-2026-08-21.md`, DRAFT/APARCADO — requiere decisión; enlaza con D3: Lab/Radar universo laboratorio).
- **F-IND-1 residual** (causalidad indicadores chikou/fractals en research; NOTA en F2).
- **Limpieza residuos históricos dev** (`m7-win-*`, `M2 *`).
- **F9/V2** (requiere ADR + diseño + decisión explícita del propietario).

**Después (con fase aprobada):** rebanada acotada, path:line verificado, batería, verificador read-only (alcance disjunto), aprobación del propietario antes de commit.

## 5. Texto de arranque (pegar en el chat nuevo)

```
CONTEXTO: Ops (deuda operativa FUERA de repo) CERRADA en su parte ejecutable 2026-08-24.
HEAD = 7363ec6, main == origin/main == 7363ec6, working tree limpio, TODO PUSHEADO.
La ampliación código+BD del hallazgo Ops previo quedó CERRADA: fix saneo símbolos '/' en
import/índices (import_instrument.py normalize_yahoo_symbol/normalize_symbol + _symbol_parts
provider FTSE100) para evitar el 404 recurrente del auto-sync BP.L; limpieza BD (0 '/' ,
idx-ftse100=100 limpias, backup _backup_instruments_corrupt). Verificación entorno read-only 2026-08-24:
0 '/' en instruments · 9 yahoo_symbols limpios (BP.L/BTA.L/BA.L/AV.L/JD.L/NG.L/RR.L/SN.L/UU.L) ·
idx-ftse100=(100) sin slash · backup conservado. Batería código de la ampliación: ruff 0 · mypy 0 ·
pytest 35 · verificador read-only APROBADO. Logs purgados (4811 archivos, solo .gitkeep).
LEE (read-first, obligatorio): backlog §0 + PROJECT_STATE §3 + PROJECT_PREMISES ⭐§0.

IDENTIDAD: QROS (Lab) + Investment OS (mesa) + Decision Spine. No reconstruir.

TAREA: PRIMERO -> el propietario decide QUÉ FASE SIGUE (E1). Candidatas: ops residual (secret
scanning UI, TRUSTED_PROXIES prod, confirmar re-sync vivo idx-ftse100 sin 404 -> si se confirma
eliminar _backup_instruments_corrupt — manual/sin código, bloqueado por credenciales/IPs del propietario);
Unificación Research->Radar (DRAFT/APARCADO, requiere decisión); F-IND-1 residual (causalidad
indicadores); limpieza residuos dev (m7-win-*, M2 *); F9/V2 (ADR+decisión).
NO lanzo agentes ni código hasta aprobar la fase y su alcance.
DESPUÉS -> rebanada acotada, path:line verificado, batería, verificador read-only (alcance disjunto),
aprobación del propietario antes de commit.

NO TOCAR: money/ledger/ExecuteTrade internals, gobernanza IA, contract:gen salvo fase pactada,
Track B B1-B12 (cerrado), pending-delete (E8 N), regen_full sin decisión,
order_intent.py (mapping default exit/reduce->sell, fase dedicada con auditoría de call-sites).
NO REABRIR: Fase 0 Decision Spine (F0.5/F0.6/F0.6-UI/D2/Escalón 3/D1) ni Cierre deuda confirm SEMI.
Aviso Ops: `_backup_instruments_corrupt` (BD bolsa_v1) = red de seguridad del fix BP.L; puede
eliminarse al confirmar que el re-sync vivo de idx-ftse100 (auto-sync de BP.L) ya no genera warning 404.

Protocolo: subagente acotado + verificador read-only, alcance disjunto, batería,
aprobación del propietario antes de commit.
```
