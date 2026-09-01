# RELEVO — Phase C3 · `TRUSTED_PROXIES` checklist (2026-09-01)

> **Alcance:** docs-only · refresh owner checklist (Opción C · deuda transversal).  
> **Padre:** [`ops-trusted-proxies-prod-runbook-2026-08-24.md`](./ops-trusted-proxies-prod-runbook-2026-08-24.md) · [`traspaso-relevo-cierre-v155-apertura-siguiente-2026-09-01.md`](./traspaso-relevo-cierre-v155-apertura-siguiente-2026-09-01.md) §5 Opción C.  
> **AsOf:** 2026-09-01.  
> **Regla:** **sin IPs prod reales en repo** · **no** commitear `.env` con valores reales.

---

## 0. Verificación código ↔ runbook (2026-09-01)

| Punto runbook                                                                                                   | Ubicación                                                              | Estado                     |
| --------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- | -------------------------- |
| Setting `trusted_proxies` default `""`, alias `TRUSTED_PROXIES`                                                 | `packages/py/infrastructure/src/bolsa_infrastructure/config.py` L34–37 | ✅ coincide                |
| `get_client_ip()`: confía XFF **solo** si `peer in set(comma-split)`; primera IP de XFF; fallback `client.host` | `apps/api-python/src/bolsa_api/middleware/rate_limit.py` L213–248      | ✅ coincide                |
| Cableado `settings.trusted_proxies` → `RateLimitMiddleware`                                                     | `apps/api-python/src/bolsa_api/main.py` L147–153                       | ✅ coincide                |
| Tests anti-spoofing + trusted peer + comma-separated                                                            | `apps/api-python/tests/test_rate_limit.py` L81–112                     | ✅ en repo                 |
| Matcher **exact-string** (no CIDR / `ipaddress`)                                                                | `rate_limit.py` L242 `peer in _split_trusted_proxies(...)`             | ✅ coincide con runbook §2 |

**Conclusión:** el runbook E1.3 sigue siendo fiel al código. **Sin cambios de código** en este slice.

---

## 1. Dev / local / compose del repo

| Check                                               | Estado                       | Notas                                                                            |
| --------------------------------------------------- | ---------------------------- | -------------------------------------------------------------------------------- |
| `docker-compose.yml` del repo                       | ✅ **vacío correcto**        | Solo Postgres (`bolsa-postgres`); **no** servicio API · **no** `TRUSTED_PROXIES` |
| `.env.example`                                      | ✅ **sin** `TRUSTED_PROXIES` | Omitir la variable en local = default vacío seguro                               |
| Poblar `TRUSTED_PROXIES` en compose/`.env` del repo | ✅ **NO hacer**              | Sin reverse proxy documentado delante del API local                              |

---

## 2. Checklist — DONE vs OWNER

| Ítem                                                             | Columna   | Estado                                                                                                       |
| ---------------------------------------------------------------- | --------- | ------------------------------------------------------------------------------------------------------------ |
| Código `trusted_proxies` + `get_client_ip` + tests rate-limit    | **DONE**  | ✅ Verificado 2026-09-01 (`config.py`, `rate_limit.py`, `test_rate_limit.py`, `main.py`)                     |
| Default vacío (anti-spoofing sin proxy)                          | **DONE**  | ✅ Seguro en dev/local/CI                                                                                    |
| Secret scanning + push protection (GitHub)                       | **DONE**  | ✅ Enabled 2026-08-24 (`5100d23`)                                                                            |
| Runbook + caveat exact-string                                    | **DONE**  | ✅ [`ops-trusted-proxies-prod-runbook-2026-08-24.md`](./ops-trusted-proxies-prod-runbook-2026-08-24.md) E1.3 |
| Compose local del repo sin `TRUSTED_PROXIES`                     | **DONE**  | ✅ Postgres-only · variable omitida                                                                          |
| `.env.example` sin valor `TRUSTED_PROXIES`                       | **DONE**  | ✅ No commitear IPs                                                                                          |
| Valor real `TRUSTED_PROXIES` en env **prod**                     | **OWNER** | ⏳ **BLOCKED_ON_OWNER** — IPs peer exactas del edge proxy (propietario)                                      |
| Confirmar edge inyecta `X-Forwarded-For`                         | **OWNER** | ⏳ Tras despliegue con proxy delante del API                                                                 |
| Verificar rate-limit cuenta por IP cliente (no por IP del proxy) | **OWNER** | ⏳ Smoke post-config (429 coherente / logs)                                                                  |
| Confirmación UI secret scanning (opcional)                       | **OWNER** | ⏳ Ver [`monitor-purge-ops-checklist-2026-08-24.md`](./monitor-purge-ops-checklist-2026-08-24.md) §3.1       |

---

## 3. Acciones OWNER (orden)

1. Obtener la(s) IP **exactas** del peer inmediato (`request.client.host`) — runbook §4; **no CIDR**.
2. Configurar `TRUSTED_PROXIES` solo en el entorno prod del API (runbook §3) — **fuera del repo**.
3. Confirmar que el edge proxy inyecta `X-Forwarded-For` con el cliente original como primera entrada.
4. Smoke rate-limit desde un cliente externo: contador por IP cliente, no por IP del proxy.

Formato (ilustrativo RFC 5737 — **no usar en prod**):

```bash
TRUSTED_PROXIES="<IP-exacta-proxy-1>,<IP-exacta-proxy-2>"
```

---

## 4. Resumen ejecutivo

| Bloque               | Estado                                                                           |
| -------------------- | -------------------------------------------------------------------------------- |
| **DONE_IN_REPO**     | Código · tests · default vacío · runbook · compose local vacío · secret scanning |
| **BLOCKED_ON_OWNER** | Valor prod real · confirmación XFF edge · smoke rate-limit post-deploy           |

Phase C3 **cierra en docs**; el desbloqueo prod requiere IPs peer del propietario (no inventar ni commitear).
