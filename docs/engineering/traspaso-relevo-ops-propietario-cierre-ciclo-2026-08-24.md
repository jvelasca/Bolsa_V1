# RELEVO — Ops propietario CERRADA → decisión de ciclo / idle

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (Product / Ops).
> **Propósito:** cierre del ciclo **U6 → DS-05 → ops propietario**. **Siguiente = decisión del propietario** (idle / nueva fase); no se inventa fase aquí.
> **AsOf:** 2026-08-24 · HEAD `15e86a4` (DS-05). Secuencia: U6 `9e9a346` → spine residual DS-05 `15e86a4` → **ops propietario (este slice, docs-only)**.
> **Protocolo:** docs-only · **sin commit** en este slice (coordinador).

---

## 1. Qué se hizo (ops propietario)

| Ítem                   | Resultado                                                                                         |
| ---------------------- | ------------------------------------------------------------------------------------------------- |
| GitHub secret scanning | **HABILITADO** vía API (`gh api PATCH repos/jvelasca/Bolsa_V1`) — ver §2                          |
| GitHub push protection | **HABILITADO** (mismo PATCH)                                                                      |
| CI `gitleaks.yml`      | ✅ Presente (`.github/workflows/gitleaks.yml`, push `main`/`stage/**` + PR, `gitleaks-action@v3`) |
| `TRUSTED_PROXIES` prod | Runbook entregado · **valor real pendiente del propietario**                                      |
| Código                 | **0 cambios** (config ya en repo desde F-SEG-3)                                                   |

**Docs (update-last):** backlog §0 · §4 · `CURRENT_SYSTEM.md` · `PROJECT_STATE.md` · [`ops-trusted-proxies-prod-runbook-2026-08-24.md`](./ops-trusted-proxies-prod-runbook-2026-08-24.md) · este relevo.

---

## 2. Secret scanning — verificación API (2026-08-24)

**Repo:** `jvelasca/Bolsa_V1` · **visibility:** public.

| Flag                                    | Estado inicial (GET) | Estado final (GET post-intento) |
| --------------------------------------- | -------------------- | ------------------------------- |
| `secret_scanning`                       | disabled             | **enabled**                     |
| `secret_scanning_push_protection`       | disabled             | **enabled**                     |
| `secret_scanning_validity_checks`       | disabled             | disabled (opcional)             |
| `secret_scanning_non_provider_patterns` | disabled             | disabled (opcional)             |
| `dependabot_security_updates`           | disabled             | disabled (fuera de alcance)     |

**Intentos API:**

- `PUT .../secret-scanning/alerts` → **404** (endpoint no disponible).
- `PATCH repos/jvelasca/Bolsa_V1` con `security_and_analysis[secret_scanning][status]=enabled` → **200**, habilitó scanning.
- `PATCH` con `security_and_analysis[secret_scanning_push_protection][status]=enabled` → **200**, habilitó push protection.

**Verificación UI recomendada al propietario:** `https://github.com/jvelasca/Bolsa_V1/settings/security_analysis` → confirmar **Secret scanning** y **Push protection** en Enabled.

**Defensa en profundidad:** CI `gitleaks.yml` sigue activa aunque GitHub nativo esté on.

---

## 3. `TRUSTED_PROXIES` — checklist propietario

Runbook: [`ops-trusted-proxies-prod-runbook-2026-08-24.md`](./ops-trusted-proxies-prod-runbook-2026-08-24.md).

Resumen:

1. Formato: `TRUSTED_PROXIES="ip1,cidr2"` (coma-separado).
2. Dónde: env del proceso API Python en prod (systemd / contenedor / PaaS) — **no** en repo.
3. Default vacío: **seguro** (anti-spoofing; rate-limit usa `client.host`).
4. **Bloqueado:** el propietario debe aportar IP/CIDR reales del edge proxy.

---

## 4. Checklist §4 backlog — estado tras este slice

| Ítem                                     | Estado                                        |
| ---------------------------------------- | --------------------------------------------- |
| GitHub secret scanning + push protection | ✅ **enabled** (API 2026-08-24; verificar UI) |
| `TRUSTED_PROXIES` prod                   | ⏳ **BLOQUEADO propietario** (runbook listo)  |
| BP/.L · logs/dev · re-sync FTSE100       | ✅ Cerrados en ops residual previo            |
| Purga historial git dev (opcional)       | ⏳ Decisión explícita pendiente               |

---

## 5. Ciclo cerrado

```
U6 (9e9a346) → DS-05 (15e86a4) → ops propietario (checklist + runbook)
```

**Freeze intacto:** sin OrderProposal · `PAPER_D_EXECUTE` off · Lab fuera spine · sin Belief · sin `contract:gen`.

---

## 6. Siguiente

**Decisión de ciclo / idle.** El propietario elige si abre nueva fase (p. ej. Unificación Research→Radar · F-IND-1 residual · higiene dev · mandate DS-03) o mantiene idle. **No hay fase técnica obligatoria pendiente** del ciclo U6→DS-05→ops salvo `TRUSTED_PROXIES` cuando exista despliegue prod con proxy.

---

## 7. Texto de arranque (pegar en chat nuevo)

```
CONTEXTO: Ciclo U6→DS-05→ops propietario CERRADO (HEAD 15e86a4 + docs ops).
Secret scanning + push protection ENABLED (API 2026-08-24). gitleaks.yml OK.
TRUSTED_PROXIES prod: runbook listo; valor real pendiente del propietario.
Freeze: sin OrderProposal · PAPER_D_EXECUTE off · Lab fuera spine · no contract:gen.
SIGUIENTE: decisión de ciclo / idle (propietario).
Read-first: backlog §0 · CURRENT_SYSTEM · PROJECT_STATE · traspaso-relevo-ops-propietario-cierre-ciclo-2026-08-24.md.
```
