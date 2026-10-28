# Auditoría independiente de `v2.88.170-beta` (contraste contra GitHub)

> **AsOf:** 2026-10-28 · **Objeto:** tag `v2.88.170-beta` ·
> **Método:** clon limpio **del tag desde GitHub** (no del árbol de trabajo), más contraste del CI público y
> de sus artefactos.
> **Naturaleza:** **verificación**, no certificación de producto. No reabre `v2.88.169-beta`, no juzga
> rentabilidad y no convierte los P2/P3 abiertos en cerrados.
> **Veredicto:** los tres criterios del dictamen **pasan con evidencia falsable** (§3), con los límites de §4.

---

## 0. Por qué este documento existe

El dictamen pedía distinguir «lo que se ha reportado» de «lo que un tercero puede contrastar desde GitHub».
El acta de auditoría es estática y POST-TAG; la respuesta del equipo es un documento de intención. Este
documento cierra ese hueco: **todo lo que afirma se ejecutó sobre el código publicado**, y todo lo que no se
pudo ejecutar aquí se dice explícitamente (§4.3).

## 1. Identidad del objeto auditado

| Comprobación | Comando | Resultado |
| --- | --- | --- |
| Tipo de tag | `git cat-file -t v2.88.170-beta` | `tag` (**anotado**, no lightweight) |
| Objeto de tag | `git cat-file -p v2.88.170-beta` | `3e7948417c22bf9e767848331fe0d57fc2154e98` |
| Commit apuntado | `git rev-parse "v2.88.170-beta^{commit}"` | `babfe228f9d81eb2b18be787465af588b5ff170b` |
| Clon del tag | `git clone --branch v2.88.170-beta --depth 1` | `HEAD` = `babfe228` (§ coincide con el tag) |
| Base inmóvil | `git rev-parse "v2.88.169-beta^{commit}"` | `3ce94048b45112d66eb6e3614f2e81676a41be97` — **sin cambios** |
| Versión | `package.json` | `2.11.170-beta` |

El tag **no es lightweight**: a diferencia del sello `.132`, aquí existe objeto de tag con su mensaje, así
que la identidad no depende de anotar un SHA en un documento.

## 2. CI del objeto auditado

| Comprobación | Resultado |
| --- | --- |
| `Release tag CI` [`40727162474`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40727162474) | **`success`** (`run_attempt 1`, `16:33:41Z` → `16:47:32Z`) |
| Jobs | **14 `success`** + **1 `skipped`** (`playwright (integrated E2E, opt-in)`, por diseño) |
| Gate duro de accesibilidad | `playwright (integrated axe)` **`success`** (`16:33:44Z` → `16:38:06Z`) |
| Reproducibilidad | `replay-repro` ⇒ `VEREDICTO REPRODUCIDO` (mismo contenido) |
| Agregado | `certify` **`success`** |
| Artefacto `release-tag-ci-summary` | `id 12834347261`, `sha256:f5a9055b…`, `status: "GREEN"` con los **12** jobs obligatorios en `success` |
| Run de rama previo | `Frontend CI`, `Python CI`, `Optimize lab`, `Fase 2 scientific` sobre `babfe228` ⇒ **`success`** |

El artefacto declara `sha: "babfe228…"` y `tag: "v2.88.170-beta"`: el CI certifica **exactamente** el commit
apuntado por el tag, no otro.

**Sobre el commit POST-TAG (`e77246d2`, solo `docs/`):** no dispara ningún workflow porque los cuatro de rama
están filtrados por `paths` y `docs/**` no está en la lista. No es un hueco de cobertura: el objeto certificado
es `babfe228` y su árbol de `apps`/`packages` es idéntico al de `e77246d2` — `window:freeze` sigue `OK` con los
mismos `appsHash` (`920f21c1…`) y `packagesHash` (`7dafa400…`) después del commit de docs.

## 3. Los tres criterios, uno por uno

### 3.1 Criterio 1 — ausencia de datos frente a error

**Afirmación a contrastar:** una API fallida no puede representarse como colección vacía, saldo cero ni
ausencia de posiciones.

