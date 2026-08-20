# RELEVO / TRASPASO — R-9: cierre F1–F4 → apertura F5 (2026-08-20)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (`Product / Ops`).
> **Propósito:** texto de paso oficial para el **NUEVO AGENTE / NUEVO CHAT** que debe continuar la refactorización R-9 (abriendo la siguiente fase **F5**). Es el ancla anti-saturación / anti-alucinación de relevo: cualquier agente nuevo **LEE ESTE DOC + `backlog-trabajo-2026-08-20.md` §0/§1 ANTES de tocar nada**.
> **Estado al redactar (verificado):** `local main = origin/main = 0800ee9` · working tree limpio · F1–F4 de R-9 cerradas y pusheadas.
> **AsOf:** 2026-08-20 (≈22:30).

---

## 1. Estado verificado (firma — no adivinar)

- **HEAD/rama:** `main` == `origin/main` == `0800ee9`. Árbol limpio (`git status --short` vacío).
- **Últimos commits (`main`, de más nuevo a más antiguo):**

  | Commit    | Contenido                                                  |
  | --------- | ---------------------------------------------------------- |
  | `0800ee9` | docs: cerrar R-9 F4 (plan + backlog)                       |
  | `b384f31` | F4 — DTOs financieros estrictos (Pydantic fail-fast 422)   |
  | `fbfefc7` | docs: cerrar R-9 F3 (plan + backlog)                       |
  | `26f5ca1` | F3 — carrera de custodia idempotente (no 500)              |
  | `2823eae` | docs: cerrar R-9 F2 (plan + backlog)                       |
  | `31954dd` | F2 — 409 ante idempotency_key con payload distinto         |
  | `29f444f` | docs: premisas E1–E9 + plan R-9 + cierre F1                |
  | `fa070ec` | F1 — idempotencia deposit/withdraw aislada por cuenta+type |

- **R-9 F1–F4 COMPLETAS** en `main` (ver §6 para detalle de cada una). La **fase en curso/corta a abrir es F5**.
- Antecedentes cerrados que ya viejos en `main` (no afectan a F5): R-7 y R-8 completas (R-8 = hasta `fb95b27`, tip previo `681a46c`).

---

## 2. PROTOCOLO OBLIGATORIO del nuevo agente (las 3 reglas que no se negocian) — VIGENTE

Estas reglas siguen siendo las mismas que en el relevo R-8 (premisas **E1–E9** en `docs/PROJECT_PREMISES.md` ⭐§0):

1. **Read-first anti-alucinación:** antes de abrir CUALQUIER fase/subagente, **LEE** `docs/engineering/backlog-trabajo-2026-08-20.md` **§0 y §1**, `docs/engineering/plan-r9-refactor-hardening-2026-08-20.md` (§ de la fase a abrir) y `docs/engineering/PROJECT_STATE.md`. Si el repo no coincide con el backlog/plan → **PARAR y re-leer**; nunca seguir por inercia.
2. **Una fase = un subagente acotado + verificación del coordinador + batería real + aprobación de usuario POR COMMIT + push a `main` (rama protegida, requiere aprobación nativa).** El coordinador **nunca** se fía del reporte de un subagente: contrasta cada diff contra el código real y corre la batería él mismo. Máx. ~3 subagentes en paralelo por chat, con alcances disjuntos.
3. **Anti-alucinación / anti-pérdida:** todo hallazgo del subagente se verifica en el código (file:line). El coordinador inyecta en el brief el **mapa de consumidores ya verificado** para que el subagente no redis cubra call-sites. **Vigilar la saturación del hilo principal:** hacer read-first acotado (greps + bloques, no leer archivos enteros), y si se degrada el contexto, hacer un relevo al cierre de la fase.

### Batería mínima (re-verificada por el coordinador en cada fase)

- **Backend (py):** `uv run ruff check packages/py apps/api-python --config pyproject.toml` → 0 · mypy de los ficheros en gate CI (`uv run mypy <files> --config-file pyproject.toml`, usando `*> archivo.txt` + leer para Powershell) · pytest de la zona.
- **Git:** `git status` acotado a los ficheros declarados por la fase.
- **Frontend/shared/contract:** solo si la fase toca web/shared/OpenAPI (F1–F4 no tocaron); las fases F4+ ya marcaron el contrato con una decisión pendiente (ver §3.2).

---

## 3. TRABAJO PENDIENTE A CERRAR (nuevo agente)

### 3.1 ▶️ FASE 5 — R-9.5: Sesión con **epoch** en vez de `monotonic()` (`time.time()`) — la siguiente

> **Dentro del plan director** (ver `plan-r9-refactor-hardening-2026-08-20.md` § FASE 5). Es la fase **corta y de menor riesgo** de las que siguen.

