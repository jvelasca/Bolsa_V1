# Dictamen técnico de aceptación — `v2.88.170-beta`

> **AsOf:** 2026-10-28 · **Objeto:** tag `v2.88.170-beta` (objeto `3e7948417c22bf9e767848331fe0d57fc2154e98` → commit
> `babfe228f9d81eb2b18be787465af588b5ff170b`) · **Versión:** `2.11.170-beta`.
> **Naturaleza:** **registro de aceptación**. No es una re-auditoría, no reabre `v2.88.169-beta` (`d31df9b3` →
> `3ce94048`, inmóvil), no modifica código, CI, migraciones, `package.json`, tags ni el pin PAPER.
> **Veredicto:** se aceptan los dos cambios de representación (`P2-01`, `P2-02`) **con los cuatro límites de §4
> expresamente conservados**. Aceptar el sello **no** certifica P&L neto, patrimonio multidivisa ni rentabilidad.

---

## 0. Qué añade este documento

El sello ya tiene evidencia propia ([`evidence/v2.88.170`](./evidence/v2.88.170/README.md)), una
[respuesta hallazgo por hallazgo](./respuesta-auditoria-ui-operativa-2026-10-28.md), un
[audit pack](./audit-pack-v2.88.170-beta-2026-10-28.md) y una
[auditoría independiente desde un clon limpio del tag](./auditoria-independiente-v2.88.170-beta-2026-10-28.md).
Lo que faltaba es el **acto de aceptación**: qué se da por bueno, con qué ancla, y —sobre todo— **qué no se
acepta como cerrado** al aceptarlo. Ese es el contenido de §2, §3 y §4.

Este dictamen **no re-mide**: cita la medición publicada y la contrasta con el código del árbol. Donde la
medición no existe (ventana PAPER, rentabilidad), lo dice en vez de inferirlo del CI verde.

---

## 1. Identidad y CI del objeto aceptado

| Elemento | Valor |
| --- | --- |
| Tag | **anotado** (unsigned), objeto `3e794841` |
| Commit apuntado | `babfe228f9d81eb2b18be787465af588b5ff170b` (`chore(window): re-ancla el pin PAPER al arbol del sello 2.11.170-beta`) |
| Base anterior | `v2.88.169-beta` → `3ce94048` (**sin cambios**) |
| `Release tag CI` | [run `40727162474`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40727162474) — **`success`**, 14 jobs verdes, 1 `skipped` por diseño |
| Agregado | `certify` `success`; artefacto `release-tag-ci-summary` (`id 12834347261`) con `status: "GREEN"` |
| Deltas | `Δ motor = 0` · `Δ decisión = 0` · contrato HTTP **aditivo** (`tradeFeesTotal`) · sin migración (`058_estudio_daily_proposals`) |

El artefacto declara `sha: "babfe228…"` y `tag: "v2.88.170-beta"`: el CI certifica **exactamente** el commit
apuntado por el tag. El commit POST-TAG (`e77246d2` / `582d2cbf`) es **solo `docs/`** y no dispara workflows por
diseño del filtro de `paths`; su árbol de `apps`/`packages` es idéntico al certificado (`window:freeze` sigue
`OK` con los mismos dos hashes).

---

## 2. Qué se acepta

### 2.1 `P2-01` — un P&L no medido ya no aparenta una ganancia

**Antes.** `(unrealizedPnl ?? 0) >= 0` decidía el color en la fila de posición, la tabla de Operaciones y la
cabecera de Hoy. `unrealizedPnl` es `null` cuando la posición no tiene mark observable, así que un **hueco** y un
**cero medido** se leían igual y ambos salían verdes. El texto ya declaraba el hueco; el color —la lectura
dominante en una tabla de dinero— afirmaba lo contrario.

**Ahora.** [`pnl-tone.ts`](../../apps/web/src/lib/pnl-tone.ts) define `pnlTone(value)` → `positive` | `negative` |
`neutral`, con `null`/`undefined`/`NaN`/`±Infinity` y **cero exacto** en `neutral`, y `PNL_TONE_CLASS` con
`neutral` en color de primer plano apagado (ni verde ni rojo). Las tres superficies pintan con ese tono y exponen
`data-tone` para que la prueba no dependa de clases de Tailwind.

