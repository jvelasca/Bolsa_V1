# RELEVO / TRASPASO — R-12 Track C (2026-08-21)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1.
> **Propósito:** texto de paso anti-alucinación para el **siguiente chat**. Leer este doc + backlog §0 + `PROJECT_STATE.md` §2ac + premisas ⭐§0 **antes de tocar nada**.
> **Fuente de coordinación:** GitHub [`jvelasca/Bolsa_V1`](https://github.com/jvelasca/Bolsa_V1) `origin/main`. SHA vivo = `git fetch && git rev-parse origin/main` (no asumir un SHA de este fichero).
> **Firma de partida R-12:** `f7a86cc` · implementación Track A+B **`48cc255`** · tag `v1.3.0` → `b778292` · rama `main`. El tip de GitHub puede ser un commit de firma documental posterior: verificar `git rev-parse origin/main`.

---

## 1. Qué está hecho

- Track A (A0–A6) + Track B estudio: **`48cc255`**.
- Track B **APROBADO** por el propietario (2026-08-21), línea a línea: mesa 5 puertas (Universo · Señales · Dictamen · Confirmar · Libro).
- Plan C escrito: `docs/engineering/plan-r12-track-c-frontend-2026-08-21.md`.
- **C1** `5bc51ff` (local; no en GitHub hasta push del propietario): `/confirm` + nav Confirmar + `openHelpAiPlatform({ panel: "supervised-f3" })` → `bolsa:navigate`.
- **C2 en este commit:** nav diaria (Trading · Señales · Confirmar) vs herramientas vs Laboratorio/Asesor; hub Señales; copy Universo en vigilancia. C3–C5 no abiertas.

## 2. NO tocar

`pending-delete` riesgo alto · gobernanza IA · `PAPER_D_EXECUTE` · scheduler-vs-worker · `contract:gen` · producción `ExecuteTrade` cash_before · split `accounts.py` · split `backtests-page.tsx` · fusión `/research`+`/screeners` · frontend **fuera de la fase C viva**.

## 3. Texto de paso (pegar en el chat nuevo)

> CONTEXTO: repo Bolsa_V1, ciclo **R-12**. Lee `docs/engineering/traspaso-relevo-r12-apertura-2026-08-21.md` · `docs/engineering/plan-r12-track-c-frontend-2026-08-21.md` · `docs/engineering/estudio-flujo-semi-vs-tops-2026-08-21.md` · `docs/PROJECT_PREMISES.md` ⭐§0 · `docs/engineering/PROJECT_STATE.md` §2ac · backlog §0.
> Firma: **GitHub `origin/main`** — ejecutar `git fetch && git rev-parse HEAD origin/main` y `git status`. Partida del ciclo: `f7a86cc`. Tag `v1.3.0` → `b778292`.
> Track B **APROBADO**. **C1** `5bc51ff` (local). **C2 en este commit.** Tarea viva: **C3** (AUTO «No disponible (BETA)»). Luego C4 Libro · C5 HELP. Gates (409, ExecuteTrade post-lock, scheduler) siguen en decisión. Coordinación SIEMPRE desde GitHub (commit+push; working tree ≠ estado).
> Batería C2: typecheck web · vitest confirm/nav/`supervised-f3*` · lint zona tocada · grep «Rastreadores» ausente como hub de nav · sin diff OpenAPI.

## 4. Siguiente producto

1. **C3** AUTO de cuenta «No disponible (BETA)». No thaw `PAPER_D_EXECUTE`.
2. Después: **C4** Libro · **C5** HELP.
3. Push C1 `5bc51ff` + C2 a `origin/main` cuando el propietario lo pida.
4. Tag `v1.4.0` / `v1.5.0-beta` **solo** si lo pide.
