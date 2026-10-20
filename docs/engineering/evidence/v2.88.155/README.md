# Evidencia `v2.88.155-beta` — cierre de las dos observaciones de la auditoría de `.154`

> **Naturaleza:** sello **posterior y acotado** a `v2.88.153-beta`/`v2.88.154-beta`.
> **`Δ motor = 0`** · **`Δ decisión = 0`** · **`Δ contrato HTTP = 0`** · **sin migración**
> (head `057_top3_opportunity_identity`).
>
> **Bump** `2.11.154-beta` → **`2.11.155-beta`** (+ `meta.bump` de los **13** CLIs) y tag
> anotado **`v2.88.155-beta`**. La evidencia publicada de `.153` y `.154` **no se reescribe**.
> **AUTO sigue OFF** y la ventana PAPER sigue **`INCONCLUSIVE`**: un CI verde no certifica
> rentabilidad.

## 1. Qué publica este sello

Dos hallazgos de la auditoría externa sobre `.154`, **ambos de presentación/documentación**:

| # | Severidad | Hallazgo | Cierre |
| --- | --- | --- | --- |
| **P2** | `P2` | El rótulo de la estrategia **ejecutada** concatenaba `v` a mano ⇒ `vv1` con versión `v1` y `vSin dato todavía` en el hueco. | Reutiliza `versionLabel(...)` + `data-testid` estable + test de regresión de tres casos. |
| **P3** | `P3` | El audit pack publicado declaraba `22290ca2` como base de `.153`. | Corregido en §1 y §7 del release, **con nota visible de corrección fechada**. |

Ninguno toca motor, decisión, contrato ni esquema: el único árbol que se mueve es `apps`
(por el `meta.bump` de los CLIs, **no** por la UI) y `packages` queda **idéntico**.

## 2. P2 — el rótulo de la estrategia EJECUTADA duplicaba el prefijo

**Defecto.** En `apps/web/src/features/auto-monitor/estudio-chain-evidence.tsx` la línea
«Ejecutada (ciclo)» hacía:

```tsx
{textOrAbsent(cycle.executed.strategyPresetKey)} · v
{textOrAbsent(cycle.executed.strategyVersion)}
```

Las otras tres líneas de identidad del mismo componente ya llamaban a `versionLabel(...)`, que
solo prefija `v` cuando la versión no lo trae. El fixture de la batería declara
`executed.strategyVersion: "v1"`, así que el camino estaba **vivo** y la ficha podía mostrar
`vv1`; con el hueco, `vSin dato todavía`.

**Corrección.**

```tsx
<span className="font-mono" data-testid="estudio-chain-executed-strategy">
  {textOrAbsent(cycle.executed.strategyPresetKey)} ·{" "}
  {versionLabel(cycle.executed.strategyVersion)}
</span>
```

El `data-testid` es necesario para asertar **esa** línea: «Declarada por el valor» ya usaba
`versionLabel(...)` y una aserción sobre el bloque la satisfaría sin probar nada.

**Regresión.** Test nuevo en `estudio-daily-ops-panel.test.tsx` (`structuredClone(CHAIN)` sobre
tres copias): `v1` → `estudio_auto · v1`; `1` → `estudio_auto · v1`; `null` → `Sin dato todavía`.
Se prohíben `vv1`, `v1v1` y `vSin`. Panel: **22 passed** (antes 21).

## 3. P3 — el SHA base del audit pack publicado era falso

**Defecto.** El cuerpo del GitHub Release de `.154` declaraba `22290ca2` como base en la tabla
de identidad (§1) y en la fila 1 de la tabla de falsabilidad (§7). Ese commit **no** es el de
`v2.88.153-beta`.

**Valor real, medido.**

```bash
git cat-file -p v2.88.153-beta    # objeto de tag 5a724765422ba168c12c5c6d4f4978ee759e393f
git rev-parse v2.88.153-beta      # 5a724765422ba1…
git rev-parse 'v2.88.153-beta^{}' # 2af7f0d9dc3c93c1a80bbcf44cc3fc064c6c1a1a
git rev-list --left-right --count 'v2.88.153-beta...v2.88.154-beta'   # 0	7
```

El comparador `.153 → .154` da **0 por detrás / 7 por delante**: la base correcta es `2af7f0d9`.

**Corrección.** Se edita el **cuerpo del release** (`gh release edit --prerelease`): §1 pasa a
`v2.88.153-beta` → tag `5a724765` → commit `2af7f0d9`; §7 pasa a
`(tag 5a724765, commit 2af7f0d9)`; y se añade en §1 una **nota visible de corrección fechada**
que declara el valor previo erróneo, para que el cambio sea auditable en vez de silencioso.
Verificado sobre el cuerpo publicado: `22290ca2` aparece **solo** en esa nota, el release sigue
`pre-release` y sigue colgado del tag de `.154` (`170a79e8` → `e3bcbe86`).

**Sin efectos sobre el sello.** No se mueve ningún tag, no se tocan assets ni el run y la
evidencia de `.153` no se reescribe. No hay evidencia de que el error alterase código funcional.

## 4. Verificación medida

| Comprobación | Resultado |
| --- | --- |
| `vitest src/features/auto-monitor` | **21 ficheros / 170 tests** (panel **22**, uno más que en `.154`) |
| `pnpm --filter @bolsa/web typecheck` | **OK** |
| `pnpm --filter @bolsa/web lint` | **0 errores** (23 avisos preexistentes) |
| `contract:check` | **OK** (sin diff: no hay cambio de contrato) |
| Guardián de bump (`test_dia_d_bump_guard.py`) | **2 passed** |
| `pnpm window:freeze` | **`freeze OK`** |
| `pnpm window:test` | **50 passed** |

No hay migración ni cambio de esquema: `packages` **no** se mueve.

## 5. Límites declarados (sin fabricar)

- **AUTO sigue OFF.** No se enciende la cadencia.
- La ventana PAPER sigue **`INCONCLUSIVE`** y **`CONFIRMED` no se emite**.
- Operativa **100 % SIM**; el bridge LIVE no se abre.
- Este sello **no** cierra la brecha funcional: el parte diario ESTUDIO sigue **sin** compartir
  identidad (`presetKey="estudio_auto"`, `strategyVersion=1`, `decisionId` descartado) y el DTO
  del ciclo sigue sin publicar `planId`/`signalId`.
- La verificación DÍA-D del arnés de `.154` sigue siendo una fila **derivada del ciclo**, no un
  replay real.
- Tag **anotado, unsigned**.

## 6. Freeze

El bump mueve `apps` —el `meta.bump` de los **13** CLIs vive en `apps/api-python/scripts`— ⇒ el
pin PAPER se **re-ancla** al árbol del sello (`apps 5fccc568…` / `packages be243531…`, sin
cambio) para que el run de las 18:00 no aborte con `TREE_MOVED`; `pnpm window:freeze` ⇒
**`freeze OK`** y `pnpm window:test` **50 passed**.

## 7. Publicación

Se publica como `v2.88.155-beta` (anotado, unsigned) sobre el commit de **re-anclaje del pin**
inmediatamente posterior al commit del sello, igual que en `.154`: el gate `window:freeze` del
job `shared` es **fail-closed** y el tag no puede apuntar a un commit cuyo pin no case con su
árbol.

La **cita POST-TAG** con el run de `Release tag CI` se añade en un commit posterior sobre
`main` (patrón del repo: el tag no se mueve después de publicado y la evidencia se publica
encima). **Un CI verde no certifica rentabilidad**: AUTO sigue OFF y la ventana PAPER sigue
`INCONCLUSIVE`.
