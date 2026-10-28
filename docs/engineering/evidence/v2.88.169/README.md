# Evidencia `v2.88.169-beta` — la matriz de regresión de fechas ISO imposibles queda simétrica

## 1. Qué publica este sello

Sello de **seguimiento** posterior a `v2.88.168-beta`. No abre frente funcional: cierra la única
observación que dejó abierta la auditoría del commit `3f25b2b2` sobre el defecto de normalización de
fechas ISO imposibles (hallazgo **P2 de fechas**, ya **cerrado** en ese commit).

- **`Δ motor = 0`**: ninguna regla, indicador ni umbral de señal cambia.
- **`Δ decisión = 0`**: no se decide distinto; el único cambio de código es **test-only**.
- **`Δ contrato HTTP = 0`**: `contract:check` verde, `openapi.json`/`schema.d.ts` sin tocar.
- **SIN migración nueva**: `head` sigue `058_estudio_daily_proposals`.
- **Bump** `2.11.168-beta` → `2.11.169-beta` (+ `meta.bump` de los **13** CLIs;
  `test_dia_d_bump_guard`).

> **Nota de identidad pública.** Las versiones `2.11.166-beta`, `2.11.167-beta` y `2.11.168-beta`
> viajan en el árbol con su `CHANGELOG` y su evidencia, pero **no se publicaron como tag ni como
> audit pack**. Este sello es el primero con tag desde `v2.88.165-beta`, y su pack declara esa
> continuidad (ver §4 del [audit pack](../../audit-pack-v2.88.169-beta-2026-10-28.md)).

## 2. El hallazgo que cierra

La corrección de `3f25b2b2` es correcta y compartida: `formatHoldInstant` y `formatHoldBarDay`
conservan crudo el sello con forma ISO y día imposible, en vez de pintar el día que `new Date`
habría inferido. La cobertura, sin embargo, **no era simétrica**:

| Función | Febrero (`2026-02-31`) | Abril (`2026-04-31`) |
| --- | --- | --- |
| `formatHoldInstant` | cubierto (sello con hora y sin hora) | **no cubierto** |
| `formatHoldBarDay` | cubierto (sello con hora y sin hora) | cubierto (y control `not.toContain("may")`) |

La implementación ya aplicaba la misma validación a los dos casos —el desbordamiento de abril
(`2026-04-31` → 1 de mayo) lo rechaza el mismo `isoDay`—, así que el hueco era de **matriz de
regresión**, no de comportamiento: una regresión futura que sólo rompiera abril en
`formatHoldInstant` no habría hecho fallar ninguna prueba.

Este sello cierra el hueco con una prueba nueva y **no** toca la implementación.

## 3. La prueba añadida

`apps/web/src/features/auto/auto-hold-declarations.test.ts` · bloque `formatHoldInstant`:

```ts
it("un mes de 30 días no se desborda al mes siguiente", () => {
  // `new Date("2026-04-31")` la normaliza al 1 de mayo: tampoco aquí se inventa un instante.
  expect(formatHoldInstant("2026-04-31T00:00:00Z")).toBe("2026-04-31T00:00:00Z");
  expect(formatHoldInstant("2026-04-31")).toBe("2026-04-31");
  // Control negativo: el sello no se pinta con el día que `new Date` habría inferido.
  expect(formatHoldInstant("2026-04-31T00:00:00Z")).not.toContain("may");
});
```

Qué fija:

1. **Sello con hora** (`2026-04-31T00:00:00Z`): se devuelve **byte a byte**, no formateado.
2. **Sello sólo día** (`2026-04-31`): se devuelve crudo, no como `01 may 2026`.
3. **Control negativo**: el texto pintado no contiene `may`; si una regresión volviera a delegar en
   `new Date`, la prueba falla por el valor esperado **y** por el control.

La matriz queda simétrica: febrero y abril, con hora y sin hora, en **las dos** funciones de
formato.

## 4. Ficheros

| Capa | Ficheros |
| --- | --- |
| Web · prueba | `apps/web/src/features/auto/auto-hold-declarations.test.ts` (+1 caso) |
| Bump | `package.json` (raíz) + `meta.bump` de `apps/api-python/scripts/v2_87`, `v2_89`…`v2_100` |
| Docs | `CHANGELOG.md` (§`2.11.169-beta`), `docs/engineering/PROJECT_STATE.md`, este pack, `docs/engineering/audit-pack-v2.88.169-beta-2026-10-28.md` |

**No** se toca `apps/web/src/features/auto/auto-hold-declarations.ts`: la implementación del sello
anterior se conserva íntegra.

## 5. Verificación medida (local, sobre este árbol)

| Comprobación | Resultado |
| --- | --- |
| `vitest run auto-hold-declarations` | **49 passed** / 2 ficheros (`auto-hold-declarations.test.ts` **35**, `auto-hold-declarations-panel.test.tsx` **14**) |
| `pnpm --filter @bolsa/web typecheck` | **OK** (`tsc -b --noEmit`, sin salida) |
| `pnpm --filter @bolsa/web lint` | **0 errores** / 23 avisos (preexistentes, sin cambios) |
| `pytest test_dia_d_bump_guard.py` | **2 passed** |
| `pnpm window:test` | **50 passed** |
| `pnpm contract:check` | **OK** — `openapi.json` y `schema.d.ts` coinciden |

La verificación de este sello es **dirigida** por decisión del propietario; las suites completas
(`web`, `shared`, `pytest` completo) las ejecuta el `Release tag CI` del tag y su resultado se cita
en el audit pack §4. Este documento **no** adelanta cifras que no se hayan medido.

## 6. Límites declarados

- **AUTO sigue OFF**; operativa **100 % PAPER virtual**, sin LIVE ni XTB real.
- La ventana PAPER sigue **`INCONCLUSIVE`** (`episodios 0/2`, `ciclos 0/32`): este sello **no la
  mueve** y **no demuestra rentabilidad**.
- La prueba fija **el formato**, no la fuente del sello: que un `barTimestamp` llegue imposible es
  un defecto del productor, y lo que aquí se garantiza es que la UI **no lo maquilla**.
- Añadir abril a `formatHoldInstant` **no** amplía el alcance de `withoutBarDay`: ese contador sigue
  calculándose sólo cuando se solicita un día.
- El bump mueve `apps`, así que el pin PAPER de la ventana queda **`STALE`** hasta el re-anclaje
  POST-TAG; los días anteriores **no** se reinterpretan.

## 7. Falsabilidad

| # | Afirmación | Cómo se rompe |
| --- | --- | --- |
| 1 | Abril no se normaliza al 1 de mayo en `formatHoldInstant` | el caso nuevo falla si la función vuelve a devolver `formatDateTimeCompact(new Date(...))` |
| 2 | El sello `2026-04-31` (sin hora) se conserva crudo | el caso falla si se pinta `01 may 2026` |
| 3 | La regla es compartida, no duplicada | `hasIsoDayPrefix` + `isoDay` desaparecen o divergen entre las dos funciones |
| 4 | El cambio es test-only | `git diff 3f25b2b2 HEAD -- apps/web/src/features/auto/auto-hold-declarations.ts` sale vacío |
| 5 | El bump es coherente | `test_dia_d_bump_guard` falla si un `meta.bump` difiere de `package.json` |
| 6 | El contrato no cambia | `pnpm contract:check` falla |