| Evidencia | Qué prueba | Resultado |
| --- | --- | --- |
| `src/components/query-absence.test.ts` | Tabla de precedencia `error > loading > unavailable > empty > ready`; un refetch fallido con datos previos sigue siendo `error` | **9 passed** |
| `history-page-absence.test.tsx` | Movimientos y operaciones con la API caída ⇒ `No disponible`, y el texto de vacío **no** aparece | **3 passed** |
| `operativa-outcomes-absence.test.tsx` | Sesiones caídas ≠ «aún no hay sesiones de este valor» | **3 passed** |
| `use-pending-orders.test.tsx` | La cola ilegible hace que `useInstrumentOrderPending` devuelva `null` (tri-estado), no `false` | **4 passed** |
| `dia-d-trades-panel-absence.test.tsx` | `detail` ausente ⇒ hueco declarado, no `0` operaciones | **3 passed** |
| `dia-d-auto-panel-absence.test.tsx` | `divergent`/`unmeasuredCount`/`limits.length` sin dato ⇒ hueco, no `0` | **2 passed** |
| `ops-incidents-absence.test.tsx` | Consola: `!isError` separa «sin incidentes» de «no se pudo leer» | **2 passed** |
| `mesa-candidates-panel-absence.test.tsx` | Sin ranking no se pinta `Universo 0` ni el CTA acusatorio | (incluida en la suite completa) |
| `mesa-portfolio-absence.test.tsx` | Cartera caída ⇒ no aparece la frase de seguridad «no hay stop que confirmar» | (incluida en la suite completa) |
| `auto-risk-summary.test.ts` (bloque P2-02) | Estado sano + recuento de incidencias **sin leer** ⇒ `Sin dato todavía`, nunca «Controlado» | **9 passed** |

**Falsación mínima:** reintroducir `query.data ?? []` en cualquiera de esas superficies rompe su render test;
reintroducir `fillLinkIssuesCount ?? 0` rompe el bloque P2-02.

**Veredicto del criterio: PASA.**

### 3.2 Criterio 2 — ejecución frente a propuesta

**Afirmación a contrastar:** un fill `skipped` o `unknown` sin `transactionId` no puede presentarse como
operación ejecutada ni borrarse de la cola como si lo estuviera.

| Evidencia | Qué prueba | Resultado |
| --- | --- | --- |
| `pending-order-fill.test.ts` | Tabla de **seis desenlaces**: solo `executed` **con** `transactionId` produce «ejecutada»; `executed` sin transacción **degrada a `unknown`**; `expired` cancela y retira; `skipped`/`unknown`/`submitted`/fuera de vocabulario **no** se anuncian como ejecutadas | **8 passed** |
| Mismo fichero | Solo `executed` y `expired` retiran la orden (`removesOrder`); el resto no es `retryable` | cubierto |

**Falsación mínima:** hacer que la copia de `skipped`/`unknown` imite la de `executed` (o devolver
`removesOrder: true` para ellos) rompe la tabla.

**Veredicto del criterio: PASA.**

### 3.3 Criterio 3 — exactitud financiera

**Afirmación a contrastar:** las comisiones acumuladas tienen alcance histórico explícito, y el tono visual
no altera el signo ni el significado contable del importe.

| Evidencia | Qué prueba | Resultado |
| --- | --- | --- |
| `packages/py/application/tests/test_list_ledger_total_fees.py` | **150 filas `fee` con página de 100** ⇒ el agregado es el total completo, no la página | `pytest` dirigido **4 passed** (con el bump guard) |
| `apps/api-python/tests/integration/test_accounts.py` | El campo `tradeFeesTotal` viaja en la respuesta del ledger | **5 passed** (medido en el árbol; CI `python`/`lifecycle-pg` verdes) |
| `ledger_repository.total_fees_for_account` | Excluye custodia (`reference_type != "custody"`), por diseño declarado | lectura de código |
| `history-page-fees.test.tsx` | 1 fila visible y total **1 234,50** ⇒ la tarjeta pinta el agregado, no `5.00`; cero medido ⇒ `0.00`; API caída ⇒ `No disponible` | **3 passed** |
| Rótulo de la tarjeta | «Comisiones de operaciones (histórico)» + `title` que declara que la custodia se contabiliza aparte | lectura de código + test |
| `history-page-tone.test.tsx` | Fila `fee` ⇒ `data-tone="cost"` y **sin** verde; compra ⇒ `neutral`; venta ⇒ `in` | **2 passed** |
| `portfolio-cash.test.ts` | Mapeo completo de `ledgerAmountTone` | (suite `shared` **861 passed**) |
| `pnl-tone.test.ts` | `null`/`undefined`/`NaN`/`±Infinity` y **cero exacto** ⇒ `neutral`; solo un valor medido distinto de cero declara signo | **5 passed** |
| `mesa-position-row.test.tsx`, `mesa-daily-header-pnl-tone.test.tsx`, `operations-panel-pnl-tone.test.tsx` | El hueco se declara en texto y `data-tone="neutral"` sin verde; el importe conserva su signo (`-50` sigue siendo `-50`) | render tests en verde |

**Falsación mínima:** volver a sumar las filas de la página rompe `history-page-fees`; colorear por
`amount >= 0` rompe `history-page-tone`; volver a `(x ?? 0) >= 0` rompe `pnl-tone` y las tres render tests.

