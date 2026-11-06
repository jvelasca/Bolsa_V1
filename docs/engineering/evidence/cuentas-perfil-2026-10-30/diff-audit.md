# Auditoría del diff — `feat/cuentas-perfil-2026-10-30`

> Auditoría **read-only** del trabajo de Cuentas / Perfil inversor contra el sello `a5f6f1c6`, con el
> recorrido visual CUE-E2E ejecutado contra la API del propio worktree. Esta pasada (§0-§6) no aplicó ninguna
> corrección de código: los hallazgos se documentan y se para para decisión.
>
> **Segunda pasada (2026-10-30)**: se aplicaron las correcciones AUD-01, AUD-03 y AUD-07 aprobadas a partir de
> esta auditoría; el resultado, los ficheros tocados y los gates re-medidos están en **§7**.
>
> Fecha: 2026-10-30 · Worktree: `C:\Users\josea\.cursor\worktrees\cuentas-perfil-2026-10-30`
> Evidencia del recorrido: [`e2e/`](./e2e/README.md) · Evidencia de gates: [`README.md`](./README.md)

---

## 0. Invariantes comprobados (antes y después)

| Invariante | Antes | Después |
|------------|-------|---------|
| `HEAD` del worktree | `a5f6f1c6` | `a5f6f1c6` (sin commit) |
| Árbol fiscal `Bolsa_V1` | `HEAD c9e572cb`, 65 entradas en `git status --porcelain --untracked-files=all`, hash del listado ordenado `1B8D293A7F00BA5D` | **idéntico** (mismo HEAD, 65 entradas, `1B8D293A7F00BA5D`). Ningún fichero de código/docs/evidencia con `mtime` posterior al inicio; lo único con fecha nueva son `logs/` y `operability_runs/`, que escribe el stack dev ajeno ya en marcha |
| Worktree `git status` | 34 entradas (`1079A571FA1AEAFA`) | 54 entradas (`9BE16306E15BEFC6`): +20 y todas en documentación/evidencia (`diff-audit.md` + los 19 ficheros de `e2e/`) |
| BD (cuentas/perfiles) | 1 cuenta (`default-account-seed`, `is_default=true`, `active_profile_id=PROF-996fcd3d6ec6`), 2 perfiles | **idéntica** (`db-after.json` comparado con `db-before.json`: byte a byte salvo fin de línea) |
| Procesos | Stack dev ajeno vivo en 5173/8000 (intacto) | Ese stack sigue vivo; los puertos aislados 5317/8317 se cerraron |

Sin commit, push, PR, tag ni Release. Las únicas escrituras de BD fueron sobre datos desechables `CU-E2E-*`
(borrados al final) más el autoguardado preexistente del panel de mercado (`PUT /core-r`, `PUT /workspaces/…`),
ajeno a este alcance.

---

## 1. Alcance: 16 modificados (+581/−358) y 18 sin seguimiento

### 1.1 Modificados

