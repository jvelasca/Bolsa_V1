# Runbook — `TRUSTED_PROXIES` en producción (2026-08-24; E1.3 2026-08-25)

> **Alcance:** variable de entorno del API Python (F-SEG-3). **Sin valores reales en repo** — el propietario debe aportar las IP del edge proxy.
> **Padre:** [`ops-r1-seguridad-operaciones-2026-08-19.md`](./ops-r1-seguridad-operaciones-2026-08-19.md) §2.2.
> **Estado E1.3:** código + default vacío + secret scanning = **DONE_IN_REPO**. Valor prod = **BLOCKED_ON_OWNER** (sin peer IPs reales).

---

## 1. Qué hace y por qué importa

El rate-limit identifica al cliente con `get_client_ip()` (`apps/api-python/src/bolsa_api/middleware/rate_limit.py`). Cualquier cliente puede enviar un header `X-Forwarded-For` falso; por eso **solo se confía en la primera IP de XFF cuando el peer inmediato** (`request.client.host`) **está en la lista de proxies de confianza**.

| Escenario                          | Comportamiento                                                                                                                                                       |
| ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `TRUSTED_PROXIES` vacío (default)  | Se ignora XFF → rate-limit usa `client.host`. **Seguro** en dev/local/CI sin reverse proxy. Un atacante externo **no** puede resetear su contador fingiendo otra IP. |
| Peer inmediato ∈ `TRUSTED_PROXIES` | Se usa la **primera** IP de `X-Forwarded-For` (cliente original tras la cadena de proxies).                                                                          |
| Peer de confianza sin XFF          | Cae a `client.host` (p. ej. acceso directo al API detrás del LB).                                                                                                    |

Setting en código: `packages/py/infrastructure/src/bolsa_infrastructure/config.py` → `trusted_proxies: str = Field(default="", validation_alias="TRUSTED_PROXIES")`.

Cableado: `main.py` pasa `settings.trusted_proxies` a `RateLimitMiddleware`.

---

## 2. Formato de la variable — **exact-string, no CIDR**

```bash
# Una o más entradas separadas por coma (trim de espacios)
TRUSTED_PROXIES="<IP-del-proxy-1>,<IP-del-proxy-2>"
```

### Caveat crítico (código actual)

`get_client_ip()` hace **igualdad exacta de string** (`peer in set(entradas)`). **No** hay matching CIDR/`ipaddress`:

| Entrada en `TRUSTED_PROXIES` | Peer real `10.0.0.5` | ¿Confía XFF? |
| ---------------------------- | -------------------- | ------------ |
| `10.0.0.5`                   | `10.0.0.5`           | Sí           |
| `10.0.0.0/8`                 | `10.0.0.5`           | **No**       |
| `203.0.113.1`                | `10.0.0.5`           | No           |

- Listar **cada IP concreta** del peer inmediato que ve el proceso API (puede haber varias si hay varios nodos LB).
- **No** incluir la IP del cliente final — solo la(s) del reverse proxy / load balancer / ingress que habla con el API.
- **No** commitear valores reales en `.env`, `.env.example`, docker-compose del repo ni docs.
- Docs antiguos que mencionan `CIDR` / `203.0.113.0/24` son **ilustrativos erróneos** respecto al matcher actual: usar solo IPs host exactas hasta que exista matching de red en código.

Ejemplo ilustrativo (RFC 5737, **no usar en prod**): `TRUSTED_PROXIES="203.0.113.1,198.51.100.10"`.

---

## 3. Dónde configurarlo en prod

Bolsa V1 **no tiene** un servicio API en `docker-compose.yml` de prod (solo Postgres local). En el despliegue real del propietario, definir `TRUSTED_PROXIES` en el **mismo sitio que el resto de env del API Python**:

| Plataforma típica        | Dónde                                                                     |
| ------------------------ | ------------------------------------------------------------------------- |
| systemd / unit file      | `Environment=TRUSTED_PROXIES=...` o `EnvironmentFile=/etc/bolsa/api.env`  |
| Docker / Compose prod    | `environment:` o `env_file:` del contenedor `api-python` (no el repo dev) |
| Kubernetes               | `Secret` / `ConfigMap` del Deployment del API                             |
| PaaS (Fly, Render, etc.) | Variables de entorno del servicio API en el panel                         |

