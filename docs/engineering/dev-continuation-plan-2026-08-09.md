# Continuación: estado + plan de siguientes pasos — 2026-08-09

Documento vivo de continuación. Enlaza con
[improvement-roadmap-post-audits-2026-08-02.md](./improvement-roadmap-post-audits-2026-08-02.md)
(roadmap de fases Q0–Q3) y con el trabajo de la rama
`stage/estudio-membership-operativa-2026-08-04`.

## 1. Qué se ha hecho (registro de trabajo reciente)

| Commit    | Momento           | Qué                                                                                               |
| --------- | ----------------- | ------------------------------------------------------------------------------------------------- |
| `939a1f3` | F1·3              | CI frontend (typecheck+lint+test+build) + reparar lint web                                        |
| `b045b81` | F1·4              | Pre-commit con lint-staged (prettier + eslint --fix)                                              |
| `3219e8b` | F1·5              | Refuerzo preventivo de `.gitignore`                                                               |
| `4ec5bac` | F2·6              | Quitar secretos por defecto hardcodeados (auth_secret, BD)                                        |
| `d9dc6ba` | F4·8 paso 1       | Extraer `backtest-hub-nav` (tipos/`parseTab`/`isAnalysisResultFocus`) + tests                     |
| `bbdba44` | F3·7 (post-audit) | `run-dev`/`dev-api-python` cargan `.env` raíz → API conecta a BD (fix 500 "no password supplied") |
| `57bc732` | F4·8 paso 2       | Extraer `HubTabButton` a `backtest-hub-tabs.tsx` + tests                                          |
| `01d3944` | docs              | Registrar hallazgo recurrente F3.7 en el roadmap                                                  |

Batería de verificación por paso: `typecheck` + `lint` (0 errores) + `build` + tests.
Tras los pasos 1–2 de F4·8 el web queda en **139 archivos / 701 tests en verde**.

Reducción real de `backtests-page.tsx`: **~5.792 → 5.549 líneas** (~243 menos) tras
extraer `hub-nav` y `HubTabButton`.

## 2. Hallazgo recurrente del dev-stack (F3.7, sin resolver del todo)

**Síntoma:** el stack `run-dev` cae de forma intermitente bajo carga de `sync`.
En `logs/dev/*Z.log` la última línea antes del crash es:

```text
[vite] http proxy error: /api/instruments/{id}/sync
Error: read ECONNRESET
```

y acto seguido `ERR_PNPM_RECURSIVE_RUN_FIRST_FAIL` y `Deteniendo stack (exit=1)`.
Quedan procesos huérfanos (API + Vite) que siguen respondiendo 200 y hay que
limpiarlos a mano; los puertos quedan libres tras el cleanup.

**Causa raíz (diagnóstico):** Vite actúa de proxy hacia la API; en operaciones de
`sync` pesadas la API cierra la conexión TCP a medias (`ECONNRESET`), y Vite aborta.
Observado también el patrón de cierre tras syncs concurrentes de varios instrumentos.

**Estado:** F3.7 **mitigó** (mejora de estabilidad: >18 min en sesiones previas) pero
**no elimina**. Es un problema de robustez del dev-stack, no de los refactors F4·8.

**Opciones de hardening (pendientes de valorar):**

- (a) Mantener Vite vivo ante `http proxy error` (p.ej. `server.proxy.configure` que
  anule la propagación del error / reintento).
- (b) Limitar la concurrencia de `sync` en cliente (cola/rate-limit) para no saturar la API.
- (c) Separar la API y el proxy (sin proxy por Vite), o usar `workhandle`/manejo de pool.

## 3. Plan exhaustivo de siguientes pasos

Orden propuesto por **valor/menor-riesgo** (los F4·8 son refactors locales, los F3.7
son robustez de entorno). "Poco a poco": cada paso con su batería de verificación.

### P3 — Robustez del dev-stack (F3.7 hardening) ★ **propuesto como más necesario**

- Objetivo: evitar que el crash intermitente de Vite derribe la sesión de trabajo.
- Entregables: (a) o (b) — ver sección 2; + limpieza de huérfanos en `shutdown`.
- Verificación: relanzar el stack, forzar syncs pesados en bucle, comprobar ≥30 min sin
  `ERR_PNPM_RECURSIVE`; tests web + typecheck + lint + build sin regresión.
- Riesgo: bajo-medio. Impacto: alto (elimina interrupciones recurrentes).

### F4.8 — Continuar descomposición de `backtests-page` (5.549 → objetivo <3.500)

- **Paso 3**: extraer el bloque de tabs del render (`setTab` + 4× `HubTabButton`) a un
  sub-componente `BacktestHubTabsBar` (alto valor, bajo riesgo).
- **Paso 4**: extraer hook `useBacktestHubNav` (estado/URL: `tab`, `setTab`,
  `resultFocus`, `runSource`, `patchSearchParams`).