| Archivo | +/− | Veredicto |
|---------|-----|-----------|
| `apps/api-python/.../routes/investor_profiles.py` | +36/−6 | Correcto: `responses` documentados, 409 con `accounts`, `principal` propagado a `ensure-defaults` y a la asignación |
| `apps/web/api/openapi.json` | +6/−0 | **Solo documentación** (404 en PUT active-profile, 409 en DELETE) |
| `apps/web/src/api/schema.d.ts` | +14/−0 | **Solo documentación**; no cambia ningún tipo request/response |
| `apps/web/src/features/accounts/account-detail-panel.tsx` | +90/−7 | Correcto; ver AUD-02/AUD-04 |
| `apps/web/src/features/accounts/account-investor-profile-select.tsx` | +85/−43 | Correcto: única superficie de asignación, `pendingId` explícito; ver AUD-01 |
| `apps/web/src/features/accounts/account-settings-dialog.tsx` | +2/−3 | Solo copy/título |
| `apps/web/src/features/accounts/account-settings-panel.tsx` | +0/−8 | Retirada limpia del selector y de `activeProfileId` |
| `apps/web/src/features/accounts/accounts-page.tsx` | +129/−25 | Correcto; ver AUD-04/AUD-05 |
| `apps/web/src/features/accounts/create-account-wizard-dialog.tsx` | +12/−1 | Correcto (uso compartido + copy) |
| `apps/web/src/features/accounts/investor-profile-panel.tsx` | +62/−201 | Correcto: catálogo puro; `assignAccountId`/`assignProfileId`/`assignMutation`/auto-bootstrap eliminados |
| `apps/web/src/features/config/platform-config-dialog.tsx` | +10/−26 | Correcto: la pestaña ya no exige cuenta activa |
| `apps/web/src/features/help/app-help-menu.tsx` | +11/−6 | Solo texto de ayuda |
| `docs/API_REFERENCE.md` | +28/−12 | Coherente con el comportamiento real verificado en vivo |
| `docs/CONFIGURATION_MODEL.md` | +11/−2 | Coherente |
| `packages/py/application/.../investor_profiles.py` | +64/−16 | Correcto: `DeleteInvestorProfileResult`, `accounts_using`, `DEFAULT_PROFILE_NAME`; ver AUD-03 |
| `packages/py/infrastructure/.../investor_profile_repository.py` | +21/−2 | Correcto: `owner_user_id` en cuenta y perfil, `accounts_using`; ver AUD-03 |

Ningún path pertenece a fiscal (`fiscal/`, `tax-report`, comisiones), ni hay cambios en
`packages/shared`, `package.json`, lockfiles o migraciones.

### 1.2 Sin seguimiento (18)

| Archivo | Tipo | Veredicto |
|---------|------|-----------|
| `packages/py/application/tests/test_investor_profiles.py` | test (9 casos) | Genuino: fake store con el mismo contrato que el puerto. No mockea lo que verifica |
| `apps/api-python/tests/test_investor_profiles_assign.py` | test (3 casos) | Genuino: ASGI + PostgreSQL real; crea perfil ajeno por SQL directo para probar el 404. Ver AUD-06 |
| `accounts-page.test.tsx` (5) | test | Genuino: comprueba `?selected=`, ausencia de `make-default` y `localStorage` |
| `account-detail-panel.test.tsx` (5) | test | Genuino (incluye `?focus=perfil` y perfil legacy) |
| `account-investor-profile-select.test.tsx` (4) | test | Genuino: `PUT` solo tras «Aplicar»; sin auto-ensure (el mock ni lo define) |
| `investor-profile-panel.test.tsx` (3) | test | Genuino: uso por perfil, borrado deshabilitado, aviso de compartido |
| `account-settings-panel.test.tsx` (1) | test | Genuino, pero **colisiona con el árbol fiscal** (§3) |
| `evidence/…/README.md` + 9 `*.txt` | evidencia | Recuentos reproducidos; ver AUD-07 |
| `docs/engineering/seguimiento-…-2026-10-30.md` | seguimiento | Actualizado en esta pasada (§4) |

### 1.3 Ruido accidental

Ninguno de los marcadores buscados aparece en las líneas añadidas: ni `console.log`/`console.debug`, ni
`debugger`, ni `TODO`/`FIXME`, ni `.only(`. Sin código comentado ni imports muertos en el diff. El único
resto es una función del cliente que ya nadie llama (AUD-02).

---

## 2. Invariantes de comportamiento (revisión + comprobación en vivo)