Reiniciar el proceso API tras cambiar la variable.

### Dev / local / compose del repo

**Dejar `TRUSTED_PROXIES` vacío** (omitir la variable). No hay reverse proxy delante del API en el stack local documentado; poblarla sin peer real solo añade riesgo de confiar XFF spoofed. Default vacío = correcto.

---

## 4. Cómo descubrir la IP del peer (guías por setup)

Objetivo: la IP que el proceso API ve en `request.client.host` (peer TCP inmediato), **no** la IP pública del usuario.

| Setup                              | Cómo obtener el peer                                                                                                                                                                                                   |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **nginx** (proxy_pass al API)      | En el host del API: `ss -tn` / logs uvicorn del peer; o `proxy_set_header` + log `$remote_addr` en nginx hacia el upstream. Suele ser la IP del contenedor/host nginx en la red privada.                               |
| **Caddy**                          | Igual: IP del contenedor/host Caddy en la red hacia el API (`docker network inspect`, `ip addr` en el proxy).                                                                                                          |
| **Cloudflare** (CDN delante)       | El peer del API **no** es la IP del visitante: es el origin-facing proxy (nginx/Caddy/LB propio) **o** el rango del proveedor cloud si Cloudflare → origin directo. Listar la IP del hop que termina TLS hacia el API. |
| **Docker Compose** (proxy + API)   | `docker inspect <proxy>` → IP en la bridge network compartida con el API; esa es la que suele aparecer como `client.host`.                                                                                             |
| **Cloud LB** (AWS ALB, GCP, Azure) | IP privada del ENI/backend connection; a menudo dinámica → listar todas las IPs actuales del LB hacia el target, o fijar un hop fijo (sidecar) con IP estable.                                                         |

Verificación rápida en prod (sin meter IPs en el repo): con logging temporal del peer, o un endpoint interno de diagnóstico solo en red privada que imprima `request.client.host` (no exponer públicamente).

---

## 5. Checklist — DONE vs OWNER (verdad 2026-08-25)

| Ítem                                                             | Columna   | Estado                                                                 |
| ---------------------------------------------------------------- | --------- | ---------------------------------------------------------------------- |
| Código `trusted_proxies` + `get_client_ip` + tests rate-limit    | **DONE**  | ✅ En repo (`config.py`, `rate_limit.py`, `test_rate_limit.py`)        |
| Default vacío (anti-spoofing sin proxy)                          | **DONE**  | ✅ Seguro en dev/local/CI                                              |
| Secret scanning + push protection (GitHub)                       | **DONE**  | ✅ Enabled 2026-08-24                                                  |
| Runbook + caveat exact-string (este doc)                         | **DONE**  | ✅ E1.3                                                                |
| Valor real `TRUSTED_PROXIES` en env **prod**                     | **OWNER** | ⏳ Bloqueado — sin IPs peer reales aportadas                           |
| Confirmar edge inyecta `X-Forwarded-For`                         | **OWNER** | ⏳ Tras tener proxy delante del API                                    |
| Verificar rate-limit cuenta por IP cliente (no por IP del proxy) | **OWNER** | ⏳ Smoke post-config (429 coherente / logs)                            |
| Poblar `TRUSTED_PROXIES` en `.env` / compose **local del repo**  | **DONE**  | ✅ No hacerlo — vacío correcto; no hay valor en compose/`.env.example` |

### Acciones OWNER (orden)

1. Obtener la(s) IP **exactas** del peer inmediato (§4) — no CIDR.
2. Configurar `TRUSTED_PROXIES` solo en el entorno prod del API (§3).
3. Confirmar que el edge proxy inyecta `X-Forwarded-For`.
4. Smoke rate-limit desde un cliente externo (contador por IP cliente).

---

## 6. Estado resumen (E1.3)

| Ítem            | Estado                                                                   |
| --------------- | ------------------------------------------------------------------------ |
| Código + tests  | ✅ DONE_IN_REPO                                                          |
| Default vacío   | ✅ DONE_IN_REPO                                                          |
| Docs / runbook  | ✅ DONE_IN_REPO (caveat exact-string + discovery + checklist DONE/OWNER) |
| Valor prod real | ⏳ **BLOCKED_ON_OWNER** (IPs del edge proxy; no inventar ni commitear)   |
