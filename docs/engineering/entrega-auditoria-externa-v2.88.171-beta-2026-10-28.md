# Entrega para auditoría externa — `v2.88.171-beta`

> **Objeto entregado:** tag anotado `v2.88.171-beta` (identidad en §7).
> **Rama:** `ui/auto-hold-provenance-2026-10-28` (**no** `main`).
> **Naturaleza:** **acto nuevo de publicación documental**. No es una auditoría, no es un sello de
> corrección y no reabre `.169` ni `.170`. No cambia motor, decisión, contrato HTTP, UI ni
> migraciones. **No** abre PR ni fusiona a `main`.
> **Para quién:** auditor externo que no conoce la historia del repositorio y necesita un punto de
> entrada único, verificable y con sus límites escritos.

---

## 0. Qué recibe el auditor (y qué no)

Este documento **no** es un dictamen. Es un **índice verificable** de un expediente ya publicado y
una declaración explícita de procedencia: qué se midió, qué se cita y qué queda fuera.

| Afirmación                                                             | Procedencia                                          | ¿Re-verificada al escribir esto? |
| ---------------------------------------------------------------------- | ---------------------------------------------------- | -------------------------------- |
| El repositorio es **público**                                          | `gh repo view`                                       | **Sí**                           |
| `origin/main` = `26250187` y su `package.json` está en `2.11.160-beta` | `git show origin/main:package.json`                  | **Sí**                           |
| `v2.88.170-beta` = objeto `3e794841…` → commit `babfe228…`             | `git rev-parse` sobre los refs del tag               | **Sí**                           |
| `v2.88.169-beta` = objeto `d31df9b3…` → commit `3ce94048…`             | `git rev-parse` sobre los refs del tag               | **Sí**                           |
| El último GitHub Release **antes** de este acto era `v2.88.165-beta`   | `gh release list`                                    | **Sí**                           |
| El corpus `.170` **no** está en `origin/main`                          | `git merge-base --is-ancestor`                       | **Sí**                           |
| CI, recuentos de suites y enlaces del corpus `.170`                    | **Evidencia aportada** en su acta, no re-medida aquí | **No**                           |
| `Release tag CI` y GitHub Release de **este** sello                    | Medidos POST-TAG; citados en §7                      | **Sí** (§7)                      |

Consecuencia práctica: lo verificable **sin confiar en nadie** es la **identidad del objeto**, el
**alcance del diff** y la **posición de `main`**. Lo relativo a runs de CI del corpus anterior se
acepta **como evidencia aportada** por quien lo firmó.

---

## 1. Índice del expediente (todo dentro del árbol del tag)

### 1.1 El sello `.170` — objeto certificado anterior

| Documento                                                                                                        | Qué es                                                             |
| ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| [`audit-pack-v2.88.170-beta-2026-10-28.md`](./audit-pack-v2.88.170-beta-2026-10-28.md)                           | Pack de auditoría del sello `.170`                                 |
| [`dictamen-tecnico-v2.88.170-beta-2026-10-28.md`](./dictamen-tecnico-v2.88.170-beta-2026-10-28.md)               | Dictamen técnico: acepta `P2-01`/`P2-02` y fija **cuatro límites** |
| [`auditoria-independiente-v2.88.170-beta-2026-10-28.md`](./auditoria-independiente-v2.88.170-beta-2026-10-28.md) | Auditoría independiente desde un clon limpio del tag               |
| [`auditoria-ui-operativa-profunda-2026-10-28.md`](./auditoria-ui-operativa-profunda-2026-10-28.md)               | Acta que originó el sello (POST-TAG, read-only)                    |
| [`respuesta-auditoria-ui-operativa-2026-10-28.md`](./respuesta-auditoria-ui-operativa-2026-10-28.md)             | Respuesta hallazgo a hallazgo, con prueba y límite                 |
| [`evidence/v2.88.170/README.md`](./evidence/v2.88.170/README.md)                                                 | Evidencia del sello                                                |

### 1.2 El cierre documental de `.170`

| Documento                                                                                                                      | Qué es                                                                   |
| ------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------ |
| [`acta-cierre-documental-v2.88.170-beta-2026-10-28.md`](./acta-cierre-documental-v2.88.170-beta-2026-10-28.md)                 | Acto de aceptación del cierre documental **sobre la evidencia aportada** |
| [`adenda-precision-filtros-paths-v2.88.170-beta-2026-10-28.md`](./adenda-precision-filtros-paths-v2.88.170-beta-2026-10-28.md) | Por qué el corpus no disparó CI (causa triple)                           |

### 1.3 Auditoría externa de `.169`

| Documento                                                                                            | Qué es                                |
| ---------------------------------------------------------------------------------------------------- | ------------------------------------- |
| [`auditoria-externa-v2.88.169-beta-2026-10-28.md`](./auditoria-externa-v2.88.169-beta-2026-10-28.md) | Contraste de identidad y CI de `.169` |

### 1.4 Este acto

| Documento                                                        | Qué es                                      |
| ---------------------------------------------------------------- | ------------------------------------------- |
| [`CHANGELOG.md`](../../CHANGELOG.md) §`2.11.171-beta`            | Declaración del acto nuevo                  |
| [`PROJECT_STATE.md`](./PROJECT_STATE.md)                         | Bloque `AsOf (V2.88.171-beta)` al principio |
| [`evidence/v2.88.171/README.md`](./evidence/v2.88.171/README.md) | Evidencia y falsabilidad de este sello      |