| Invariante | Cómo se comprobó | Resultado |
|------------|------------------|-----------|
| Seleccionar en la lista **no** activa la cuenta | Clic real + `localStorage` + log de la API | `?selected=` cambia; `localStorage` intacto; **0** `make-default` en todo el recorrido salvo el de «Usar ahora» |
| «Usar ahora» sí activa | Clic real | `POST /make-default` 200, `isDefault` en servidor, ACTIVA movida en la lista |
| La selección se constriñe al filtro | `?type=paper&selected=<demo>` | Lista Paper vacía + aviso de activa fuera del filtro + placeholder de detalle; el detalle **no** pinta la cuenta demo |
| `?focus=perfil` abre Configuración y enfoca la asignación | Navegación real | Bloque presente, **1** superficie de asignación, copy «Editar comisiones y fiscal» |
| Una sola superficie de asignación | DOM del modal y de comisiones/fiscal | `AccountInvestorProfileSelect` solo en la ficha; `AccountSettingsPanel` sin selector |
| El catálogo es puro (sin cuenta, sin asignar, sin auto-ensure) | DOM + log | Sin selector de cuenta, sin «Aplicar», **0** `ensure-defaults` |
| Asignar solo con «Aplicar» | Clic real + log | Seleccionar no escribe; «Aplicar» → 1 `PUT` 200 |
| Borrado de perfil en uso | UI + API | Botón deshabilitado; con caché obsoleta → `DELETE 409` y mensaje en UI (AUD-04) |
| Perfil ajeno/legacy invisible | API con el perfil huérfano `PROF-afa68b344b69` (`user_id NULL`) | `GET` → 404, `PUT` → 404 «Perfil no encontrado», la cuenta conserva su perfil (no 403) |
| Bootstrap con dueño e idempotente | Test de integración (PG real) | `ensure-defaults` devuelve un único perfil con `userId`, y la segunda llamada no duplica |

---

## 3. Roces de integración con el árbol fiscal

Intersección exacta de paths entre los dos `git status`: **5** (4 modificados + 1 sin seguimiento).

| Path | Divergencia en el árbol fiscal vs `a5f6f1c6` | Divergencia aquí | Riesgo de conflicto |
|------|---------------------------------------------|------------------|---------------------|
| `account-detail-panel.tsx` | 49 líneas (hunks en 23, 138, 648-650, 711) | 97 líneas (hunks en 104, 128, 145, 176, 330, 399, 483, 721, 742) | **Alto** en el bloque «Comisiones y fiscal» (ambos tocan ~línea 640-660: el fiscal añade campos y aquí cambia el botón) |
| `account-settings-panel.tsx` | 219 líneas (presets, `initialTab`, validación cliente) | 8 líneas (retirada del selector) | **Alto**: es el fichero más reescrito del lado fiscal; la retirada aquí es de 3 bloques concretos que hay que reintroducir a mano |
| `account-settings-dialog.tsx` | 4 líneas | 5 líneas (título/descripción) | **Medio**: mismas líneas de cabecera; conflicto seguro pero trivial de resolver |
| `create-account-wizard-dialog.tsx` | 22 líneas (imports, 591, 601, 626) | 13 líneas | **Bajo/Medio**: zonas distintas salvo el bloque de perfil |
| `account-settings-panel.test.tsx` | **Sin seguimiento**, hash `9CB7C8D5…` | **Sin seguimiento**, hash `5A4493F7…` | **Colisión de path**: al integrar hay que **fusionar** los dos ficheros; el fiscal trae 7+ casos (presets, fiscal ES/US, validación, guardado) y aquí 1 (sin selector de perfil). Ambos son compatibles, pero sobrescribir perdería cobertura |

Ningún import del diff apunta a algo que solo exista en el árbol fiscal: `POLICY_TEMPLATE_LABELS` vive en
`packages/shared/src/cognitive/suggest-policy-from-declared.ts` (sin cambios en ninguno de los dos árboles),
y `tsc` está limpio en el worktree. La dependencia es solo de *paths compartidos*, no de símbolos.

**Orden recomendado al integrar**: rebasar el fiscal sobre esta rama (el fiscal tiene más masa en
`account-settings-panel.tsx`), resolver los 4 ficheros a mano y **fusionar** los dos tests del panel de
comisiones conservando los 8 casos.

---

## 4. Hallazgos

Severidad: **Alta** = puede producir datos/UX incorrectos · **Media** = limitación funcional o evidencia poco
fiable · **Baja** = higiene · **Info** = anotación sin acción.

