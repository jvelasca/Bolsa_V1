# Criterio de salida de `-beta` — PROPUESTA para ratificación del propietario (2026-10-01)

> **Clase:** **propuesta de política** (docs-only; **SIN bump, SIN tag, CERO `src`, CERO tests**).
> **Autoridad:** el propietario. Este documento **no promueve nada**: fija **qué habría que cumplir**
> para que una versión pueda declararse **estable** (sin sufijo `-beta`).
> **AsOf:** 2026-10-01.
> **Padre:** [`versioning.md`](./versioning.md) (regla 3) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) ·
> [`PROJECT_STATE.md`](./PROJECT_STATE.md).
> **Motivo inmediato:** [`audit-pack-v2.88.17-w4-bundle-direccional-2026-10-01.md`](./audit-pack-v2.88.17-w4-bundle-direccional-2026-10-01.md) §5.

---

## 0. Qué es y qué NO es esta propuesta

**Es** la definición explícita de un término que hoy se usa **sin definición**. **NO es** un hito de
marketing, **no** cambia ningún umbral (`TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B) y **no habilita LIVE**.

El hueco que cierra

`versioning.md` regla 3 dice: «**Bump de package** solo al cerrar una **versión estable**», y añade:
«V1.46 es Paper Desk foundation… **Ninguno es estable**». Y ahí se acaba: **no existe ningún documento
que diga cuándo algo lo es**. Todo el repo va con sufijo `-beta` (hoy `2.11.17.1-beta`), de modo que la
regla 3 **nunca se ha podido aplicar**. Escribir el criterio **antes** de necesitarlo es lo que evita
que la promoción sea un acto de fe.

Y una consecuencia ya medida: `CURRENT_SYSTEM.md` declaraba `AsOf (V2.15)` / package `1.44.0-beta`
mientras el producto iba por `V2.88.17.1` — **36 versiones** de deriva en el documento que el `README`
señala como «estado canónico» al auditor. Un criterio de salida **sin** gobernanza al día es una
contradicción en los propios términos (por eso **G7**).

---

## 1. Definición propuesta de «estable»

Una versión `Vx.y` (sin `-beta`) se declara **estable** cuando su **tag anotado** cumple **las siete
compuertas** de §2. «Estable» significa **«las afirmaciones que el repo hace sobre ella han sido
verificadas por un tercero y siguen siendo verdaderas»** — **nunca** «lista para capital real».

> **`estable ≠ LIVE`.** La promoción de versión y la autorización de LIVE son **decisiones
> independientes**, con dueños distintos (versión = honestidad del artefacto; LIVE = riesgo de capital).

---

## 2. Las siete compuertas

Cada una es **falsable**: trae su modo de verificación. Una compuerta «en curso» no es una compuerta
cumplida.

| # | Compuerta | Verificación |
| --- | --- | --- |
| **G1** | **Auditoría externa APROBADA del tag que se promueve**, con **0 bloqueantes**; las precisiones, **cerradas o declaradas con dueño** | Informe `docs/engineering/auditoria-…md` citando el SHA del tag; `APROBADO` / `APROBADO CON PRECISIONES` |
| **G2** | **CI del tag 100 % verde y SIN tests rojos no ejecutados**: ningún test existe-no-corre | `Release tag CI` `success` (sólo `skipped` por diseño declarado) **y** `rg -n "test_…" .github/workflows` cubre los ficheros de test del repo, o la lista se **deriva** en vez de escribirse a mano |
| **G3** | **Cero deuda declarada BLOQUEANTE**; el resto, con dueño, motivo y disparador | Tabla de deuda ([`deuda-p3-post-auditoria-v2.70-2026-09-26.md`](./deuda-p3-post-auditoria-v2.70-2026-09-26.md) + `OBS-*`): ninguna marcada bloqueante sin cerrar |
| **G4** | **Evidencia operativa real**: ventana PAPER/forward ≥ **N días** con `AUTO_ENGINE_SIM_REAL_PRICE=1` y **material publicado**, con el **denominador de R certificado** | Scripts de material/ventana (`P3-2`/`P3-3`): informe con nº de ciclos, R medible y no medible, y la procedencia (`PAPER real`, no `synthetic_fixture`) |
| **G5** | **Honestidad del dato:** toda cifra citada en los docs es **reproducible por un tercero desde el tag** | Los hashes citados coinciden con el `assert` del CI (no con un render local); las bandas citan su `K` y su IC |
| **G6** | **Ninguna capacidad peligrosa armada por accidente** | `LIVE_EXECUTION_UNLOCKED` off · `PAPER_D_EXECUTE` off · thaw **no** · kill switch y `checkExitPermission` con sus suites verdes |
| **G7** | **Gobernanza al día en el commit promovido** | `CURRENT_SYSTEM.md` con `AsOf` == tag promovido (no una versión anterior) · `versioning.md` con su tabla de las **5 verdades** actualizada · `package.json` bufeado por la regla 3 (es **el** bump que la regla reservaba) |

**N (ventana de `G4`) es decisión del propietario** (§4). Referencia existente en el repo: la ventana
declarada para la deuda de correlación es **≥ 4 días** (`P3-2`), con el `≥32 ciclos` de los cubos.

---

## 3. Estado actual frente a las compuertas (2026-10-01, `v2.88.17.1-beta`)

| # | Estado | Por qué |
| --- | --- | --- |
| G1 | ❌ | Última auditoría externa emitida: **`v2.88.3`** (2026-09-29). `v2.88.4`…`v2.88.17.1` (**~14 versiones**) sin auditar. **Este tramo prepara el paquete** de `v2.88.17.1`, pero el informe **no existe todavía** |
| G2 | ❌ | **`OBS-19` ATACADA en `v2.88.18-beta`:** el censo se **DERIVA** de los workflows (`scripts/ci/test_selection.py` + guarda de 5 tests) y el test de AUTO-23 **ya corre** (denominador de R derivado del fixture). **Sigue en rojo** porque quedan **53** ficheros que **ningún job ejecuta** — **34** `W-G2/2` (**PG**) + **19** `W-G2/3` (**red/E2E**) — **declarados con motivo y tanda** y con la guarda impidiendo que crezca ([`evidence/v2.88.18`](./evidence/v2.88.18/README.md)) |
| G3 | ❌ | `W5` y `W6` sin sellar · regla direccional duplicada en 4 módulos · `P3-5` · `H-4` |
| G4 | ❌ | `P3-2`/`P3-3` **sin arrancar**: el precio real está sellado pero **no medido en operación** |
| G5 | ⚠️ | El par sellado se cita correctamente, pero la evidencia usa también un hash **local** de plataforma (`697526ED…`): declarado, pero es un imán de confusión para un tercero |
| G6 | ✅ | `LIVE_EXECUTION_UNLOCKED` off · `PAPER_D_EXECUTE` off · XTB **PARKED** · sin thaw |
| G7 | ⚠️ | `CURRENT_SYSTEM.md` se pone al día **en este mismo tramo**; `versioning.md` sigue con la tabla de las 5 verdades **congelada en `1.35.0`/`V1.48`** |

⇒ **Lectura honesta: hoy no se cumple ninguna compuerta difícil (G1–G4).** El orden natural que se
deduce de la tabla es: **G2** (es barato y es lo que un auditor mira primero) → **G1** (el paquete ya
está preparado) → **G4** (la ventana PAPER, que es el único modo de que el precio real deje de ser una
capacidad y pase a ser una **medida**) → **G3/G7**.

---

## 4. Decisiones que son del propietario (no técnicas)

1. **¿Se promueve un tag existente o se crea un tag nuevo sin `-beta`?** Propuesta: **tag nuevo**
   (p. ej. `v2.89.0`), sobre el mismo árbol auditado, para que el objeto auditado y el objeto promovido
   sean **el mismo SHA** — y que la promoción sea **citable**, no una convención.
2. **¿Cuántos días es `N` en `G4`?** Referencia en el repo: **≥ 4 días / ≥ 32 ciclos** (`P3-2`).
3. **¿Qué deuda es BLOQUEANTE?** Candidatos a bloquear: `OBS-19` + el test invisible (G2), y la
   ventana PAPER (G4). Candidatos a **no** bloquear: la convergencia de la regla direccional en los 4
   módulos restantes y `W6`.
4. **¿La promoción cambia el régimen de autorización?** Propuesta: **no** — `LIVE` sigue siendo una
   decisión separada y posterior (§1).
5. **¿Se documenta la promoción como enmienda de `versioning.md`** (regla 3 pasa de «no hay criterio» a
   «el criterio es `G1`–`G7`»)? Propuesta: **sí**, en el mismo commit que la promoción.

---

## 5. Qué cambia (y qué no) el día de la promoción

**Cambia:** el sufijo del **producto** y del **tag**; el `version` de `package.json` (**es exactamente
lo que la regla 3 reservaba**); y la **fila de las 5 verdades** en `versioning.md`.

**NO cambia:** ningún umbral · ninguna capacidad · ningún checkbox de riesgo · `LIVE_EXECUTION_UNLOCKED` ·
`PAPER_D_EXECUTE` · el estatus de `PAPER`/`DEMO` · la obligación de auditar cada incremento siguiente
(la serie `W` continúa y **vuelve a empezar** la cuenta de compuertas en el siguiente tag).

**Corolario:** una versión estable **puede volver** a `-beta` si un sello posterior demuestra que una de
las compuertas era falsa. La promoción no es irreversible, pero **sí es revocable sólo con evidencia**.