- **Problema (auditoría):** `apps/api-python/src/bolsa_api/auth/session.py` usa `time.monotonic()` para el deadline de la cookie de sesión → **no portable multi-host** (en un cluster, otro host con distinto timer monotónico invalidaría/confundiría expiraciones).
- **Verificado (file:line):**
  - `session_deadline(settings)` `session.py:35-38`: `return int(time.monotonic()) + settings.app_auth_ttl_seconds`.
  - `verify_session_cookie(...)` `session.py:50-70`: compara `if time.monotonic() >= exp` (`:67`); valida formato, firma HMAC (`hmac.new` + `secrets.compare_digest`, `:44-46`, `:62-65`) y token.
  - Cookie: `Secure` solo en producción (dev `Secure=False` para localhost HTTP) (`:17-19`, `:72-73`), `SameSite`, TTL (`app_auth_ttl_seconds`).
  - Docstring del módulo (`:5-19`) explica `exp.token.sig`.
- **Corrección (decisión del plan, aún por confirmar con el usuario en el turno nuevo):** cambiar `exp` a **Unix epoch UTC** (`time.time()`), manteniendo HMAC y `Secure`/`SameSite`/TTL. La revocación real (logout que invalida sesión copiada via `session_id`+Redis+`session_version`) es **OPCIONAL** (decisión §5.2 del plan) — para app personal local el cambio a epoch es suficiente y de menor riesgo.
- **Criterio de aceptación (del plan):** login→cookie válida TTL; logout borra cookie; con epoch la cookie es portable; tests auth existentes (10 en `apps/api-python/tests/test_auth.py`) verdes.
- **Alcance propuesto (acotado):** `apps/api-python/src/bolsa_api/auth/session.py` (+ opcionalmente un test nuevo para portabilidad/expiración con epoch). NO migración, no contrato, no web.
- **Riesgo/aviso:** el cambio `monotonic`→epoch es mecánico; pero **no** tocar la revocación real salvo decisión explícita del usuario (mayor alcance). Comprobar que ningún test depende de un valor monotónico concreto; los tokens `exp` en cookies ya emitidas bajo `monotonic()` quedarán inválidos tras el cambio (aceptable en no-producción).

### 3.2 🟡 Ítems de decisión de usuario (NO auto-cerrar — presentar y esperar)

| Ítem                                                                                                                                                       | Origen   | Regla vigente                                                                                         |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ----------------------------------------------------------------------------------------------------- |
| **Contrato F2/F4:** el `409 IDEMPOTENCY_KEY_REUSED` (F2, `main.py` handler) NO figura en `openapi.json`/`schema.d.ts` (no se hizo regen)                   | R-9.2    | **Pendiente decisión** si exponer el 409 en OpenAPI + `contract:check`. No se ejecutó `contract:gen`. |
| **`pending-delete/README.md` riesgo alto**                                                                                                                 | R-8D     | **NO tocar** hasta decisión de `purge storage`.                                                       |
| **R-8C.2 scheduler-vs-worker** y **M-4/T-M4** (job dedicado custodia)                                                                                      | R-7/R-8C | **Documentadas, NO tocar código** salvo decisión.                                                     |
| Fases posteriores a F5: **F6** invariante `balance_after` (garantía física, decidir) · **F7** suite concurrencia · **F8** limpieza · **F9** (V2, opcional) | R-9 plan | Una por chat, con diseño en el plan + subagente + aprobación por commit.                              |

### 3.3 🏁 Cierre por fase (obligatorio al terminar cada una)

Al cerrar cada fase: **update-last en `backlog-trabajo-2026-08-20.md`** (§0 relego + §6 historial con commits/batería) **y** `plan-r9-refactor-hardening-2026-08-20.md` (añadir el § "Estado ... IMPLEMENTADO" al pie de la fase). Commit de docs separado del commit de código, ambos con push a `main`.

---

## 4. TEXTOS DE PASO PARA EL NUEVO AGENTE (pegar directamente)

### 4.1 Brief de arranque (nuevo chat principal)