**Veredicto del criterio: PASA**, con el límite de §4.2 (el alcance es «comisiones de operaciones», no
comisiones totales con custodia, y así se rotula).

## 4. Límites de esta auditoría

### 4.1 Lo que **no** he podido verificar aquí

- **El stack completo de UI en navegador** no se ha levantado en este entorno; el gate `axe` integrado y los
  E2E se aceptan por el CI (`playwright (integrated axe)` y `playwright (mock E2E)` en `success`), que es
  evidencia pública y citable, pero **no** es una observación directa mía.
- **`pnpm typecheck` en un clon recién instalado falla en `@bolsa/database`** (`PrismaClient` no generado y
  `process` sin `@types/node`): el cliente Prisma se genera en el pipeline, no en `pnpm install`. El typecheck
  de `@bolsa/shared` y `@bolsa/web` —las capas que toca este sello— sí pasa sin salida, y el job `frontend`
  del CI, que ejecuta el typecheck completo, salió `success`. Se declara para que no se lea como defecto
  oculto.
- **Suites completas de Python**: no se han ejecutado aquí; las ejecuta el `Release tag CI` (`python`,
  `lifecycle-pg`, `a7-gate`, `dr-verify`, todos `success`).

### 4.2 Límites que el propio sello declara y esta auditoría **confirma**

1. Corregir la representación **no** corrige la fuente: un `unknown` de fill sigue siendo un desconocimiento
   real del bróker.
2. El agregado de comisiones mide **operaciones sin custodia**; la custodia va aparte y así se rotula.
3. **P2-03** (bases bruto/neto conviviendo sin etiqueta), **P2-05…P2-12** (día UTC vs local, truncación del
   informe diario, FX, «N posiciones» que incluye las no valoradas, etc.) y los **P3** siguen **abiertos**.
   Este sello no los presenta como cerrados y esta auditoría tampoco los absuelve.
4. `FALSE_ZERO_SURFACES` sigue sin ampliarse a Mesa/Mercado/AUTO: el gate de fuente no se ha endurecido.
5. AUTO **OFF**, operativa **100 % PAPER virtual**, ventana **`INCONCLUSIVE`** (`0/2` episodios, `0/32`
   ciclos): **no se demuestra rentabilidad** ni se autoriza operar con dinero real.

### 4.3 Un reparo honesto sobre el alcance del sello

El dictamen nombra tres criterios; el slice original cerraba siete hallazgos y dejaba `P2-01` y `P2-02`
fuera. Con este cierre, **los tres criterios tienen prueba ancla**, pero dos de las doce familias de P2
siguen tocando cifras de dinero (`P2-03` y `P2-11`). Aceptar el sello significa aceptar que **la afirmación
de un P&L neto o de un patrimonio multi-divisa no está certificada por esta versión**, no que el dinero esté
mal calculado: la presentación de las bases sigue sin etiquetar.

## 5. Comandos ejecutados sobre el clon

```bash
git clone --branch v2.88.170-beta --depth 1 https://github.com/jvelasca/Bolsa_V1.git
git fetch --unshallow --tags
git cat-file -t v2.88.170-beta            # tag
git rev-parse "v2.88.170-beta^{commit}"   # babfe228...
git rev-parse "v2.88.169-beta^{commit}"   # 3ce94048... (sin cambios)
pnpm install --frozen-lockfile
pnpm window:freeze                        # freeze OK (babfe228)
pnpm window:test                          # 50 passed
pnpm contract:check                       # OK
pnpm --filter @bolsa/shared typecheck     # sin salida
pnpm --filter @bolsa/web typecheck        # sin salida
pnpm --filter @bolsa/shared test          # 861 passed | 1 todo
pnpm --filter @bolsa/web test             # 2539 passed / 338 ficheros
npx vitest run <12 suites de ancla>       # 53 passed
uv run python -m pytest test_list_ledger_total_fees.py test_dia_d_bump_guard.py -q   # 4 passed
gh run view 40727162474 --json status,conclusion,jobs
gh run download 40727162474 -n release-tag-ci-summary
```

## 6. Veredicto

| Criterio del dictamen | Veredicto |
| --- | --- |
| Ausencia de datos frente a error | **PASA** — precedencia con prueba y seis superficies con render test |
| Ejecución frente a propuesta | **PASA** — sin `transactionId` no hay ejecución ni retirada de la cola |
| Exactitud financiera | **PASA** con alcance declarado — agregado histórico sin custodia y tono independiente del signo |

**El sello `v2.88.170-beta` es auditable y sus tres criterios están respaldados por pruebas que se rompen si
el defecto vuelve.** Lo que **no** certifica: la fuente de los datos, la rentabilidad, la ventana PAPER, ni
los P2/P3 que siguen abiertos.