| ID | Sev. | Hallazgo | Ubicación | Recomendación (no aplicada) |
|----|------|----------|-----------|------------------------------|
| **AUD-01** | Media | **La UI no puede desasignar un perfil.** `InvestorProfilePicker` no ofrece opción «sin perfil» y `selectedId = pendingId \|\| activeProfileId` cae al activo con `pendingId=""`, así que `dirty` nunca es verdadero para desasignar. El estado «sin perfil» (que la UI sí sabe pintar y avisar) solo se alcanza por API (`profileId: null`), como se hizo en el E2E | `account-investor-profile-select.tsx`, `investor-profile-picker.tsx` | Decidir producto: o se añade «Quitar perfil» explícito, o se documenta que la desasignación es solo API |
| **AUD-02** | Baja | Código muerto: `api.ensureDefaultInvestorProfiles` sigue en el cliente sin ningún llamador (el endpoint debe seguir existiendo para el bootstrap externo) | `apps/web/src/lib/api.ts:1320` | Retirar del cliente o dejar comentario de por qué se conserva |
| **AUD-03** | Media | **Ventana TOCTOU en el borrado**: `DeleteInvestorProfile` consulta `accounts_using` y después borra, sin serializar contra una asignación concurrente. Además `SqlAlchemyInvestorProfileRepository.delete()` **sigue desasignando** cuentas: el guard vive en el caso de uso, no en el repositorio, así que cualquier llamada directa al repo mantiene el borrado silencioso | `investor_profiles.py`, `investor_profile_repository.py` | Mover el guard al repositorio (o a una operación atómica) y quitar el `update(...).values(active_profile_id=None)` |
| **AUD-04** | Baja | **El mensaje del 409 en UI no enumera las cuentas** afectadas, aunque el payload las trae (`accounts`): se muestra un texto fijo. El detalle sí está en la fila («En uso en: …») y en el JSON | `investor-profile-panel.tsx` (`onError`) | Pintar `detail.accounts` cuando llegue |
| **AUD-05** | Baja | Higiene de URL: `focus` sobrevive al cambio de filtro/pestaña (`?selected=…&focus=perfil&type=all`); solo se limpia al seleccionar otra cuenta | `accounts-page.tsx` (`setHubFilter`) | Borrar `focus` al cambiar de pestaña o al cerrar el foco |
| **AUD-06** | Baja | El test de integración restaura el estado con `_restore`, que **cae a `ensure-defaults`** si el `PUT` de restauración falla (perfil legacy `user_id NULL`). En esta pasada la semilla tenía perfil propio y la restauración fue exacta (BD idéntica), pero en un entorno con perfil legado la suite cambiaría el estado de la cuenta semilla | `apps/api-python/tests/test_investor_profiles_assign.py` | Fallar el test si la restauración no es exacta, en vez de bootstrapear |
| **AUD-07** | Media (evidencia) | `contract-check.txt` está **corrupto**: texto UTF-16 volcado como UTF-8 → 920 bytes NUL, ilegible para revisión y para `grep`. Los otros 8 `*.txt` están en UTF-16LE (default de `Out-File` en PowerShell 5.1), así que no son grep-amigables ni reproducibles desde otro shell | `evidence/…/*.txt` | Reescribir la evidencia con `-Encoding utf8` (idealmente en un solo paso reproducible) |
| **AUD-08** | Info | `accounts-page.tsx` resuelve `activeAccount` sobre `accounts` (incluye cerradas), así que el aviso «la cuenta activa está fuera de esta pestaña» podría nombrar una cuenta cerrada. Situación de borde | `accounts-page.tsx` | Filtrar por `status === "active"` si se quiere endurecer |
| **AUD-09** | Info | `goToProfileBlock` usa un `setTimeout(…, 80)` para hacer scroll tras cambiar de pestaña; el deep-link equivalente (`?focus=perfil`) usa el efecto con `setTimeout` también. Funciona, pero es frágil ante cambios de render | `account-detail-panel.tsx` | Sustituir por `useLayoutEffect`/callback de pestaña |

### Verificado sin hallazgos

- El contrato OpenAPI cambia **solo** por documentación: `contract:check` verde y el diff son 6+14 líneas de
  `404`/`409`, sin esquemas ni tipos de request/response.
- Los 8 gates se reproducen hoy con los mismos recuentos (§5).
- Las respuestas reales (`200`/`404`/`409`) se reproducen contra la API de este worktree; `profile_in_use` no
  existe en `a5f6f1c6`.
