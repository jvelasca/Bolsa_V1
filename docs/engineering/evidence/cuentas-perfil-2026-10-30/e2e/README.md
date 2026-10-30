# CUE-E2E visual — Cuentas y Perfil inversor (2026-10-30)

> Recorrido con navegador real contra el **stack del propio worktree**: Vite en `http://localhost:5317`
> (proxy a `127.0.0.1:8317`) y API `apps/api-python/run_dev.py` en `8317`, con `XTB_BRIDGE_AUTOSTART=0`.
> No se reutilizó ni se proxeó nada del stack del árbol fiscal (5173/8000), que en esta pasada estaba parado
> y se dejó igual.
>
> Autenticidad de la API: el contrato servido por el worktree documenta `PUT /api/accounts/{id}/active-profile → 404`
> y `DELETE /api/investor-profiles/{id} → 409`; el código de `a5f6f1c6` no tiene ni `profile_in_use` ni
> `active_profile_id` desasignable desde la UI.

## Anexos

| Fichero | Contenido |
|---------|-----------|
| `e2e-01-lista.png` … `e2e-08-409.png` | Capturas del recorrido original (casos 1-8). **Históricas**: `e2e-01`/`e2e-05` muestran el copy antiguo «Sin perfil (moderate)», sustituido por «Sin perfil» en la corrección AUD-01. La referencia actual del copy es `e2e-10-sin-perfil.png` |
| `e2e-09-confirmacion.png` | **Nuevo (AUD-01)**: «Quitar perfil» pulsado, confirmación inline visible y todavía sin ninguna escritura |
| `e2e-10-sin-perfil.png` | **Nuevo (AUD-01)**: tras confirmar; cabecera y fila de la cuenta en «Sin perfil», botón ya no ofrecido |
| `console.txt` | Instrumentación de consola (`error`/`warning`/`pageerror`) y las **12 comprobaciones** del caso nuevo. **0 errores** |
| `network.txt` | Traza de red del navegador (34 peticiones `/api/*`), recuento por endpoint y cuerpos de las escrituras |
| `db-before.json` / `db-after.json` | Foto de BD antes y después (mismo script `snapshot-cuentas.py`, solo lectura). **Idénticas byte a byte**: 1 cuenta, 2 perfiles (incluido el huérfano `PROF-afa68b344b69` con `user_id NULL`, invisible para el tenant), 0 residuos |
| `db-active-profile-null.json` | **Nuevo**: lectura SQL directa de la cuenta desechable entre la desasignación y el borrado: `active_profile_id: null`, perfil intacto |
| `db-active-profile.py` | **Nuevo**: script de esa lectura (`uv run python db-active-profile.py <accountId> <profileId>`), solo lectura |
| `snapshot-cuentas.py` | Script de la foto: `uv run python snapshot-cuentas.py`; lee `DATABASE_URL` del `.env` y hace dos `select` de solo lectura |
| `setup-quitar-perfil.json`, `teardown-quitar-perfil.json` | **Nuevos**: ids de los datos desechables del caso 10 y las respuestas del cierre (`close 200` · `DELETE account 204` · `DELETE profile 200`) |
| `e2e-quitar-perfil.mjs` | **Nuevo**: recorrido reproducible del caso 10 con Playwright (ver «Reproducción») |
| `setup-create-account.json`, `setup-create-activacion.json`, `setup-unassign.json` | Respuestas del alta desechable y de la desasignación por API del recorrido original |
| `api-foreign-get.json`, `api-foreign-put.json` | `404` sobre el perfil huérfano/ajeno (`user_id NULL`) |

## Caso 10 (AUD-01) — «Quitar perfil desde la UI»

Ejecutado con `e2e-quitar-perfil.mjs` (Playwright, `chromium` headless, viewport 1440×900) desde `apps/web`:

```powershell
$env:E2E_BASE_URL = "http://localhost:5317"
node ..\..\docs\engineering\evidence\cuentas-perfil-2026-10-30\e2e\e2e-quitar-perfil.mjs
```

| Paso | Comprobación | Resultado |
|------|--------------|-----------|
| Preparación | Alta desechable de cuenta (`CU-AUD01 quitar perfil …`) y perfil (`CU-AUD01 perfil …`) por API | `201` / `200` |
| Asignación | Opción del catálogo + «Aplicar a esta cuenta» → **1** `PUT {"profileId":"PROF-…"}`; la cabecera refleja el perfil | `200` |
| Confirmación | «Quitar perfil» abre `role="alertdialog"` con el texto del fallback moderate; **no se escribe nada** (mismo número de escrituras antes y después del clic) | OK · `e2e-09` |
| Desasignación | «Sí, quitar perfil» → **exactamente 1** `PUT {"profileId":null}`; 0 llamadas a `ensure-defaults` | `200` |
| Estado UI | Cabecera y fila muestran **«Sin perfil»**; el botón «Quitar perfil» deja de ofrecerse | OK · `e2e-10` |
| Estado BD | `select … from investment_accounts where id = <cuenta>` → `active_profile_id = NULL`; el perfil sigue existiendo | `db-active-profile-null.json` |
| Consola | 0 `console.error` y 0 `pageerror` durante todo el recorrido | OK |
| Cierre | `close 200` → `DELETE account 204` → `DELETE profile 200 {"ok":true}`; `db-after.json` **idéntico** a `db-before.json`, `residue_like: []` | OK |

## Resultado caso a caso (recorrido original, casos 1-9)