---

## 2. Cómo obtener el objeto

```bash
git clone https://github.com/jvelasca/Bolsa_V1.git
cd Bolsa_V1
git fetch --tags
git checkout v2.88.171-beta
```

**Un clon por defecto entrega `main`, que no contiene este expediente.** Para el corpus completo,
nombrando la rama:

```bash
git clone --branch ui/auto-hold-provenance-2026-10-28 https://github.com/jvelasca/Bolsa_V1.git
```

---

## 3. Qué certifica este acto y qué no

| Ámbito                                    | Dictamen                                                                                                                     |
| ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| **Publicación**                           | **Sí**: existe un objeto etiquetado, con notas de Release y un punto de entrada                                              |
| **Trazabilidad**                          | **Sí**: tag anotado → commit → árbol, verificable con `git rev-parse`                                                        |
| **Alcance del diff**                      | **Sí**: `package.json`, los 13 `meta.bump`, `CHANGELOG`, `docs/` y el pin (`scripts/lib/window-forward.mjs`). Nada funcional |
| **Rentabilidad**                          | **No**. AUTO **OFF**; PAPER **`INCONCLUSIVE`** (`episodios 0/2`, `ciclos 0/32`)                                              |
| **P&L neto de comisiones**                | **No**. `P2-03` **abierto**                                                                                                  |
| **Multidivisa**                           | **No**. `P2-11` **abierto**                                                                                                  |
| **Typecheck reproducible en clon limpio** | **No**. `R-170-1` **abierto**                                                                                                |
| **Alineación de `main`**                  | **No**. `main` sigue en `2.11.160-beta`; este acto no fusiona                                                                |
| **Re-certificación de `.169`/`.170`**     | **No**. Sus objetos quedan **intactos** y sus actas no se reescriben                                                         |

---

## 4. Hallazgos abiertos y cómo se tratan

| Hallazgo            | Qué exige                                                                                   | Estado       |
| ------------------- | ------------------------------------------------------------------------------------------- | ------------ |
| **`R-170-1`**       | Generar Prisma en el camino de `typecheck` o documentar el paso como precondición explícita | **Abierto**  |
| **`P2-03`**         | Decidir y ejecutar la etiqueta de base financiera (bruto/neto) del P&L no realizado         | **Abierto**  |
| **`P2-11`**         | Conversión de divisa en `marginUsed` y en los totales de cartera                            | **Abierto**  |
| `P2-05…P2-12`, `P3` | Según el dictamen de `.170`                                                                 | **Abiertos** |

**No se abre ningún issue en este acto.** Si más adelante se abren, deben enlazar al dictamen y al
acta de `.170`, y no sustituirlos.

---

## 5. Invariantes que este acto no cambia

- `v2.88.169-beta` y `v2.88.170-beta`: **byte-idénticos**, sin re-anotar.
- `main`: **sin** PR ni merge de este expediente.
- AUTO: **OFF**.
- PAPER: **`INCONCLUSIVE`**; rentabilidad **no demostrada**.
- Motor, decisión, contrato HTTP, migraciones y `@bolsa/shared`: **sin cambios**.
- Pin PAPER: re-anclado **solo** porque el bump mueve `apps`; los días anteriores quedan `STALE`.

---

## 6. Cómo se falsa esta entrega

```bash
# §0 — main sigue en 2.11.160-beta
git show origin/main:package.json | grep '"version"'

# §0 — el corpus no está en main
git merge-base --is-ancestor babfe228 origin/main && echo "EN main" || echo "NO en main"

# §0 — los sellos anteriores no se han movido
git rev-parse 'v2.88.169-beta^{tag}' 'v2.88.169-beta^{}'   # d31df9b3… / 3ce94048…
git rev-parse 'v2.88.170-beta^{tag}' 'v2.88.170-beta^{}'   # 3e794841… / babfe228…

# §3 — el diff de este acto no toca producto
git diff --name-only 'v2.88.170-beta^{}' 'v2.88.171-beta^{}'

# §3 — el bump casa con el monorepo
pytest apps/api-python/tests/test_dia_d_bump_guard.py -q

# §3 — el pin casa con el árbol del tag
pnpm window:freeze
```

Si alguno discrepa, **esta entrega es falsa en ese punto** y debe corregirse con un acto nuevo, no
reescribiendo el pasado.

---

## 7. Identidad y publicación (POST-TAG)

| Dato                                   | Valor                            |
| -------------------------------------- | -------------------------------- |
| Tag anotado                            | `v2.88.171-beta`                 |
| Objeto de tag                          | _pendiente de medición POST-TAG_ |
| Commit                                 | _pendiente de medición POST-TAG_ |
| `Release tag CI`                       | _pendiente de medición POST-TAG_ |
| GitHub Release                         | _pendiente de medición POST-TAG_ |
| Commit del corpus `.170` de referencia | `0765960b`                       |

---

## 8. Alcance y no-cambios de este documento

- **No** modifica `apps/`, `packages/`, `.github/`, migraciones ni `operability_runs/` (salvo los
  `meta.bump` de los CLIs de evidencia, que son literales de versión).
- **No** crea, mueve ni re-anota tags distintos de `v2.88.171-beta`.
- **No** reescribe el dictamen, el audit pack, el acta de cierre, la adenda ni la auditoría
  independiente de `.170`: los **indexa**.
- **No** abre ni cierra hallazgos.
