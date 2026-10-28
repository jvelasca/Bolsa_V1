# Evidencia `v2.88.169-beta` — la matriz de regresión de fechas ISO imposibles queda simétrica

## 1. Qué publica este sello

Sello de **seguimiento** posterior a `v2.88.168-beta`. No abre frente funcional: cierra la única
observación que dejó abierta la auditoría del commit `3f25b2b2` sobre el defecto de normalización de
fechas ISO imposibles (hallazgo **P2 de fechas**, ya **cerrado** en ese commit) y, además, corrige
un **rojo falso del teardown del E2E integrado AUTO S5** que descubrió el primer intento del CI de
este mismo tag (§4).

- **`Δ motor = 0`**: ninguna regla, indicador ni umbral de señal cambia.
- **`Δ decisión = 0`**: no se decide distinto.
- **`Δ contrato HTTP = 0`**: `contract:check` verde, `openapi.json`/`schema.d.ts` sin tocar.
- **SIN migración nueva**: `head` sigue `058_estudio_daily_proposals`.
- **Cambios de código: test-only** (una prueba unitaria y un helper del fixture E2E).
- **Bump** `2.11.168-beta` → `2.11.169-beta` (+ `meta.bump` de los **13** CLIs;
  `test_dia_d_bump_guard`).

> **Nota de identidad pública.** Las versiones `2.11.166-beta`, `2.11.167-beta` y `2.11.168-beta`
> viajan en el árbol con su `CHANGELOG` y su evidencia, pero **no se publicaron como tag ni como
> audit pack**. Este sello es el primero con tag desde `v2.88.165-beta`, y su pack declara esa
> continuidad (ver §1 del [audit pack](../../audit-pack-v2.88.169-beta-2026-10-28.md)).

## 2. El hallazgo que cierra: la matriz de fechas

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
formato. **La implementación no se toca**: `git diff 3f25b2b2 <tag> --
apps/web/src/features/auto/auto-hold-declarations.ts` sale vacío.

## 4. El primer intento del tag: un rojo falso del teardown (y su corrección)

El primer `Release tag CI` de este sello (run
[`40677571486`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40677571486), sobre `c04b9e3c`)
salió **rojo**: **12** jobs `success`, **1** `failure`
(`playwright (integrated AUTO S5)`) y `certify` arrastrando el fallo. No se cita como verde y queda
documentado.

**Qué pasó, medido en el artefacto `playwright-integrated-auto-s5-timings`:**

1. **Intento 1 del fixture:** `POST /api/instruments/{id}/sync` (proveedor **Yahoo Finance**,
   externo al repo) devolvió `partial` con `0` barras; `ensureMarketDataReady` lo declaró —como debe—
   «precondición de datos» y el primer test quedó **flaky** al pasar en el reintento (una vez
   sincronizadas 765 barras). Ese punto **no** fue la causa del rojo.
2. **Intento 2:** todos los tests pasaron, pero el **teardown** declaró residuo:
   `la cuenta efímera b359f445… sigue existiendo tras el teardown (status=closed, type=simulated)`.
   El log de la API lo desmiente en el orden exacto en que ocurrió:

   ```
   DELETE /api/accounts/b359f445… → 204 No Content
   GET    /api/accounts/b359f445… → 200 OK        (4 ms después)
   ```

   Causa raíz: la sesión de la API comitea al **salir** de su dependencia con `yield`, es decir
   **después** de responder. Un `204` no prueba por sí solo que la fila ya no exista en la lectura
   inmediata. El teardown sondeaba **una vez** y trataba esa carrera de commit como residuo de
   producto.

**Corrección (`W-169-2`, test-only):** el teardown del S5 sondea con **reintentos acotados**
(`probeAccountUntilGone`, 6 intentos × 250 ms) **después** de cada `DELETE` y en la comprobación
final de residuo. No se relaja el gate: si el borrado **no** ocurre, el sondeo agota sus intentos y
el residuo sigue siendo **rojo**. Tampoco se oculta el otro síntoma: la dependencia del fixture con
Yahoo queda **declarada** como límite (§7).

> **Qué habría fallado con el arreglo:** nada del producto. Lo que se elimina es un **rojo falso**
> de 4 ms de ventana; lo que se conserva es la afirmación de que la cuenta efímera **no sobrevive**
> al teardown.