> CONTEXTO (2026-08-20, ≈22:30): repo `Bolsa_V1`, `main` = `0800ee9`, árbol limpio. **R-9 en curso: F1–F4 completas y pusheadas** (F1 `fa070ec`, F2 `31954dd`+`2823eae`, F3 `26f5ca1`+`fbfefc7`, F4 `b384f31`+`0800ee9`). El plan director está en `docs/engineering/plan-r9-refactor-hardening-2026-08-20.md` y las premisas E1–E9 en `docs/PROJECT_PREMISES.md` ⭐§0.
> **LEE PRIMERO (obligatorio):** `docs/engineering/backlog-trabajo-2026-08-20.md` §0/§1 · `docs/engineering/plan-r9-refactor-hardening-2026-08-20.md` § FASE 5 · `docs/engineering/PROJECT_STATE.md` · este doc (`traspaso-relevo-cierre-r9-f1-f4-2026-08-20.md`).
> **Tarea inmediata:** abrir **F5 (R-9.5)** — cambiar session `monotonic()`→`time.time()` (epoch UTC) en `apps/api-python/src/bolsa_api/auth/session.py`, conservando HMAC/`Secure`/`SameSite`/TTL (ver §3.1 de este doc). Protocolo: read-first acotado → decidir diseño (confirmar con el usuario si se incluye o no la revocación opcional) → documentar en el plan → lanzar **un** subagente acotado → verificación del coordinador (diff + batería real) → **aprobación del usuario por commit** → push a `main`.
> **NO tocar** (salvo decisión de usuario): regen OpenAPI/`contract:gen` (pendiente decisión F2/F4), `pending-delete` riesgo alto, scheduler/worker R-8C.2, M-4/T-M4, features nuevas, ni migraciones fuera de la fase.

### 4.2 Brief para el SUBAGENTE de FASE 5 (a lanzar cuando el usuario apruebe abrir F5)

> Fase **R-9.5** — sesión epoch. Repo `main` debería estar limpio y con la decisión de diseño ya documentada en `plan-r9-*` (aplica SIEMPRE epoch + mantener HMAC/`Secure`/`SameSite`/TTL; la revocación opcional SOLO si el plan la marca aprobada). Fichero destino único: `apps/api-python/src/bolsa_api/auth/session.py` (verificar `monotonic` en `:37` y `:67`). Cambio mecánico `time.monotonic()`→`time.time()` en `session_deadline` y en la comparación de `verify_session_cookie`; actualizar el docstring del módulo que menciona "monotónico". NO cambiar la estructura `exp.token.sig` ni HMAC ni flags de cookie. Tests: `apps/api-python/tests/test_auth.py` (10) deben seguir verdes; añade un test que compruebe que una cookie con exp en epoch pasada ya no es válida y que con exp futura sí (portabilidad/expiración), sin depender de un timer concreto. Battery: ruff 0 · mypy de `session.py` 0 · pytest `test_auth.py` verde. Alcance SOLO `session.py` + (opcional) un `test_*.py`. NO migración/contrato/web/docs. Devuelve file:line antes→después y el resultado de la batería. **NO commits ni push.**

### 4.3 Brief para cierres siguientes (F6–F9)

> Para F6+ re-lee el plan (`plan-r9-refactor-hardening-2026-08-20.md`) y aplica el mismo protocolo: una fase = un subagente acotado + verificación del coordinador + aprobación por commit + push. **F6** (`balance_after` invariante físico) requiere **decisión de diseño** previa del usuario (es la fase de mayor complejidad de las que quedan). Documentar siempre en el plan y el backlog.

---

## 5. Enlaces (fuentes de verdad — no inventar estado)

- Backlog (LEER PRIMERO): `docs/engineering/backlog-trabajo-2026-08-20.md` (§0/§1 · §4 checklist · §6 historial)
- Plan de la R-9: `docs/engineering/plan-r9-refactor-hardening-2026-08-20.md`
- Premisas E1–E9: `docs/PROJECT_PREMISES.md` (⭐§0)
- Estado vivo: `docs/engineering/PROJECT_STATE.md`
- Auth/session a refactorizar: `apps/api-python/src/bolsa_api/auth/session.py`
- Índice / registro: `docs/engineering/engineering-index-2026-08-03.md` §5
- Relevo R-8 previo: `docs/engineering/traspaso-relevo-cierre-r8-auditoria-versiones-2026-08-20.md`

---

## 6. Cierres de la R-9 registrados hasta este relevo

| Fecha         | Hito                                                    | Commits `main`              |
| ------------- | ------------------------------------------------------- | --------------------------- |
| 2026-08-20    | **F1** idempotencia por cuenta+type (R-9.1)             | `fa070ec` (+docs `29f444f`) |
| 2026-08-20    | **F2** 409 idempotency_key con payload distinto (R-9.2) | `31954dd` (+docs `2823eae`) |
| 2026-08-20    | **F3** carrera de custodia idempotente, no 500 (R-9.3)  | `26f5ca1` (+docs `fbfefc7`) |
| 2026-08-20    | **F4** DTOs financieros estrictos (R-9.4)               | `b384f31` (+docs `0800ee9`) |
| **siguiente** | **F5** sesión epoch (R-9.5)                             | _(por abrir — usar §4.2)_   |
