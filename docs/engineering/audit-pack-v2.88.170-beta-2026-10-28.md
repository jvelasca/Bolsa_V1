# Audit pack — `v2.88.170-beta` (auditable desde GitHub)

> **AsOf:** 2026-10-28 · **Repo:** [`jvelasca/Bolsa_V1`](https://github.com/jvelasca/Bolsa_V1) (**público**) · **Tag:** `v2.88.170-beta`
> **Propósito:** reunir en un solo sitio **todo lo necesario para auditar esta versión desde GitHub sin credenciales**: identidad inmutable, cómo obtenerla, dónde está la evidencia, qué **certifica**, qué **NO**, y cómo **falsarlo**.
> **Naturaleza:** documento de **evidencia/enlace**, no de producto. **`Δ motor = 0` · `Δ decisión = 0`** · **contrato HTTP ADITIVO** (`tradeFeesTotal`) (corrección de representación + tests + docs). Tag **unsigned**.
>
> **✅ Estado:** la **identidad inmutable** del tag (§1) y el **run de CI del sello** (§4) están citados en este mismo commit POST-TAG.

---

## 0. TL;DR — auditar en un comando

```bash
git clone --branch v2.88.170-beta --depth 1 https://github.com/jvelasca/Bolsa_V1.git
```

> El `<SHA_DEL_SELLO>` exacto es **`babfe228f9d81eb2b18be787465af588b5ff170b`** (ver §1).

---

## 1. Identidad inmutable del sello

| Elemento | Valor |
| --- | --- |
| **Tag** | `v2.88.170-beta` — **anotado** (**unsigned**) |
| **Objeto de tag** | `3e7948417c22bf9e767848331fe0d57fc2154e98` (`git cat-file -t v2.88.170-beta` ⇒ `tag`) |
| **Commit apuntado** | `babfe228f9d81eb2b18be787465af588b5ff170b` (`chore(window): re-ancla el pin PAPER al arbol del sello 2.11.170-beta`) |
| **Base (tag anterior)** | `v2.88.169-beta` → objeto `d31df9b3f1bfbdae9c5f15d99ddf1280d53f425a` ⇒ commit `3ce94048b45112d66eb6e3614f2e81676a41be97` (**no se mueve**) |
| **Versión monorepo** | `2.11.170-beta` ([`package.json`](../../package.json)) |
| **Alembic head** | `058_estudio_daily_proposals` (**sin migración**) |
| **Firma** | **unsigned** |

> **Nota (flujo del repo).** Aquí el objeto de tag y el SHA apuntado se **crearon antes** del commit POST-TAG y **no cambian** con él; este pack cita ambos en el mismo commit que los publica.

### 1.1 Orden de commits del sello

| # | Commit | Contenido |
| --- | --- | --- |
| 1 | `e9d5cb2a` | `fix(ui)` **P2-01** — un P&L no medido no se colorea como ganancia |
| 2 | `81e8b9aa` | `fix(ui)` **P2-02** — el riesgo solo está controlado si sus tres componentes se midieron |
| 3 | `bef8767a` | `docs(release)` — declaración del sello (respuesta, evidencia, CHANGELOG, estado) |
| 4 | `babfe228` | `chore(window)` — pin PAPER re-anclado al árbol del sello **← tag** |

Los siete commits anteriores (`31974c6c`…`033af182`) cierran los seis P1 y el comodín P2-04 y quedan descritos en §5.

---

## 2. Cómo obtener la versión

| Forma | Comando / enlace |
| --- | --- |
| Clonar el tag (recomendado) | `git clone --branch v2.88.170-beta --depth 1 https://github.com/jvelasca/Bolsa_V1.git` |
| Fijar el commit SHA | `git checkout babfe228f9d81eb2b18be787465af588b5ff170b` |
| Ver el árbol en la web | [tree/v2.88.170-beta](https://github.com/jvelasca/Bolsa_V1/tree/v2.88.170-beta) |

---

## 3. Evidencia — qué leer, en orden

| # | Documento | Qué responde |
| --- | --- | --- |
| 1 | [`evidence/v2.88.170/README.md`](evidence/v2.88.170/README.md) | Evidencia del sello: los nueve hallazgos, ficheros, verificación medida y límites declarados |
| 2 | [`CHANGELOG.md` §`2.11.170-beta`](../../CHANGELOG.md) | Nota de release: alcance, `W-170-1`…`W-170-9`, límites |
| 3 | [`PROJECT_STATE.md`](PROJECT_STATE.md) (AsOf `V2.88.170-beta`) | Estado vivo + agenda funcional |
| 4 | [`respuesta-auditoria-ui-operativa-2026-10-28.md`](respuesta-auditoria-ui-operativa-2026-10-28.md) | Causa → cambio → prueba → límite por hallazgo |
| 5 | [`auditoria-ui-operativa-profunda-2026-10-28.md`](auditoria-ui-operativa-profunda-2026-10-28.md) | El acta original (**no se reescribe**: se responde encima) |
| 6 | [`auditoria-independiente-v2.88.170-beta-2026-10-28.md`](auditoria-independiente-v2.88.170-beta-2026-10-28.md) | Contraste **desde un clon limpio del tag** y su CI, criterio por criterio |
| 7 | [`dictamen-tecnico-v2.88.170-beta-2026-10-28.md`](dictamen-tecnico-v2.88.170-beta-2026-10-28.md) | **Acto de aceptación**: qué se acepta (`P2-01`, `P2-02`, signo ≠ tono) y los **cuatro límites** que la aceptación conserva |
| 8 | [`audit-pack-v2.88.169-beta-2026-10-28.md`](audit-pack-v2.88.169-beta-2026-10-28.md) | Sello inmediatamente anterior (inmóvil) |

---

## 4. CI público (citable)

**Run del `Release tag CI` del sello:** [`40727162474`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40727162474) — **VERDE** (`2026-10-28T16:33:41Z` → `16:47:32Z`, `run_attempt 1`).

- **14 jobs `success`**, entre ellos `security (gitleaks)`, `shared`, `decision-spine`, `frontend`, `python`, `lifecycle-pg`, `dr-verify`, `a7-gate`, `playwright (mock E2E)`, `playwright (live AUTO daily chain)`, `playwright (integrated AUTO S5)`, **`playwright (integrated axe)`** (gate duro), `replay-repro` y **`certify (aggregate + artifact)`**.
- **1 `skipped` por diseño:** `playwright (integrated E2E, opt-in)`.
- **Artefacto `release-tag-ci-summary`** (`id 12834347261`, `sha256:f5a9055b…`) con `status: "GREEN"`, `tag: "v2.88.170-beta"`, `sha: "babfe228…"` y los **12** jobs obligatorios en `success`.
- **`replay-repro`** ⇒ `VEREDICTO REPRODUCIDO` (mismo contenido) ⇒ `Δ decisión = 0` confirmado por CI.

**Run de rama previo al tag:** los mismos cuatro workflows (`Frontend CI`, `Python CI`, `Optimize lab`, `Fase 2 scientific`) salieron `success` sobre `babfe228`, así que el tag no certificó un árbol no probado.

**Referencia de la base** `v2.88.169-beta`: `Release tag CI` [run `40680699713`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40680699713) — `success`.

> **Nota sobre el commit POST-TAG (`e77246d2`).** Ese commit es **solo `docs/`** y no dispara workflows: los
> cuatro workflows de rama filtran por `paths` (`apps/web/**`, `packages/shared/**`, `package.json`,
> `pnpm-lock.yaml`, `turbo.json`, `eslint.config.js`, el módulo de calibración y el propio workflow; Python y
> los demás, análogamente). La ausencia de run para ese SHA es **por diseño del filtro**, no un hueco de
> cobertura; el objeto certificado sigue siendo `babfe228`, y su árbol de `apps`/`packages` es **idéntico**
> al de `e77246d2` (`window:freeze` sigue `OK` con los mismos dos hashes).

---

## 5. Qué **certifica** esta versión

Corrige la **representación** de la operativa sin tocar motor ni decisión:

- **P1-01 — un error de lectura no es una colección vacía.** [`query-absence.ts`](../../apps/web/src/components/query-absence.ts) fija la precedencia `error > loading > unavailable > empty > ready`; [`collection-absence.tsx`](../../apps/web/src/components/collection-absence.tsx) declara el hueco; `useInstrumentOrderPending` pasa a tri-estado (`null` = no se pudo leer) y termina en `unknown`, nunca en «sin orden pendiente».
- **P1-02 — `skipped`/`unknown` no son «ejecutada».** [`pending-order-fill.ts`](../../apps/web/src/features/trading/pending-order-fill.ts): **sin `transactionId` no hay ejecución**; solo `executed` y `expired` retiran la orden; el resto no se borra ni se reintenta.
- **P1-03 — comisiones del histórico reales.** Agregado de servidor `total_trade_fees` → campo aditivo `tradeFeesTotal`; excluye custodia por diseño; la tarjeta se rotula «Comisiones de operaciones (histórico)».
- **P1-04 — el color declara el papel, no el signo.** `ledgerAmountTone` (`cost`/`in`/`neutral`) en [`portfolio-cash.ts`](../../packages/shared/src/portfolio-cash.ts); el importe conserva su signo.
- **P1-05 — el universo «0» solo si se midió.** `rankingUnavailable`/`rankingLoading` suprimen el CTA acusatorio y los ceros fabricados.
- **P1-06 — cartera caída ≠ «sin posiciones ni stops».** `absenceState` en el KPI de protección y «No disponible» en el resumen.
- **P2-04 — el comodín se prueba sobre el DOM.** `formatPriceOrAbsent` en primer nivel y `DATA_FRESHNESS_ABSENT_LABEL` en vez de `—`.
- **P2-01 — un P&L no medido no se colorea como ganancia.** [`pnl-tone.ts`](../../apps/web/src/lib/pnl-tone.ts): `pnlTone` (`positive`/`negative`/`neutral`, con hueco/`NaN`/`±Infinity` y **cero exacto** en `neutral`) sustituye `(x ?? 0) >= 0` en Mesa (fila y cabecera) y Operaciones.
- **P2-02 — «Controlado» exige sus tres componentes medidos.** [`auto-risk-summary.ts`](../../apps/web/src/features/auto/auto-risk-summary.ts) deja de hacer `fillLinkIssuesCount ?? 0`; si estado, cuadre o recuento no se midieron, el veredicto es «Sin dato todavía».

**Deltas:** `Δ motor de decisión = 0` · `Δ decisión = 0` · **sin migración** (`058_estudio_daily_proposals`) · **contrato HTTP solo aditivo** (`tradeFeesTotal`).

---

## 6. Límites / huecos **declarados** (lo que NO certifica)

1. **Corregir la representación no corrige la fuente.** Un `unknown` de fill sigue siendo un desconocimiento real del bróker; una cartera ilegible sigue siendo ilegible.
2. **`FALSE_ZERO_SURFACES` no se amplía** a Mesa/Mercado/AUTO: quedan `?? 0` de nivel 2 que alimentan cálculos, no cifras de primer nivel.
3. **P2-03, P2-05…P2-12 y los P3 siguen abiertos** (bases bruto/neto, día UTC vs local, truncación del informe diario, FX, «N posiciones», etc.). Este sello **no** los presenta como cerrados.
4. **El gate `axe` integrado mide estados estructurales**: las violaciones que solo afloran con datos o en estados modales pueden quedar latentes (deuda declarada, igual que en `.169`).
5. **NO cierra la ventana PAPER real** ni la rentabilidad: `INCONCLUSIVE` (`0/2` episodios, `0/32` ciclos). AUTO **OFF**, operativa **100 % PAPER virtual**.
6. **El pin PAPER** se re-ancló al árbol del sello; los días anteriores quedan **`STALE`** y no se reinterpretan.
7. **`R-170-1` · `pnpm typecheck` no es reproducible en un clon limpio.** Con `pnpm install --frozen-lockfile` y sin generar Prisma, el typecheck falla en `@bolsa/database` (`PrismaClient` no generado y `process` sin `@types/node`); `@bolsa/shared` y `@bolsa/web` **sí** pasan y el job `frontend` del CI —que genera Prisma antes— sale `success`. Es una **limitación reproducible del entorno de instalación**, declarada y abierta: **no** se corrige en este sello ni se presenta como absorbida por el CI verde. Ver [`dictamen-tecnico-v2.88.170-beta-2026-10-28.md` §4.2](dictamen-tecnico-v2.88.170-beta-2026-10-28.md).

---

## 7. Falsabilidad — cómo un auditor **rompe** cada afirmación

| # | Afirmación | Cómo se falsa |
| --- | --- | --- |
| 1 | Un error de lectura nunca se pinta como vacío | `query-absence.test.ts` + las seis render tests de ausencia fallan si vuelve `data ?? []` |
| 2 | Ningún desenlace distinto de `executed` dice «ejecutada» | `pending-order-fill.test.ts` falla si la copia de `skipped`/`unknown` imita la de `executed` |
| 3 | Las comisiones son el histórico, no la página | `history-page-fees.test.tsx` falla si la tarjeta suma las filas visibles (1 fila y total 1 234,50) |
| 4 | El color del asiento declara el papel | `history-page-tone.test.tsx` falla si una `fee` sale verde |
| 5 | Sin ranking no se acusa al usuario | `mesa-candidates-panel-absence.test.tsx` falla si reaparece el CTA |
| 6 | Cartera caída no es «sin stops» | `mesa-portfolio-absence.test.tsx` falla si reaparece la frase de seguridad |
| 7 | El hueco se declara en el texto, no con `—` | `history-page-dash-absence.test.tsx` y `data-freshness.test.ts` |
| 8 | Un P&L no medido no se colorea como positivo | `pnl-tone.test.ts` + `mesa-position-row.test.tsx` + `mesa-daily-header-pnl-tone.test.tsx` + `operations-panel-pnl-tone.test.tsx` fallan si vuelve `(x ?? 0) >= 0` |
| 9 | «Controlado» exige los tres componentes | `auto-risk-summary.test.ts` falla si `fillLinkIssuesCount ?? 0` vuelve a producir `ok` |
| 10 | `Δ contrato` solo aditivo | `pnpm contract:check` falla si `openapi.json`/`schema.d.ts` divergen |
| 11 | El pin casa con el árbol | `pnpm window:freeze` falla si `HEAD:apps`/`HEAD:packages` ≠ `WINDOW_CONFIG` |
| 12 | Bump coherente | `test_dia_d_bump_guard` falla si un `meta.bump` difiere de `package.json` |

---

## 8. Reproducir la verificación (local, sin credenciales)

```bash
pnpm install --frozen-lockfile
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared typecheck && pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/shared test
pnpm --filter @bolsa/web test
pnpm contract:check
pnpm window:test
pnpm window:freeze
uv run python -m pytest packages/py/application/tests/test_list_ledger_total_fees.py \
  apps/api-python/tests/test_dia_d_bump_guard.py -q
```

**Resultados medidos de referencia (clon del tag, 2026-10-28):** `web` **2539 passed / 338 ficheros** · `shared` **861 passed / 100 ficheros** (+1 `todo`) · `typecheck` de `shared` y `web` **sin salida** · `contract:check` **OK** · `window:test` **50 passed** · `window:freeze` **`freeze OK`** · suites de ancla **53 passed / 12 ficheros** · `pytest` dirigido **4 passed**.

> **`pnpm typecheck` en un clon recién instalado** puede fallar en `@bolsa/database` (`PrismaClient` no generado, `process` sin `@types/node`) porque el cliente Prisma se genera en el pipeline y no en `pnpm install`. El job `frontend` del CI —que es el que certifica— ejecuta el typecheck completo y salió `success`. Se declara aquí para que un auditor no lo lea como defecto del sello.
