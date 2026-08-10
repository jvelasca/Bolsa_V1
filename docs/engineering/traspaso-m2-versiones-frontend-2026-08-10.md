# Traspaso M2 — Versiones frontend (`@types/react`/`@types/react-dom` + rangos `^`) · 2026-08-10

> **Este documento es el punto de entrada para el chat/hilo que ejecute M2.**
> Resumen ejecutivo del contexto **verificado en el repo y en npm** (2026-08-10, en el hilo M1,
> sin cambios de código). No se re-descubre nada: cada hecho abajo está confirmado.

## 0. Qué es M2 (fuente: `docs/engineering/general-audit-plan-2026-08-10.md` §4/§5)

Fila de la tabla de módulos:

> **M2 — Versiones frontend** | Reconciliar `@types/react`/`react-dom`; revisar rangos `^` amplios | Riesgo Bajo | Prioridad ★★

Orden sugerido: M1 + M2 (reproducibilidad/versiones) atacan la premisa de "revisar versiones tras
el crecimiento". **M1 ya está cerrado** (2026-08-10, `67f8b46` → reproducible backend). M2 es el
siguiente módulo de esa pareja.

## 1. Protocolo sagrado (leer y respetar — mismo que M0/M1/shared)

1. **Tolerancia cero a fallos.** No asumir: verificar siempre en el repo/CI.
2. **Preservación funcional absoluta.** Un cambio solo si es necesario y probado.
3. **Alcance atómico.** Un módulo por hilo; no tocar nada ajeno a M2.
4. **Flujo en 3 fases:** FASE 1 (diagnóstico, sin cambios) → FASE 2 (plan atómico + aprobación del
   usuario) → FASE 3 (ejecución + batería + commit + push + registro). Sin aprobación explícita
   **no se toca código ni se commitea.**
5. **Docs como fuente de verdad.** Anclar decisiones a ficheros reales.
6. «No romper NADA»: batería completa de tests antes y después.

## 2. Hechos de diagnóstico confirmados (FASE 1 ya avanzada, 2026-08-10)

### 2.1 Desalineación `@types/react` vs `@types/react-dom` (CONFIRMADA en `pnpm-lock.yaml`)

Hallazgo del plan 08-10 §4 reproducido **a nivel resuelto** (el `pnpm-lock.yaml` de HEAD):

| Paquete | Resuelto en `pnpm-lock.yaml` | Declarado en `apps/web/package.json` |
| ------- | ----------------------------- | ------------------------------------- |
| `@types/react` | **19.2.17** | `^19.1.6` |
| `@types/react-dom` | **19.2.3** | `^19.1.6` |

> ⚠️ **Matiz clave:** los **rangos ya están alineados** (ambos `^19.1.6`). La desalineación está
> en la **resolución del lock** (`19.2.17` vs `19.2.3`), pese a rangos iguales.

### 2.2 Limitación upstream (verificado en npm, NO reparable subiendo react-dom types)

Consultadas las versiones publicadas en npm (2026-08-10):

| Paquete | latest publicado |
| ------- | ---------------- |
| `@types/react` | **19.2.18** |
| `@types/react-dom` | **19.2.4** (la mayor existente; no hay 19.2.5+… y en el rango `19.2.x` solo llega a `19.2.4`) |
| `react` / `react-dom` | **19.2.8** |

→ **`@types/react-dom` va siempre por detrás de `@types/react`** (limitación topológica de
DefinitelyTyped: los `@types/*` no están 1:1 con el runtime). **No existe** una `@types/react-dom`
que iguale la `19.2.17`/`19.2.18` de `@types/react`. La desalineación `19.2.x` **no es un bug del
repo ni un rango mal puesto**, es estructural.

**Implicación para decidir en M2 (FASE 2):** alinear "a la par" es **imposible** upstream. Las
opciones son: (a) aceptar y documentar la desalineación como limitación, (b) subir ambos a su
`latest` (`@types/react 19.2.18` + `@types/react-dom 19.2.4`), lo que **reduce el gap** (`19.2.18`
vs `19.2.4`) pero NO lo elimina, (c) no tocar nada. Requiere decisión del usuario (no técnica).

### 2.3 Estado frontend actual (HEAD `67f8b46`)

- `apps/web/package.json`: `react ^19.1.0` · `react-dom ^19.1.0` · `@types/react ^19.1.6` ·
  `@types/react-dom ^19.1.6` · `typescript ^5.8.3` · `vite ^6.3.5` · `vitest ^3.2.3` ·
  `@vitejs/plugin-react ^4.5.2` · `tailwindcss ^4.1.8`.
- Resueltos en lock: `react@19.2.7`, `react-dom@19.2.7`, `typescript@5.9.3`.
- `packages/shared/package.json`: `typescript ^5.8.3` (sin `@types/react` dependencia — es TS puro).
- CI frontend: `.github/workflows/frontend-ci.yml` — batería `typecheck` + `lint` + `test` + `build`.

