# Premisas para continuar la auditoría de la APP — 2026-08-09

Documento vivo de arranque para un **nuevo hilo de trabajo** que siga auditando la
aplicación "poco a poco", sin romper nada, manteniendo el contexto global y en
sincronía con GitHub (para poder recuperarlo todo si se pierde algo).

Úsalo como **prompt de contexto** al abrir el nuevo chat. Sustituye `../README.md`
por el enlace real del documento cuando lo tengas a mano.

---

## 1. Advertencia operativa (LEER PRIMERO)

- **No tocar código a la ligera.** Cada paso de cambio se decide, se propone y se
  valida con la **batería completa** antes de committear: `typecheck` + `lint`
  (0 errores) + `build` + `test` web.
- **Poco a poco.** Pasos pequeños, de bajo riesgo, medibles. Si un paso implica
  tocar muchos sitios o reescribir una pieza muy entrelazada, se desaconseja y se
  propone una alternativa más acotada.
- **Contexto total.** Antes de trabajar se repasa el estado global (docs de
  roadmap/continuación + git). No perder el hilo.
- **GitHub siempre sincronizado.** Todo lo real se commitea y, con aprobación, se
  pushea a la rama habitual para que sea recuperable.

## 2. Estado del repositorio (referencia de partida)

- Rama de trabajo: `stage/estudio-membership-operativa-2026-08-04`.
- Último commit confirmado y pusheado: `6c53302` (F4·8 paso 3: `BacktestHubTabsBar`).
- El árbol debe estar limpio y en sincronía con `origin/<rama>`.
- Actualmente: **139 archivos de test / 703 tests en verde** (web).

## 3. Documentos de referencia (leer antes de trabajar)

- `docs/engineering/improvement-roadmap-post-audits-2026-08-02.md` — roadmap de
  fases Q0–Q3 (roadmap principal de mejoras).
- `docs/engineering/dev-continuation-plan-2026-08-09.md` — documento vivo de
  continuación: registro de commits, hallazgo del dev-stack F3·7, y plan
  exhaustivo de siguientes pasos con priorización. **Es el punto de partida para
  cuadrar qué sigue.**
- `docs/README.md` y `README.md` — visión general (el usuario suele tener
  `docs/README.md` abierto).

## 4. Líneas de trabajo en curso (para elegir el siguiente paso)

Prioridades razonadas al cierre de sesión (2026-08-09):

- **F4·8 — Descomposición de `backtests-page.tsx`.**
  - Hecho: pasos 1 (`backtest-hub-nav`), 2 (`HubTabButton`), 3 (`BacktestHubTabsBar`).
  - `backtests-page.tsx`: 5.792 → **5.530** líneas.
  - **Paso 4 (aplazado / a decidir):** extraer `useBacktestHubNav` completo.
    ⚠️ Riesgo alto: ~20 usos de `setTab`, dependencias de `pathname`/`setSelectedId`,
    poca reducción real de líneas. **Se desaconseja tal cual.** Alternativas:
    - Aparcar F4·8 y revisar otro frente de valor (F4·9, hardening F3·7).
    - Versión reducida `useBacktestTabNav` (solo `tab` + `patchSearchParams`),
      acotada y de bajo riesgo.
- **F4·9 — Tests smoke sin falso verde.** Revisar que los smoke de backtest
  ejecutan el flujo real y no solo "no tira error"; añadir asserts de invariantes
  (0 trades → gate, candle sync real → 200, etc.).
- **F3·7 (residual) — Robustez del dev-stack.** Aunque mitigado con autoreinicio de
  Vite + proxy catch, existe un crash "puro" silencioso de Vite sin rastro en
  stderr. Hipótesis: versión de Vite/http-proxy, chunk grande (~2,5 MB) y HMR en
  `strictPort`, o `uncaughtException` ligado a WebSocket/HMR. Opciones (sin orden):
  subir Vite, aislar `run-dev` (ya parcial), code-splitting del chunk.
