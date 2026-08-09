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

---

_Documento de premisas para nuevo hilo. 2026-08-09._