- **Paso 5**: migrar utilidades puras del cuerpo (helpers de copy/labels) a módulos
  con tests.
- **Paso 6**: evaluar si quedan bloques JSX autocontenidos (Lista AUTO panel) para
  extraer a sub-panel.
- Verificación por paso: typecheck + lint + build + tests web.

### F4.9 — Tests smoke sin falso verde

- Revisar que los tests de smoke de backtest realmente ejecutan el flujo (no solo
  comprueban que "no tira error").
- Añadir asserts de invariantes: 0 trades → gate; candle sync real → 200; etc.

### F4.10+ — Higiene no urgente (si la ruta lo permite)

- Reducir warnings de `react-hooks` legado (240 actuales) de forma gradual y selectiva.

## 4. Recomendación

**Abordar P3 (hardening F3.7) ahora** antes de seguir con F4·8, porque:

1. Es la causa de las interrupciones recurrentes observadas hoy (bloquea el trabajo real).
2. Es acotado y verificable.
3. F4·8 no puede validarse cómodamente en el navegador mientras el stack caiga en sync.

Tras P3, seguir F4·8 paso 3.

> **Recomendación actualizada (2026-08-09, 21:0x):** tras el hallazgo 4c, el paso más
> necesario es **endurecer `run-dev` para que NO muera si Vite cae (autoreinicio de
> Vite / no-propagar exit a todo el stack)**, antes de seguir con F4·8. Es un cambio
> en `scripts/run-dev.mjs` (tope), sin tocar Vite ni la semántica del stack, y ataca
> la incidencia recurrente que bloquea el trabajo.

## 4b. Resultado P3 (2026-08-09, hecho)

**Decisión:** opción (a) — capturar errores del proxy en `vite.config.ts` vía
`server.proxy.configure(proxy => proxy.on('error', ...))`. Esto impide que el
`ECONNRESET` emitido por `http-proxy` al reenviar `/api` a la API se propague como
fallo fatal que derriba el proceso Vite.

**Cambio:** `apps/web/vite.config.ts` (solo el bloque `proxy['/api']`).

**Verificación:**

- Stress: 10+ syncs concurrentes de instrumentos reales a través del proxy Vite
  (`POST /api/instruments/{id}/sync`) → todos **200 OK** en la API.
- Stack vivo tras el estrés (`api=200`, `web=200`), **0** `proxy error`/`ECONNRESET`/
  `Deteniendo stack`/`ERR_PNPM` en el log.
- Batería: typecheck ✅ · lint (0 errores) ✅ · build ✅ · **701 tests (139 archivos)** ✅.
- No se observó regresión de build ni de dev.

**Nota:** la causa última (API cerrando conexión en sync pesado) persiste como
fragilidad; P3 la vuelve **no fatal para Vite**. Si reaparece un crash, las opciones
(b) límite de concurrencia de sync y (c) separar proxy quedan documentadas.

## 4c. Hallazgo posterior (2026-08-09, MISMO día, tras P3)

**El crash silencioso de Vite persiste aun con P3.** En la sesión que siguió a P3
(shell `709482`), Vite volvió a salir con `Exit status 1` **sin ningún mensaje
propio en stderr**, derribando el stack (`ERR_PNPM_RECURSIVE_RUN_FIRST_FAIL`).
Lo relevante:

- **No hubo NI UN `proxy error` ni `ECONNRESET`** en todo el log de esa sesión.
- Antes del crash todo era tráfico **200 OK** normal (syncs que completaron, alertas,
  mono-ventana), sin carga extraordinaria.
- Quedaron de nuevo huérfanos (API+Web) sirviendo tras el cierre.

→ **Conclusión:** hay una **segunda vía de crash silencioso "puro" de Vite** (sin
trigger visible en stderr, ni proxy error, ni rastro de memoria/stack en el log),
independiente del `ECONNRESET` que atajó P3. El hardening P3 **no es suficiente**.

Hipótesis a explorar (no probadas aún): problema de la versión de Vite/`http-proxy`
con el chunk grande (~2.5 MB) y su HMR en `strictPort`, o un `uncaughtException`
silencioso ligado a WebSocket/HMR del dev server. Siguientes opciones, en orden:
(a1) subir la versión de Vite; (a2) aislar `run-dev` para que el run-dev NO muera si
Vite cae (que lo **reinicie solo**); (a3) reducir el chunk con code-splitting.
**Recomendación: (a2) hacer a `run-dev` resiliente al exit de Vite (autoreinicio)**
es el de mayor impacto/mejor ratio y no toca la semántica del stack.

## 5. Sincronización con GitHub

Rama: `stage/estudio-membership-operativa-2026-08-04`. Cada paso se commitea y pushea
(con aprobación) para mantener el roadmap recuperable.
