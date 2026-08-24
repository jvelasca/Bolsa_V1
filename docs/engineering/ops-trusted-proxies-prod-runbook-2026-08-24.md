# Runbook — `TRUSTED_PROXIES` en producción (2026-08-24)

> **Alcance:** variable de entorno del API Python (F-SEG-3). **Sin valores reales en repo** — el propietario debe aportar las IP/CIDR del edge proxy.
> **Padre:** [`ops-r1-seguridad-operaciones-2026-08-19.md`](./ops-r1-seguridad-operaciones-2026-08-19.md) §2.2.

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

## 2. Formato de la variable

```bash
# Una o más entradas separadas por coma (sin espacios obligatorios; se hace trim)
TRUSTED_PROXIES="<IP-o-CIDR-del-proxy-1>,<IP-o-CIDR-del-proxy-2>"
```

- Acepta **IP host** (`203.0.113.50`) o **CIDR** si el despliegue lo requiere.
- **No** incluir la IP del cliente final — solo la(s) del reverse proxy / load balancer / ingress que termina TLS y reenvía al API.
- **No** commitear valores reales en `.env`, `.env.example`, docker-compose del repo ni docs.

Ejemplo ilustrativo (RFC 5737, **no usar en prod**): `TRUSTED_PROXIES="203.0.113.1,10.0.0.0/8"`.

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

---

## 4. Checklist del propietario

1. [ ] Obtener la IP (o rango CIDR) **del peer inmediato** que ve el API — suele ser el internal IP del LB/ingress, no la IP pública del cliente.
2. [ ] Configurar `TRUSTED_PROXIES` en el entorno prod del API (§3).
3. [ ] Confirmar que el edge proxy **inyecta** `X-Forwarded-For` con la IP del cliente (estándar en nginx, Traefik, Caddy, cloud LB).
4. [ ] Verificar rate-limit: desde un cliente externo, dos peticiones rápidas al mismo endpoint limitado deben contar contra **la IP del cliente**, no la del proxy (p. ej. observar 429 coherente; logs si están disponibles).
5. [ ] **No** poblar `TRUSTED_PROXIES` en dev local salvo que haya un reverse proxy real delante — default vacío es correcto.

---

## 5. Estado (2026-08-24)

| Ítem            | Estado                                                       |
| --------------- | ------------------------------------------------------------ |
| Código + tests  | ✅ (`config.py:28`, `get_client_ip`, `test_rate_limit.py`)   |
| Valor prod real | ⏳ **BLOQUEADO en el propietario** (IPs/CIDR del edge proxy) |
| Default vacío   | ✅ Seguro hasta que exista despliegue prod con proxy         |