**Ancla.** [`pnl-tone.test.ts`](../../apps/web/src/lib/pnl-tone.test.ts) (tabla de valores, **5 passed**),
[`mesa-position-row.test.tsx`](../../apps/web/src/features/mesa/mesa-position-row.test.tsx),
[`mesa-daily-header-pnl-tone.test.tsx`](../../apps/web/src/features/mesa/mesa-daily-header-pnl-tone.test.tsx) y
[`operations-panel-pnl-tone.test.tsx`](../../apps/web/src/features/trading/operations-panel-pnl-tone.test.tsx).

**Falsación mínima.** Volver a `(x ?? 0) >= 0` rompe las cuatro pruebas.

**Límite propio del cambio.** `neutral` **no distingue por color** «no medido» de «cero medido»: la distinción la
hace el **texto** (`Sin dato todavía` frente a `0.00`). Así se declara y así se acepta.

### 2.2 `P2-02` — «Controlado» exige evidencia de los tres componentes

**Antes.** [`auto-risk-summary.ts`](../../apps/web/src/features/auto/auto-risk-summary.ts) hacía
`const issues = fillLinkIssuesCount ?? 0`. Con estado operativo sano y cuadre de cartera sano, un recuento de
incidencias **sin leer** caía en el veredicto `ok` y emitía «El riesgo está controlado. No hay bloqueos ni
incidencias activas» — una afirmación de salud sobre un dato que no existía. El helper ya declaraba el hueco en la
**celda** (`fillLinkIssuesAvailable`), pero no en el **titular**, que es la afirmación de primer nivel.

**Ahora.** `riskVerdict` conserva la precedencia de las señales medidas (`blocked` > `attention`) y añade, **antes**
de `ok`, la exigencia de que **estado, cuadre y recuento** estén medidos; si falta cualquiera, el veredicto es
`Sin dato todavía`. Una señal medida (bloqueo, degradación, desajuste, incidencias > 0) **sigue mandando** sobre el
hueco de otro componente, porque afirma un problema y no una salud.

**Ancla.** [`auto-risk-summary.test.ts`](../../apps/web/src/features/auto/auto-risk-summary.test.ts) (**9 passed**,
bloque `P2-02` incluido): `OK` + `clean` + `null` ⇒ `Sin dato todavía` y la frase **no** contiene «controlado» ni
«No hay»; `OK` + `null` + `0` ⇒ `Sin dato todavía`; y el caso medido `OK` + `clean` + `0` **sigue** siendo
`Controlado` (el hueco no contagia a la afirmación soportada).

**Falsación mínima.** Reintroducir `fillLinkIssuesCount ?? 0` en el veredicto rompe el bloque.

**Límite propio del cambio.** El veredicto **agrega tres señales**; no mide el riesgo por posición, que sigue
declarado como no materializado (`positionRiskAvailable: false`).

### 2.3 El signo del importe se conserva separado del tono visual

Los dos cambios y el precedente `P1-04` comparten la misma regla, y el dictamen la acepta como **mérito, no como
detalle cosmético**: [`ledgerAmountTone`](../../packages/shared/src/portfolio-cash.ts) devuelve `cost` | `in` |
`neutral` y `pnlTone` devuelve `positive` | `negative` | `neutral`; en ambos casos **el tono es color, no
aritmética**. El importe conserva su signo y su formato (`-50` sigue siendo `-50`; una comisión con importe
negativo sigue siendo negativa y solo cambia de color).

**Por qué importa.** Si el color sustituyera al valor financiero, un hueco podría «leerse» como ganancia y una
comisión como una entrada de capital. El dictamen sostiene que **el color no debe sustituir al valor financiero**
en ninguna de estas superficies, y que esa separación es la que permite afirmar «no medido» sin borrar el dato.

---

## 3. Veredicto

- **`P2-01` — PASA.** Un P&L no medido no se colorea como ganancia; el tono es independiente del signo y el signo
  no se toca. Falsable en cuatro pruebas.
- **`P2-02` — PASA.** «Controlado» requiere los tres componentes medidos; el hueco no produce salud y el caso
  medido sigue afirmando salud. Falsable en la suite de nueve casos que contiene el bloque `P2-02`.
- **`P1-04` (precedente) — se mantiene.** El tono del asiento declara el papel (coste/entrada/neutral), no el
  signo, y el importe conserva su signo.
- **Alcance del veredicto.** Lo aceptado es la **representación**: qué afirma la UI sobre lo ya decidido. **No** se
  acepta como certificado el **contenido** de las cifras que dependen de bases sin etiquetar ni de conversión de
  divisa (§4.1).