- El perfil `PROF-32502ce0735d` citado en la evidencia ya no existe y no quedan filas `CU-*`/`PROF-EVIDENCIA*`.
- El perfil huérfano preexistente `PROF-afa68b344b69` (`user_id NULL`) es invisible para su dueño: `404` en
  `GET` y en `PUT`, y la cuenta conserva su perfil al rechazarse.

---

## 5. Gates reproducidos en esta pasada

| Gate | Declarado | Reproducido hoy |
|------|-----------|-----------------|
| `pytest` área | 12 passed | **12 passed** (9 fake store + 3 PG/ASGI, 9.1 s) |
| `vitest` área | 5 ficheros · 18 tests | **5 · 18** |
| `vitest` web completa | 353 ficheros · 2632 tests | **353 · 2632** (38.5 s) |
| `tsc -b --noEmit` | limpio | **exit 0** |
| `eslint` áreas | sin hallazgos | **exit 0** |
| `contract:check` | `OK` | **OK** |
| `ruff check` | limpio | **All checks passed** |
| `mypy` | 582 ficheros | **582, sin errores** |
| BD tras la suite API | restaurada | **idéntica a la foto previa** |

---

## 6. Veredicto

- **Alcance**: limpio. Todo el diff pertenece a Cuentas / Perfil inversor, docs y evidencia; cero ruido
  accidental y cero rastros fiscales.
- **Comportamiento**: los invariantes declarados se sostienen en revisión **y** en navegador real con la API
  del propio worktree (incluido el `409` y el `404` de perfil ajeno).
- **Bloqueos para dar por cerrado el trabajo**: ninguno de severidad Alta. Hay **dos decisiones de producto**
  que conviene tomar antes de integrar: AUD-01 (¿se puede quitar el perfil desde la UI?) y AUD-03 (¿dónde vive
  el guard de borrado: caso de uso o repositorio?).
- **Coste de integración**: 5 paths compartidos, con dos conflictos altos (`account-settings-panel.tsx` y
  `account-detail-panel.tsx`) y una colisión de test que exige fusión manual.
- **Nada se ha modificado, commiteado ni publicado**; el árbol fiscal sigue con sus 65 entradas y el mismo
  hash que al empezar.

> **Actualización (segunda pasada)**: el veredicto anterior describe el estado **antes** de corregir. AUD-01,
> AUD-03 y AUD-07 se han corregido y re-auditado en §7; AUD-02/AUD-04/AUD-05/AUD-06/AUD-08/AUD-09 siguen
> abiertos y fuera del alcance de esta pasada.

---

## 7. Correcciones aplicadas — AUD-01, AUD-03 y AUD-07

Pasada de corrección sobre el mismo worktree (`a5f6f1c6`, sin commit). Objetivo: cerrar el ciclo de vida del
perfil inversor (borrado íntegro y desasignación explícita) y sanear la evidencia.

### 7.1 AUD-03 — el borrado ya no puede desasignar cuentas

| Cambio | Archivo | Efecto |
|--------|---------|--------|
| `delete()` → `delete_if_unused(profile_id) -> (bool, nombres)` | `packages/py/infrastructure/.../investor_profile_repository.py` | Bloquea la fila con `select(...).with_for_update()` **antes** de contar cuentas, borra dentro de `begin_nested()` y captura `IntegrityError` como `(False, nombres)`. Desaparece el `update(InvestmentAccountRow)…values(active_profile_id=None)` |
| `assign_to_account` toma el mismo lock | idem | Asignación y borrado se serializan sobre la fila del perfil: si el borrado ganó, la asignación espera, relee y recibe `ValueError("Perfil no encontrado")` (404) sin escribir |
| Puerto y caso de uso sin TOCTOU | `packages/py/application/.../investor_profiles.py` | `InvestorProfileStore.delete_if_unused`; `DeleteInvestorProfile` solo traduce `(deleted, in_use_by)`. La ruta mantiene el `409 profile_in_use` con `accounts` |
| FK `ON DELETE RESTRICT` | `.../models/tables.py`, `alembic/versions/061_profile_delete_restrict.py`, `prisma/schema.prisma`, `prisma/migrations/20260723020000_…/migration.sql`, `docs/DATA_MODEL.md` | La BD es el backstop: `DELETE` en SQL crudo sobre un perfil asignado falla con `IntegrityError`. Migración idempotente (solo recrea si `pg_constraint.confdeltype <> 'r'`), `downgrade` vuelve a `SET NULL` |

