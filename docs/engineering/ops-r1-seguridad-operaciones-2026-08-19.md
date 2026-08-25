# Ops R-1 — Cierre de deuda operativa/seguridad (2026-08-19)

> **Fase:** R-1 del plan de refactorización/corrección (aprobado 2026-08-19).
> **Naturaleza:** 100% operativa/manual — **sin cambios de código en el repositorio**.
> **Rama de referencia:** `main` = `d16c5ff` (tras sincronización `stage → main`).
> **Criterio de cierre:** todos los ítems son acciones manuales de GitHub UI / entorno / BD, verificables por checklist, **no** por batería de código.

---

## 1. Resumen ejecutivo

R-1 fue analizado contra el código real. **Todo lo que era código ya está hecho y verificado:**

| Ítem                      | Estado del código                     | Dónde                                              |
| ------------------------- | ------------------------------------- | -------------------------------------------------- |
| `gitleaks.yml` activo     | ✅ ya MERGED y funcionando (CI verde) | `.github/workflows/gitleaks.yml`                   |
| Setting `TRUSTED_PROXIES` | ✅ ya implementado en código          | `config.py:28` → `trusted_proxies` (default vacío) |

Por tanto, R-1 **no requiere subagente de código ni batería**. Lo que queda son **acciones manuales de entorno** que se registran aquí como checklist reproducible.

---

## 2. Checklist operativo (acciones manuales pendientes)

### 2.1 GitHub Secret Scanning nativo — ✅ HABILITADO 2026-08-24 (ops propietario)

- **Qué:** secret scanning + push protection en el repositorio `jvelasca/Bolsa_V1` (público).
- **Estado verificado (GET `gh api repos/jvelasca/Bolsa_V1`):**
  - `secret_scanning` → **enabled**
  - `secret_scanning_push_protection` → **enabled**
- **Cómo se habilitó:** `PATCH repos/jvelasca/Bolsa_V1` con `security_and_analysis[secret_scanning][status]=enabled` y `[secret_scanning_push_protection][status]=enabled`. Los endpoints `PUT` dedicados devolvían **404**; el PATCH del repo sí funcionó con permisos admin.
- **Verificación UI (propietario):** `Settings → Code security and analysis` → confirmar ambos en **Enabled**. URL directa: `https://github.com/jvelasca/Bolsa_V1/settings/security_analysis`.
- **Defensa adicional:** workflow `gitleaks.yml` (push a `main/master/stage/**` + PR) sigue activo en CI.

### 2.2 Definir `TRUSTED_PROXIES` en producción (entorno)

- **Qué:** poblar la variable de entorno `TRUSTED_PROXIES` en el entorno de **producción** con las **IPs exactas** del peer inmediato (reverse proxy / load balancer). El matcher actual es igualdad de string — **no CIDR**.
- **Motivo:** `get_client_ip()` en `middleware/rate_limit.py` (F-SEG-3) solo confía en la primera IP de `X-Forwarded-For` **si el peer inmediato está en `TRUSTED_PROXIES`**; default vacío → en local/CI sin proxy usa `client.host`. Es **anti-spoofing** del rate-limit.
- **Bloqueado por:** necesitas el valor real (IPs del proxy de borde). Este doc no puede completarlo sin esos datos.
- **Runbook detallado (E1.3):** [`ops-trusted-proxies-prod-runbook-2026-08-24.md`](./ops-trusted-proxies-prod-runbook-2026-08-24.md).
- **Formato** (coma-separado): `TRUSTED_PROXIES="10.0.0.1,203.0.113.50"` (RFC 5737 ilustrativo — **no commitear valores reales**).
- **Verificación:** tras desplegar con el valor, confirmar que el rate-limit cuenta contra la IP del cliente, no la del proxy.

### 2.3 Limpieza de `logs/dev/*` — ✅ HECHO 2026-08-24

- **Qué:** purgar los logs de desarrollo locales de tu **máquina** (no del repo).
- **Aclaración importante:** `.gitignore:8-9` ignora `logs/**` (salvo `logs/**/.gitkeep`), por lo que **el working tree del repo está vacío** y los volúmenes están solo en el entorno local de desarrollo.
- **Ejecutado 2026-08-24:** purgados **4811 archivos / 8.88 MB** bajo `logs/` (subcarpetas `dev`·`api`·`agent`·`startup`·`tests` + `.txt` en raíz `dev-repro.txt`/`dev-verify-fix.txt`/`tc.txt`), excluyendo `.gitkeep`.
- **Verificación:** `git status` limpio (0 cambios, todo gitignored) + solo `.gitkeep` restantes en cada subcarpeta.
- **Riesgo:** nulo (logs/sesiones dev descartables).

### 2.4 Corrección manual del registro `BP/.L → BP.L` en la BD local — ✅ HECHO 2026-08-24

- **Alcance real (verificado, más amplio que el doc original):** no era solo `BP/.L`, sino **9 instrumentos LSE** con patrón de slash en `symbol` y `yahoo_symbol`: `BP/.L`·`BA/.L`·`AV/.L`·`RR/.L`·`SN/.L`·`JD/.L`·`NG/.L`·`UU/.L`·`BT/A.L` (→ `BTA.L`).
- **Ejecutado en `bolsa_v1` (docker `bolsa-postgres`, user `bolsa`):**
  ```sql
  UPDATE instruments
  SET symbol = replace(symbol,'/',''), yahoo_symbol = replace(yahoo_symbol,'/',''),
      updated_at = CURRENT_TIMESTAMP
  WHERE symbol LIKE '%/%' OR yahoo_symbol LIKE '%/%';
  ```
  `UPDATE 9`. Backup previo en tabla `_backup_instruments_corrupt` (9 filas).
- **Verificado:** 0 filas con `/` restantes · sin duplicados en `UNIQUE(symbol,exchange)` ni `UNIQUE(yahoo_symbol)` · 0 referencias denormalizadas (`symbol` en decision_sessions/strategy_tops/optimization_runs/pending_orders/price_alerts/signal_alert_subscriptions) con los valores con slash · FKs a `id` intactas (ON UPDATE CASCADE, no se tocó `id`).
- **Verificación funcional:** re-ejecutar auto-sync de `BP.L` y confirmar que ya no aparece el warning `BP/.L` (Yahoo 404).

### 2.5 (Opcional) Purga de valores dev en historial git público

- **Qué:** los valores dev históricos `bolsa:bolsa_dev` / `bolsa-dev-secret` existen en el historial público (auditado en F-SEG-2). Como son **valores de desarrollo**, no es urgente.
- **Si se decide purgar:** filter-repo / BFG (reescribe historial — **requiere CI coordinada y decisión explícita**, fuera de esta fase).
- **Estado:** pendiente de decisión, no bloqueante.

---

## 3. Decisiones cerradas en R-1

- **No crear código**: R-1 no introduce cambios de código ni config en el repo.
- **gitignore logs ya correcto**: `logs/**` ignorado; nada que añadir.
- **Fase R-1 NO requiere batería de código** (0 cambios de código). La verificación es el checklist manual de §2.

---

## 4. Relevo / texto de paso

> CONTEXTO: Ops propietario **CERRADA** (2026-08-24). Secret scanning + push protection **enabled** vía API. Runbook `TRUSTED_PROXIES`: `ops-trusted-proxies-prod-runbook-2026-08-24.md`. **Pendiente del propietario:** (b) valor real `TRUSTED_PROXIES` en prod cuando exista despliegue con proxy · (e) purga opcional historial git. Relevo: `traspaso-relevo-ops-propietario-cierre-ciclo-2026-08-24.md`.