- **Lo que sostiene el veredicto y lo que no.** Lo sostienen pruebas que **se rompen si el defecto vuelve** y un
  `Release tag CI` verde sobre el commit del tag. **No** lo sostiene el CI en sí: un pipeline verde no mide si el
  dinero está bien calculado, ni si la fuente es legible, ni si la estrategia gana.

---

## 4. Límites expresos de la aceptación

Estos cuatro límites **no se suavizan** al aceptar el sello. Aceptar `v2.88.170-beta` significa aceptarlos.

### 4.1 `P2-03` y `P2-11` siguen abiertos — no se certifica P&L neto ni patrimonio multidivisa

- **`P2-03` · bases financieras mezcladas sin etiqueta.** El P&L **no realizado** es **bruto** de comisiones, el
  **realizado** es **neto**, el «Total» de una operación va **sin** comisiones y la caja va **con** comisiones.
  Cada cifra aislada no es incorrecta; el defecto es **presentarlas contiguas** —dos de ellas en la misma tarjeta—
  sin declarar cuál es neta y cuál bruta. El usuario que resta «no realizado» de «total» obtiene un número que no es
  ningún P&L. Ver [auditoría profunda §4.3](./auditoria-ui-operativa-profunda-2026-10-28.md).
- **`P2-11` · sin conversión de divisa en los totales.** `marginUsed` y los totales de cartera suman
  `market_value` sin FX, de modo que «Patrimonio» y «P&L no realizado» pueden ser **sumas de unidades monetarias
  heterogéneas** presentadas con un solo símbolo. Ver [auditoría profunda §4.11](./auditoria-ui-operativa-profunda-2026-10-28.md).

**Consecuencia explícita:** al aceptar este sello **no queda certificado el P&L neto** ni el **patrimonio
multidivisa**. No es que el dinero esté mal calculado: es que la **presentación de las bases** sigue sin
etiquetar. El sello **no** los presenta como cerrados y este dictamen tampoco los absuelve
([auditoría independiente §4.3](./auditoria-independiente-v2.88.170-beta-2026-10-28.md)). Los `P2-05…P2-12`
restantes y los `P3` siguen igualmente abiertos y declarados; `P2-04` sí se cerró en este sello.

### 4.2 `R-170-1` — incidencia de reproducibilidad: `pnpm typecheck` en un clon limpio

En un clon **recién instalado**, `pnpm typecheck` **falla** en `@bolsa/database`: el cliente `PrismaClient` no se
genera durante `pnpm install` (lo genera el pipeline) y `process` queda sin `@types/node` en ese paquete. Es una
limitación **reproducible del entorno de instalación**, no un defecto del árbol del sello:

- `pnpm --filter @bolsa/shared typecheck` pasa **sin salida**;
- `pnpm --filter @bolsa/web typecheck` pasa **sin salida**;
- el job `frontend` del `Release tag CI`, que ejecuta el typecheck completo **después** de generar Prisma, sale
  `success`.

**Cómo se registra.** Como **incidencia de reproducibilidad abierta** (`R-170-1`), declarada en el audit pack y
en la evidencia para que un auditor no la descubra por su cuenta. **No** se oculta detrás del CI verde y **no** se
reclasifica como «absorbe el pipeline»: que el CI lo tape por orden de pasos no lo convierte en reproducible local.
**No** se corrige en este dictamen: exigiría un cambio aparte (generación explícita post-install o un bootstrap
documentado) con su propio alcance y su propio sello.

### 4.3 `replay-repro` = `REPRODUCIDO` no demuestra rentabilidad

`replay-repro` respalda la **reproducibilidad de la decisión evaluada**: con el mismo contenido, el artefacto
OOS no se mueve y `Δ decisión = 0` queda confirmado por CI. Eso es **consistencia**, no **ventaja estadística**.

`REPRODUCIDO` **no** demuestra que la estrategia sea rentable: no hay muestra suficiente, ni intervalo de
confianza, ni comparación con benchmark. Un replay que se repite idéntico solo prueba que el instrumento es
estable, incluida su estabilidad para producir resultados planos.

### 4.4 `AUTO` sigue `OFF` y `PAPER` sigue `INCONCLUSIVE`

- **AUTO OFF.** Ninguna superficie de este sello autoriza operar con dinero real; la operativa es **100 % PAPER
  virtual**.