Pruebas nuevas:

- `packages/py/infrastructure/tests/test_investor_profile_delete_guard.py` (PostgreSQL real): acceso **directo**
  al repositorio sobre un perfil asignado → `(False, ("AUD-03 dir",))` con cuenta y perfil intactos; tras
  desasignar → borra; `DELETE` en SQL crudo → `IntegrityError` y la cuenta conserva el perfil; concurrencia
  con `asyncio.Event` y sesiones independientes (6 rondas) → o gana la asignación y el borrado ve uso, o gana el
  borrado y la asignación recibe 404; nunca queda una cuenta apuntando a un perfil inexistente.
- `test_schema_contract.py`: la FK declarada en metadata es `ondelete="RESTRICT"`.
- `test_investor_profiles.py`: un store «que ve libre y borra ocupado» demuestra que el guard vive en el store
  (si el caso de uso volviera a consultar por su cuenta, el test borraría y fallaría).
- `test_investor_profiles_assign.py`: nuevo caso de cuenta **cerrada** que sigue bloqueando el borrado (`409`) y
  conserva `active_profile_id`.

### 7.2 AUD-01 — «Quitar perfil» explícito y confirmado

| Cambio | Archivo | Efecto |
|--------|---------|--------|
| Botón `account-profile-clear` + confirmación inline `role="alertdialog"` | `apps/web/src/features/accounts/account-investor-profile-select.tsx` | La desasignación es una acción propia, separada de «cambiar perfil». Solo aparece si hay perfil activo; deshabilitado mientras hay mutación |
| `PUT {"profileId": null}` en la mutación `clearMutation` | idem | Un único PUT al confirmar; invalida `accounts` y `account-summary`; no llama a `ensure-defaults` ni reasigna el perfil por defecto |
| Copy «Sin perfil» | `accounts-page.tsx` (fila), `account-detail-panel.tsx` (cabecera) | La fila y la cabecera muestran «Sin perfil»; el aviso ámbar del bloque de perfil conserva la explicación del fallback moderate (comportamiento del Policy Gate, no sustitución de perfil) |

Pruebas nuevas (`account-investor-profile-select.test.tsx`, 4 casos): pedir confirmación no escribe; cancelar
no escribe; confirmar llama **exactamente** `assignAccountProfile("acc-a", null)` una vez; sin perfil activo el
botón no existe. El mock no define `ensureDefaultInvestorProfiles`, así que cualquier bootstrap rompería el
test. `account-detail-panel.test.tsx` fija la cabecera «Sin perfil» y `accounts-page.test.tsx` la fila.

### 7.3 AUD-07 — evidencia UTF-8 reproducible

- Nuevo [`regen-evidence.ps1`](./regen-evidence.ps1): ejecuta los diez gates y escribe con
  `UTF8Encoding($false)` (sin BOM), con `[exit N · Ns]` al final de cada fichero. Compatible con PowerShell 5.1.
- Los diez `*.txt` regenerados: **0 bytes NUL**, sin BOM, legibles con `Get-Content -Encoding utf8` y con
  `grep`. `contract-check.txt` contiene la salida real de `contract:gen` + `contract:check`.
- `vitest-web-full.txt` y `vitest-web-full-run2.txt` son dos ejecuciones completas independientes.
- Nuevo [`api-evidence.py`](./api-evidence.py): evidencia HTTP reproducible del `409`, del `404` ajeno y del
  `PUT null` → `active_profile_id NULL`, con restauración del estado y verificación de residuos.

### 7.4 Archivos nuevos de esta pasada