### 2.4 Rango `^` amplios (fuente del plan §4: "revisar rangos ^ amplios")

Con rangos `^`, pnpm resuelve a la **última minor** automáticamente en cada `install`. En la
practica, un rango `^` NO es por sí mismo un riesgo (es la convención de semver para deps); el plan
marca "revisar rangos ^ amplios" como higiene menor. Esperado en M2: auditar si alguna dep quedó con
un `^` que ya no tiene sentido (p.ej. `^19.1.0` de react vs resuelto `19.2.7` es correcto y deseable).
No hay señal de duplicados (1 solo `pnpm-lock.yaml`, auditado en el plan §4: JS/TS coherente).

## 3. Batería de verificación base del módulo (toca frontend)

Del plan 08-10 §5 (Web): `pnpm --filter @bolsa/web typecheck` + `lint` (0 errores) + `test` + `build`.
Global: `pnpm test` (turbo) y confirmación de CI en GitHub — `.github/workflows/frontend-ci.yml` hace
`typecheck + lint + test + build`.

> Nota anterior (08-09, §6.6 dev-continuation-plan): el lint global de `@bolsa/shared` había tenido
> 14 `no-unused-vars` pre-existentes, **ya resueltos** en el mini-módulo shared `8e4ee62`. A M2 no le
> toca eso (se asume verde; verificar igualmente en la batería).

## 4. Frentes concretos a resolver (para el chat M2)

Esto **no** es un plan consensuado, es el diagnóstico heredado + elaborado. El chat M2 debe:

1. **Decidir el tratamiento de la desalineación `@types/react`/`@types/react-dom`** (ver §2.2: la
   opción (b) `pnpm up` a latest reduce el gap; la (a) documenta como limitación; la (c) no tocar).
   Presentar opciones al usuario en FASE 2.
2. **Revisar los rangos `^`** de `apps/web/package.json` y `packages/shared/package.json`: auditar si
   hay rangos que requieran atención (probablemente ninguno — higiene de confirmación). Si se sube
   `@types/*`, `pnpm install` actualizará el `pnpm-lock.yaml`.
3. Mantener **alcance estricto M2** (solo frontend type-versions/rangos; no tocar web por features —
   eso es M5).

## 5. Estado del repo al crear este traspaso (2026-08-10)

- Rama activa: `stage/estudio-membership-operativa-2026-08-04`
- HEAD: `67f8b46` (M1 backend). **Working tree limpio**, sincronizado con `origin/<rama>`.
- M1 cerrado: `uv.lock` commiteado. No hay rama dedicada a M2 todavía; **M1 se hizo en la rama stage
  actual** (decisión previa), recomendable mantener la misma para M2 (preguntar en FASE 2 si se
  prefiere rama de módulo).

## 6. Documentos fuente de verdad / índices

- `docs/engineering/engineering-index-2026-08-03.md`
- `docs/engineering/general-audit-plan-2026-08-10.md` (§4 hallazgos, §5 módulos)
- `docs/engineering/dev-continuation-plan-2026-08-09.md` (§7.1 cierre M1)
- `docs/engineering/traspaso-m1-reproducibilidad-backend-2026-08-10.md` (precedente del patrón)
- `docs/ARCHITECTURE.md` · `docs/DEV_STARTUP.md` · `apps/web/package.json` · `pnpm-lock.yaml`

> Al cierre de M2 (FASE 3), actualizar `dev-continuation-plan-2026-08-09.md` con una sección 7.x
> nueva y añadir este fichero al índice engineering (bajo Product/Ops, junto al de M1).

## 7. Cierre M2 (2026-08-10) — EJECUTADO

- **Rama/estado al arrancar:** `stage/estudio-membership-operativa-2026-08-04`, HEAD real `aa87ad7`
  (este mismo commit de traspaso; el `67f8b46` de M1 es un ancestro). Árbol limpio.
- **Decisión (usuario, FASE 2):** opción (b) — subir ambos `@types` a su `latest` (`@types/react`
  `19.2.18` + `@types/react-dom` `19.2.4`), reconociendo el gap estructural upstream que no se elimina.
- **Cambios:** `apps/web/package.json` (solo los 2 `@types`, a `^19.2.18`/`^19.2.4`) + `pnpm-lock.yaml`
  (integridad + dependientes). Sin tocar código. Rangos `^` auditados → sin cambios.
- **Batería:** typecheck ✅ · lint ✅ (0 errores) · test ✅ (707) · build ✅ · `@bolsa/shared` typecheck ✅ ·
  `pnpm test` (turbo) ✅.
- **Registro:** sección §7.2 en `dev-continuation-plan-2026-08-09.md`; entrada del índice engineering
  marcada CERRADO en `engineering-index-2026-08-03.md`. Commit + push (botón CI en GitHub).
- **Nota entorno:** `pnpm up` no relinkeaba `node_modules` local (estado "lockfile-only"); se sincronizó
  con `pnpm install --force` (aprobado). No reproducible en CI (checkout limpio + `--frozen-lockfile`).