- **F2·6/F4·10+: higiene.** Reducir warning de `react-hooks` legado de forma
  gradual (no urgente).

**Criterio de decisión:** priorizar pasos de **valor alto y riesgo bajo**, validados
con la batería completa.

## 5. Batería de verificación estándar (por cada paso)

En `apps/web`:

```bash
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web lint      # 0 errores
pnpm --filter @bolsa/web test
pnpm --filter @bolsa/web build
```

- Probar la app dev si el cambio afecta a UI (Vite con HMR; comprobar que no salen
  `proxy error`/`ECONNRESET`/`Deteniendo stack` en el log del stack).
- Tras cada paso: registrar en `dev-continuation-plan-2026-08-09.md` y, con
  aprobación, commit + push.

## 6. Próximo paso sugerido

Dado que F4·8 paso 4 es de riesgo alto y poca ganancia, **recomendación**: mover a
**F4·9 (tests smoke sin falso verde)** o **hardening residual F3·7** (opción de mayor
impacto: code-splitting / subir Vite), y dejar F4·8 para pasos más marginales o
suspenderlo. Confirmar con el usuario cuál abordan.

## 7. Hallazgo recurrente F3·7 (resumen autosuficiente para el nuevo hilo)

**Síntoma:** el stack `run-dev` cae de forma intermitente bajo carga de `sync`.
Históricamente el patrón era:

```text
[vite] http proxy error: /api/instruments/{id}/sync
Error: read ECONNRESET
```

seguido de `ERR_PNPM_RECURSIVE_RUN_FIRST_FAIL` y `Deteniendo stack (exit=1)`,
quedando procesos huérfanos (API + Vite) sirviendo.

**Qué se ha mitigado (no eliminado del todo):**

- Arranque API→Web (evita `ECONNREFUSED` de Vite contra una API aún no lista).
- Limpieza de puertos en `run-dev` (`ensureStackPortsFree`) + `taskkill /T /F`.
- `spawnPnpm` ejecuta `node pnpm.cjs` directamente (sin `cmd.exe`), para mejor
  propagación de señales y cierre de árbol en Windows.
- Vite captura los errores del proxy (`server.proxy.configure`) para que un
  `ECONNRESET` no propague a fallo fatal.
- **Autoreinicio de Vite** en `run-dev`: si Vite muere tras haberse iniciado, se
  mantiene la API y se relanza Vite a los ~1 s en vez de derribar el stack.

**Pendiente (crash "puro" sin rastro):** hay una segunda vía de crash silencioso de
Vite (exit 1 sin stderr, sin `proxy error` ni `ECONNRESET` previo). No está resuelta.
Hipótesis y opciones en la sección 4 (F3·7 residual).

## 8. Logros consolidados (2026-08-02 → 2026-08-09)

Registro de lo cerrado y verificado, para tener el sesgo al abrir el nuevo hilo:

- **F1·3** — CI frontend (typecheck + lint + test + build) en GitHub Actions.
- **F1·4** — Pre-commit con husky + lint-staged (prettier + eslint --fix).
- **F1·5** — Refuerzo de `.gitignore` y `.gitattributes` (line-endings LF).
- **F2·6** — Quitar secretos por defecto (auth_secret, BD) en `config.py` + tests.
- **F3·7** — Endurecer `run-dev`: arranque API→Web, limpieza de puertos, `spawnPnpm`
  con `node`, autoreinicio de Vite. (Mitigado — ver sección 7.)
- **F4·8 (pasos 1-3)** — Descomposición de `backtests-page`: `backtest-hub-nav`,
  `HubTabButton`, `BacktestHubTabsBar`. Reducción 5.792 → 5.530 líneas, con tests.
- **Estudio/membership (previo)** — Actualización automática al añadir valores a
  ESTUDIO, pausa suave (soft-pause) con checkpoints y reanudación, y estatus
  "Termina X y para…" en el banner.
- **Cierre de sesión** — 139 archivos / **703 tests en verde**; GitHub sincronizado.

---

_Documento de premisas para nuevo hilo. 2026-08-09._