| Archivo | Tipo |
|---------|------|
| `packages/py/infrastructure/alembic/versions/061_profile_delete_restrict.py` | migración |
| `packages/py/infrastructure/tests/test_investor_profile_delete_guard.py` | test PG (3 casos) |
| `docs/engineering/evidence/…/regen-evidence.ps1` | herramienta de evidencia |
| `docs/engineering/evidence/…/api-evidence.py` | herramienta de evidencia |
| `docs/engineering/evidence/…/e2e/e2e-quitar-perfil.mjs` | E2E Playwright (caso 10) |
| `docs/engineering/evidence/…/e2e/db-active-profile.py` | lectura SQL de cierre (solo lectura) |
| `e2e/e2e-09-confirmacion.png`, `e2e/e2e-10-sin-perfil.png`, `e2e/db-active-profile-null.json`, `e2e/setup-quitar-perfil.json`, `e2e/teardown-quitar-perfil.json`, `vitest-web-full-run2.txt` | evidencia |

### 7.5 Efecto colateral declarado: guardias de `head` de Alembic

Añadir la revisión 061 cambia la `head` de la cadena, y seis tests la fijan de forma explícita (convención del
repo: «al añadir una migración hay que actualizar la constante»). Se actualizó **solo la constante**, sin tocar
la lógica: `test_signal_alerts_v111_pg.py`, `test_dia_d_cycle_verification_pg.py`,
`test_discovery_evidence_snapshot_pg.py`, `test_database_maintenance_pg.py`,
`test_auto_v57_auto16_applied_cost_pg.py`, `test_auto_v88_27_durable_facts_idempotent_pg.py`. Sin estos cambios
esas suites fallarían con la BD en `head` (061). No hay ningún otro cambio fuera del alcance Cuentas/Perfil.

### 7.6 Gates re-medidos

| Gate | Antes | Ahora |
|------|-------|-------|
| `pytest` área | 12 passed | **22 passed** (+3 guard PG, +5 contrato, +1 ASGI cerrada, +1 aplicación) |
| `vitest` área | 5 files · 18 tests | **5 files · 23 tests** (+5 de «Quitar perfil»/cabecera) |
| `vitest` web completa | 353 · 2632 | **353 · 2637** (dos ejecuciones independientes) |
| `tsc -b --noEmit` | limpio | **exit 0** |
| `eslint` áreas | sin hallazgos | **exit 0** |
| `contract:check` | OK | **OK** (237 paths · 519 schemas) |
| `ruff check` (con `--config pyproject.toml`) | limpio | **All checks passed** |
| `mypy` | 582 files | **582, sin errores** |
| Alembic | `060_provider_check_policy` | **`061_profile_delete_restrict`** aplicada; `confdeltype = 'r'` |
| BD tras pytest/E2E | restaurada | **idéntica** (`db-before.json` == `db-after.json`, `residue_like: []`) |

### 7.7 Invariantes de cierre

| Invariante | Resultado |
|------------|-----------|
| Ningún camino borra un perfil asignado | ruta `409` · repositorio `(False, nombres)` · SQL crudo `IntegrityError` · concurrencia sin estado incoherente |
| Escrituras implícitas de `active_profile_id = NULL` | **0** en el código; el único `NULL` nace de un `PUT` explícito (UI o API) |
| UI puede desasignar | «Quitar perfil» + confirmación; `PUT {"profileId": null}` único; 0 `ensure-defaults`; cabecera y fila «Sin perfil» |
| Evidencia | 10 `*.txt` UTF-8 sin BOM, 0 NUL, `contract-check.txt` real, dos ejecuciones completas de Vitest |
| Árbol fiscal `Bolsa_V1` | `HEAD c9e572cb`, 65 entradas en `git status --porcelain --untracked-files=all`, hash `1B8D293A7F00BA5D` |
| Worktree | `HEAD a5f6f1c6`, **77 entradas** en `git status --porcelain --untracked-files=all` (27 modificados + 50 sin seguimiento), sin commit, push, PR, tag ni Release |

### 7.8 Hallazgos que siguen abiertos

AUD-02 (código muerto `ensureDefaultInvestorProfiles` en el cliente), AUD-04 (el 409 de UI no enumera las
cuentas), AUD-05 (`focus` sobrevive al cambio de pestaña), AUD-06 (`_restore` puede caer a `ensure-defaults`),
AUD-08 (`activeAccount` incluye cerradas) y AUD-09 (`setTimeout` en el scroll al bloque de perfil). Ninguno es
bloqueante para integrar; quedan como deuda anotada.