- **Ventana PAPER `INCONCLUSIVE`:** **0/2 episodios** y **0/32 ciclos** medibles (`evidence_ready = false`).
- El sello **no mueve la ventana** y **no** convierte un CI verde en evidencia operativa. Corregir la
  representación no corrige la fuente: un `unknown` de fill sigue siendo un desconocimiento real del bróker y una
  cartera ilegible sigue siendo ilegible.

---

## 5. Lo que el sello no certifica

1. **La fuente de los datos.** Que la UI declare el hueco no hace legible lo ilegible.
2. **La rentabilidad.** Ni la ventana PAPER ni `replay-repro` la miden.
3. **La exactitud de las bases financieras.** `P2-03` y `P2-11`, §4.1.
4. **Los `P3`** y los `P2` restantes, que siguen abiertos.
5. **`FALSE_ZERO_SURFACES` no se amplía** a Mesa/Mercado/AUTO: quedan `?? 0` de nivel 2 que alimentan cálculos.
6. **El gate `axe` integrado mide estados estructurales**: las violaciones que solo afloran con datos o en estados
   modales pueden quedar latentes (deuda declarada, igual que en `.169`).
7. **El pin PAPER** se re-ancló al árbol del sello; los días anteriores quedan `STALE` y **no se reinterpretan**.

---

## 6. Falsabilidad y reproducción

Cada afirmación aceptada se puede **romper**:

- `pnpm --filter @bolsa/web test -- pnl-tone mesa-position-row mesa-daily-header-pnl-tone operations-panel-pnl-tone`
  falla si vuelve `(x ?? 0) >= 0` o si un hueco se pinta como positivo.
- `pnpm --filter @bolsa/web test -- auto-risk-summary` falla si `fillLinkIssuesCount ?? 0` vuelve a producir `ok`.
- `pnpm --filter @bolsa/shared test -- portfolio-cash` falla si el tono del asiento vuelve a salir del signo.
- `pnpm contract:check` falla si `openapi.json`/`schema.d.ts` divergen (Δ contrato solo aditivo).
- `pnpm window:freeze` falla si `HEAD:apps`/`HEAD:packages` no casan con `WINDOW_CONFIG`.
- `uv run python -m pytest packages/py/application/tests/test_list_ledger_total_fees.py apps/api-python/tests/test_dia_d_bump_guard.py -q`
  falla si el agregado vuelve a la página o si un `meta.bump` difiere de `package.json`.

Reproducir la limitación de §4.2 (no la corrige, la documenta):

```bash
git clone --branch v2.88.170-beta --depth 1 https://github.com/jvelasca/Bolsa_V1.git
pnpm install --frozen-lockfile
pnpm typecheck                            # falla en @bolsa/database (R-170-1)
pnpm --filter @bolsa/shared typecheck     # sin salida
pnpm --filter @bolsa/web typecheck        # sin salida
```

---

## 7. Alcance de este registro (no-cambios)

- **No** modifica código, tests, contrato, CI, `package.json`, `CHANGELOG`, migraciones ni `.github/`.
- **No** crea, mueve ni anota tags; `v2.88.170-beta` y `v2.88.169-beta` quedan como están.
- **No** mueve el pin PAPER ni `operability_runs/`; los días previos siguen `STALE`.
- **No** reescribe el [acta de auditoría](./auditoria-ui-operativa-profunda-2026-10-28.md), la
  [respuesta](./respuesta-auditoria-ui-operativa-2026-10-28.md) ni la
  [auditoría independiente](./auditoria-independiente-v2.88.170-beta-2026-10-28.md): este dictamen se **añade
  encima** de la evidencia publicada.
- **No** abre ni cierra `P2-03`, `P2-11`, `P2-05…P2-12` ni los `P3`.

---

## 8. Cierre

Se acepta `v2.88.170-beta` como **sello de corrección de representación** con `P2-01` y `P2-02` respaldados por
pruebas que se rompen si el defecto vuelve, y se acepta **con** los límites de §4: `P2-03` y `P2-11` abiertos
—por tanto **sin certificar el P&L neto ni el patrimonio multidivisa**—, `R-170-1` como limitación reproducible
del entorno de instalación, `replay-repro` como reproducibilidad de la decisión y **no** como rentabilidad, y
AUTO **OFF** con PAPER **`INCONCLUSIVE`** (`0/2`, `0/32`).

Lo aceptado es la **honestidad de la interfaz** sobre lo que se midió y lo que se ejecutó. Lo que sigue pendiente
es el **contenido** de las cifras y la **evidencia operativa**: ninguno de los dos se cierra con este dictamen.