| # | Caso (plan) | Resultado | Evidencia | Observaciones |
|---|-------------|-----------|-----------|---------------|
| 1 | Lista: badge de perfil por fila y aviso «Sin perfil» | **OK** (copy actualizado) | `e2e-01-lista.png` (histórica), `e2e-10-sin-perfil.png` (copy actual) | Cada fila pinta `Perfil: <nombre> · <plantilla>`; la cuenta desasignada pinta «Sin perfil» en ámbar. Si el perfil no está en el catálogo: «perfil no visible». La captura 01 conserva el texto antiguo «Sin perfil (moderate)» |
| 2 | Clic en una cuenta → `?selected=` y **no** activación | **OK** | `e2e-02-seleccion.png`, `console.txt` | `?selected=6d0f…`; `localStorage` sigue en `default-account-seed`; en toda la traza hay **0** `make-default` antes del caso 3 |
| 3 | «Usar ahora» → sí cambia la cuenta activa | **OK** | `e2e-03-usar-ahora.png`, `network.txt` | `POST /api/accounts/<id>/make-default` → `200`; `isDefault` cambia en servidor; el badge ACTIVA se mueve en la lista y se persiste en `localStorage` |
| 4 | `?type=paper&selected=<id demo>`: la selección no sale del filtro | **OK** | `e2e-04-filtro-paper.png`, `console.txt` | Lista Paper vacía, detalle en placeholder y aviso «La cuenta activa es CU-E2E demo y no está en esta pestaña». La URL conserva `selected` pero **no** se usa para pintar una cuenta fuera del filtro |
| 5 | `?selected=<id>&focus=perfil` → abre Configuración y enfoca la asignación | **OK** | `e2e-05-focus-perfil.png` (histórica), `e2e-09/10` | Bloque `account-profile-block` presente, **1** superficie de asignación, aviso de «sin perfil» visible y comisiones/fiscal con el copy nuevo |
| 6 | Catálogo: sin selector de cuenta, sin «Aplicar», sin `ensure-defaults`, uso visible | **OK** | `e2e-07-catalogo.png` | 0 `<select>`, 0 botón de asignar, **0** `ensure-defaults` en la traza; «En uso en: …»; borrado deshabilitado; aviso al editar compartido |
| 7 | Asignación: sin `PUT` hasta «Aplicar»; aviso de compartido; borrado en uso → `409` en UI | **OK con matiz** | `e2e-06-asignacion.png`, `e2e-08-409.png` | Seleccionar no escribe; «Aplicar» → 1 `PUT 200`. El `409` se probó forzando caché obsoleta: mensaje «No se puede eliminar: el perfil está en uso…», perfil intacto. **Matiz**: el texto de la UI no enumera las cuentas afectadas (el payload sí) → AUD-04 |
| 8 | Cambio Demo/Paper y `?selected=` → nunca activan; consola limpia | **OK** | `network.txt`, `console.txt` | Los 4xx/5xx inesperados del recorrido original fueron 1 `422` de un `curl` mal escapado, 2 `404` de sondas a `/openapi.json`, el `409` y los `404` intencionados |
| 9 | (Observación) filtros avanzados combinados con Demo/Paper | **N/A — deuda confirmada** | — | La página de Cuentas no tiene búsqueda ni filtros avanzados: solo `Demo / Paper / Todas` y `tab`/`focus`/`selected`. AUD-05 documenta que `focus` sobrevive al cambio de pestaña |

## Cierre: cero residuos

| Comprobación | Resultado |
|--------------|-----------|
| Caso 10 — `CU-AUD01 quitar perfil …` / `PROF-…` | `close 200` + `DELETE 204` + `DELETE profile 200`; no aparecen en `GET /api/accounts` ni en el catálogo |
| Recorrido original — `CU-E2E demo` / `CU-E2E activacion` / `CU-E2E perfil` | Cerrados y borrados en su pasada; no reaparecen en `db-after.json` |
| `is_default` | Sigue en `default-account-seed` |
| `active_profile_id` de la semilla | `PROF-996fcd3d6ec6` (nunca cambió) |
| Foto de BD final (`db-after.json`) | Comparación con `db-before.json`: **idéntica byte a byte**; `residue_like: []` (0 filas `CU-*`/`PROF-EVIDENCIA*`/`PROF-AJENO-*`) |
| `localStorage` | `bolsa-active-account` no se modifica en el caso 10 (se navega con `?selected=`) |
| Árbol fiscal | Ver §7 de `diff-audit.md`: `HEAD c9e572cb`, 65 entradas, hash `1B8D293A7F00BA5D` |
| Servidores | 5317/8317 detenidos tras el recorrido; 5173/8000 no se arrancaron |

## Límites declarados

- El armazón de mercado autoguarda su estado (`PUT /core-r`, `PUT /workspaces/…`) al montar el panel: son
  escrituras preexistentes ajenas a Cuentas/Perfil inversor. La foto de BD de cuentas/perfiles demuestra que no
  dejan residuo en este alcance.
- Las capturas 01-08 son del navegador de Cursor en la pasada de auditoría; las 09-10 son de Playwright
  (`chromium` headless) a 1440×900, con el copy corregido. No se probó responsive ni tema oscuro.
- No se probó el flujo «Nueva demo» del asistente en vivo (solo su copy y el uso compartido del picker, vía
  revisión y tests). Queda como hueco de este recorrido.
- El caso 10 usa una cuenta y un perfil desechables creados por API: lo que se ejercita por UI es la
  asignación, la confirmación y la desasignación, no el alta.