## 5. Ficheros

| Capa | Ficheros |
| --- | --- |
| Web · prueba unitaria | `apps/web/src/features/auto/auto-hold-declarations.test.ts` (+1 caso) |
| Web · fixture E2E | `apps/web/e2e/gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts` (`probeAccountUntilGone` + teardown) |
| Bump | `package.json` (raíz) + `meta.bump` de `apps/api-python/scripts/v2_87`, `v2_89`…`v2_100` |
| Docs | `CHANGELOG.md` (§`2.11.169-beta`), `docs/engineering/PROJECT_STATE.md`, este pack, `docs/engineering/audit-pack-v2.88.169-beta-2026-10-28.md` |

## 6. Verificación medida (local, sobre este árbol)

| Comprobación | Resultado |
| --- | --- |
| `vitest run auto-hold-declarations` | **49 passed** / 2 ficheros (`auto-hold-declarations.test.ts` **35**, `auto-hold-declarations-panel.test.tsx` **14**) |
| `pnpm --filter @bolsa/web typecheck` | **OK** (`tsc -b --noEmit`, sin salida) |
| `pnpm --filter @bolsa/web lint` | **0 errores** / 23 avisos (preexistentes) |
| `pytest test_dia_d_bump_guard.py` | **2 passed** |
| `pnpm window:test` | **50 passed** |
| `pnpm contract:check` | **OK** — `openapi.json` y `schema.d.ts` coinciden |

**Medido en el CI del tag (run del sello, §4 del audit pack):** `shared` **855 passed / 99
ficheros** + `window:test` **50 passed** + `freeze OK`; `frontend` **2469 passed / 322 ficheros**,
`lint` **0 errores / 23 avisos**; `python` con `ruff`/`mypy`/`pytest` en verde; `replay-repro`
**`REPRODUCIDO`** ⇒ `Δ decisión = 0` medido por el CI.

## 7. Límites declarados

- **AUTO sigue OFF**; operativa **100 % PAPER virtual**, sin LIVE ni XTB real.
- La ventana PAPER sigue **`INCONCLUSIVE`** (`episodios 0/2`, `ciclos 0/32`): este sello **no la
  mueve** y **no demuestra rentabilidad**.
- **El E2E integrado AUTO S5 depende de un proveedor externo (Yahoo Finance).** Si el `sync` no
  devuelve barras, el fixture lo declara como fallo de precondición **de datos** (no lo convierte en
  `skipped`); con los reintentos de Playwright puede quedar como `flaky` y no tumbar el job, pero el
  sello **no** controla ese proveedor ni lo sustituye por datos sintéticos en CI.
- La prueba de formato fija **el formato**, no la fuente: que un `barTimestamp` llegue imposible es
  un defecto del **productor**, y lo que aquí se garantiza es que la UI **no lo maquilla**.
- Añadir abril a `formatHoldInstant` **no** amplía el alcance de `withoutBarDay`: ese contador sigue
  calculándose sólo cuando se solicita un día.
- El bump mueve `apps`, así que el pin PAPER se **re-ancla** antes del tag y los días anteriores
  quedan **`STALE`**.

## 8. Falsabilidad

| # | Afirmación | Cómo se rompe |
| --- | --- | --- |
| 1 | Abril no se normaliza al 1 de mayo en `formatHoldInstant` | el caso nuevo falla si la función vuelve a devolver `formatDateTimeCompact(new Date(...))` |
| 2 | El sello `2026-04-31` (sin hora) se conserva crudo | el caso falla si se pinta `01 may 2026` |
| 3 | La regla es compartida, no duplicada | `hasIsoDayPrefix` + `isoDay` desaparecen o divergen entre las dos funciones |
| 4 | El cambio de producto es test-only | `git diff 3f25b2b2 <tag> -- apps/web/src/features/auto/auto-hold-declarations.ts` sale **vacío** |
| 5 | El teardown no tolera residuo real | `probeAccountUntilGone` agota sus 6 intentos y el `afterAll` sigue lanzando si la cuenta sobrevive |
| 6 | El bump es coherente | `test_dia_d_bump_guard` falla si un `meta.bump` difiere de `package.json` |
| 7 | El contrato no cambia | `pnpm contract:check` falla |
