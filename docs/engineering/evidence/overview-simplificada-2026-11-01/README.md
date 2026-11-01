# Evidencia — simplificación de Overview (2026-11-01)

> **Alcance:** solo frontend (`/overview`). Sin cambios de backend, contrato HTTP, DTO, Alembic ni worker.
> **Seguimiento:** [`../../seguimiento-ui-overview-2026-11-01.md`](../../seguimiento-ui-overview-2026-11-01.md).
> **Aceptación:** [`../../dictamen-overview-simplificada-2026-11-01.md`](../../dictamen-overview-simplificada-2026-11-01.md)
> (límites `L-OVW-1` y `L-OVW-2`).

---

## 1. Entorno de la medición

| Elemento | Valor |
| --- | --- |
| Frontend | Vite en `:5173` (`apps/web`) |
| API | Python en `:8000`, PostgreSQL local |
| Cuenta activa | `Demo · Cuenta demo EUR` (`default-account-seed`) |
| Navegador de la verificación en vivo | panel del IDE y ventanas de 1440×900 / 390×740 |
| Suite de componente | `vitest` v3.2.6 |

Nota de entorno: el barrido axe falló en el primer intento con `browserType.launch: Executable doesn't exist`.
Se resolvió con `pnpm --filter @bolsa/web exec playwright install chromium` y se repitió: fallaban las 35 rutas,
no solo Overview, así que no era un defecto del cambio.

---

## 2. Ficheros y qué mide cada uno

| Fichero | Qué mide | Resultado |
| --- | --- | --- |
| `vitest-area.txt` | `vitest run src/features/dashboard src/test/heading-order.test.tsx` | **2 archivos / 19 tests** ✅ (9 de `dashboard-page.test.tsx`, 10 de `heading-order.test.tsx`) |
| `tsc.txt` | `pnpm --filter @bolsa/web typecheck` (`tsc -b --noEmit`) | sin salida de error ✅ |
| `eslint.txt` | `eslint src/` | **0 errores**, 23 avisos `react-hooks/exhaustive-deps` preexistentes |
| `contract-check.txt` | `pnpm contract:check` (`sync-contract.mjs --check`) | **OK** — `openapi.json` y `schema.d.ts` coinciden con el commit |
| `axe-touched-routes.txt` | `playwright e2e/gp-e2e-ui5-0-axe-touched-routes-mock.spec.ts` | **35/35** ✅, incluidos `/overview` @desktop y @móvil 390×844 con 0 `critical`/`serious` |
| `api-overview.txt` | Contraste de la UI con `GET /api/accounts`, `/summary` y `/ledger?limit=8` | 200 · `totalEquity=99800` · `cash=99800` · `totalUnrealizedPnl=0` · `positionsCount=0` · `freeMargin=99800` · 2 asientos |
| `overview-antes-628x918.png` | Antes del cambio, panel real del IDE | contenido de **1749 px** a 1440×900 |
| `overview-despues-1440x900.png` | Después, 1440×900 | **596 px**, sin scroll (`scrollH = clientH = 853`) |
| `overview-despues-movil-390x740.png` | Después, 390×740 | 1103 px de contenido, `scrollWidth = 390` (sin overflow horizontal) |
| `overview-despues-628x918.png` | Después, panel real del IDE | mismo árbol que las otras dos capturas |

La captura «antes» se tomó a 628×918 porque es el panel del IDE en el que se detectó el problema; la cifra de
**1749 px** corresponde a la medición a 1440×900 y es la que se compara con los **596 px** del «después».

---

## 3. Qué **no** forma parte de esta evidencia

* **`C:\Users\josea\overview-despues-desktop.png`** — residuo del escritorio, **externo al repositorio**. No se
  copió a esta carpeta, no se cita como ancla y no se usa en el dictamen. Las capturas válidas son las cuatro de
  §2.
* **La suite web completa (2 686 tests)** — se ejecutó y quedó verde, pero no se guardó su salida en este
  directorio; se cita en el seguimiento (§6) y en el dictamen (§1.2) como cifra publicada, no como fichero.
* **El estado con varias cuentas activas en navegador** — no se midió. Es el límite `L-OVW-2`: la cobertura es el
  caso unitario `señala cuántas otras cuentas activas hay`.

---

## 4. Reproducir

Desde la raíz del repo y con el stack local levantado:

```bash
pnpm --filter @bolsa/web exec vitest run src/features/dashboard src/test/heading-order.test.tsx
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web exec eslint src/
pnpm contract:check
pnpm --filter @bolsa/web exec playwright test e2e/gp-e2e-ui5-0-axe-touched-routes-mock.spec.ts
```

El contraste HTTP de `api-overview.txt` se reproduce con la cuenta `default-account-seed` y
`curl` sobre los tres endpoints citados.
