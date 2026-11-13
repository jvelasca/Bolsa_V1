# Evidencia S3 — Cartera del Asesor · 2026-11-12

> Alcance: modelo puro de la fila, clasificador de los cinco estados, carga batch con caché
> compartida, pestaña «Cartera» en Asesor y guardas de vocabulario/primer nivel.
>
> Estado: **implementado y verificado**. Sin commit, sin migración, sin `contract:gen`, sin
> tocar S0/F4-067. `PROJECT_STATE.md` no se toca en este slice.

## 1 · Invariantes

| Invariante | Comprobación | Resultado |
| --- | --- | --- |
| `Δ motor = 0` | `git diff --name-only -- packages/py apps/api-python` | Sin archivos de S3: los listados de `packages/py` ya estaban modificados antes de este slice por F4-067 y por el bloque de concordancia backend ↔ UI |
| `Δ decisión = 0` | `compute_stance`, umbrales, gate, sizing | Sin cambios |
| Sin migración | `git status` sobre `versions/` | Nada añadido |
| Sin `contract:gen` | `Select-String` de `asesor.?cartera|AsesorCartera|market.?structure` en `openapi.json` y `schema.d.ts` | 0 coincidencias |
| S0/F4-067 intactos | `git status --porcelain` | Los archivos ajenos siguen modificados, no revertidos ni staged |
| Sin commit | `git log -1` | Sin cambios de HEAD |

**Atribución corregida (R-07).** Los dos módulos que el bloque backend ↔ UI reclama como
propios —`daily_opinion_service.py` y `daily_opinion_hints.py`— **no** forman parte de las 18
rutas certificadas de F4-067 (acta §2). Su modificación pertenece al bloque de concordancia
backend ↔ UI, no a F4-067. Las rutas de S3 siguen siendo las de §4.

**Nota de honestidad sobre el contrato:** `apps/web/api/openapi.json` y
`apps/web/src/api/schema.d.ts` ya estaban modificados **antes** de S3 por F4-067. S3 no los
toca; no hay ninguna referencia a cartera ni a estructura de mercado en su contenido.

## 2 · Pruebas ejecutadas

```text
pnpm --filter @bolsa/shared test -- asesor-cartera
  ✓ src/cognitive/asesor-cartera.test.ts (34 tests)

pnpm --filter @bolsa/web test -- asesor-cartera
  ✓ src/features/research/use-asesor-cartera-data.test.ts (5 tests)
  ✓ src/features/research/asesor-cartera-panel.test.tsx (16 tests)

pnpm --filter @bolsa/web test -- research-first-level
  ✓ src/features/research/research-first-level.test.tsx (7 tests)

pnpm --filter @bolsa/web test -- operativa-recomendacion-vocabulary
  ✓ src/features/trading/operativa-recomendacion-vocabulary.test.tsx (9 tests)
```

Cobertura declarada y falsable:

**Clasificador (`asesor-cartera.test.ts`)**

- un caso por estado y la precedencia completa;
- cartera no medida gana y **no** se lee «sin posición»;
- `position_unmeasured`, `io_unmeasured` y `eod_data_stale` son `sin_datos`, no «Sin
  oportunidad»;
- `overbought` con posición ⇒ «Posición sin respaldo», sin la palabra «sobrecompra»;
- `review_strategy` con y sin posición;
- `reduce`/`sell_exit` con posición ⇒ «Posición abierta»;
- `reduce`/`sell_exit` sin posición ⇒ `sin_datos` con «Dictamen de salida sin posición medida»;
- `hold_watch`/`no_trade`/`review_strategy` sin posición ⇒ «Sin oportunidad»;
- `buy` sin posición ⇒ «Recomendación favorable».

**No agregación**

- contexto alcista completo (tendencia alcista fuerte, fuerza 9, S/R detectados, entrada
  publicada) + `hold_watch` ⇒ sigue «Sin oportunidad» y «Mantener», con el contexto visible;
- `buy` con contexto flojo ⇒ sigue «Recomendación favorable».

**Niveles**

- solo `detectado` produce nivel; `roto`/`no_fiable`/`en_precio` se ignoran;
- histórico insuficiente declara `N velas` y el mínimo;
- sin estructura no se pinta `0` como nivel.

**Tendencia, fuerza y momento**

- sin parte diario: «Sin dato de tendencia» y «Sin dato de fuerza»;
- la fuerza se copia del estudio, no se infiere;
- parte caducado se declara sin cambiar la tendencia;
- termómetro: `sin_entrada`, `frio`, `templado`, `caliente`, `extendido`;
- con posición el momento es stop/T1/T2 y no un termómetro; sin geometría se declara.

**Cargador de velas (`use-asesor-cartera-data.test.ts`)**

- `peakConcurrency ≤ 4` y `> 1` con 10 instrumentos;
- reutiliza la caché sin llamar al fetch;
- un fallo por instrumento queda en `failedIds` y no tumba la lista;
- deduplica ids; una caché vacía no cuenta como acierto.

**UI (`asesor-cartera-panel.test.tsx`)**

- las cinco filas con las cinco etiquetas de producto y `data-state` correcto;
- filtros por estado y «solo con posición»;
- «Cartera sin medir» y «Sin dictamen» declarados, sin «Sin posición» falso;
- cantidad, coste y P&L en posición abierta;
- sin CTA de compra ni de firma; «Ver en Mercado» abre el valor;
- la recomendación visible es la del dictamen («Comprar» / «Mantener»);
- primer nivel sin claves `snake_case`, sin `<details>` paralelos, sin `—` de relleno y sin
  `?? 0`.

## 3 · Tipos y lint

```text
pnpm --filter @bolsa/shared typecheck   → OK
pnpm --filter @bolsa/web typecheck      → OK (tsc -b --noEmit)
pnpm --filter @bolsa/shared lint        → OK
pnpm --filter @bolsa/web lint           → 0 errores (23 warnings preexistentes)
```

Nota: `packages/shared` se compila (`pnpm --filter @bolsa/shared build`) porque
`apps/web` consume `dist/`. El paso no genera artefactos versionados.

## 4 · Archivos de S3

**Nuevos**

- `packages/shared/src/cognitive/asesor-cartera.ts`
- `packages/shared/src/cognitive/asesor-cartera.test.ts`
- `apps/web/src/features/research/use-asesor-cartera-data.ts`
- `apps/web/src/features/research/use-asesor-cartera-data.test.ts`
- `apps/web/src/features/research/asesor-cartera-panel.tsx`
- `apps/web/src/features/research/asesor-cartera-panel.test.tsx`
- `docs/engineering/diseno-asesor-cartera-s3-2026-11-12.md`
- `docs/engineering/evidence/s3-asesor-cartera-2026-11-12/README.md`

**Modificados (solo lo imprescindible)**

- `packages/shared/src/cognitive/index.ts` — exporta el dominio nuevo.
- `apps/web/src/features/research/research-page.tsx` — pestaña «Cartera» antes de «Análisis»
  (`HubTab`, `parseTab`, botón) y enlace en el primer nivel de Tesis.
- `apps/web/src/features/research/research-first-level.test.tsx` — añade el panel al gate.
- `apps/web/src/features/trading/operativa-recomendacion-vocabulary.test.tsx` — añade el panel
  a la guarda de términos retirados.

## 5 · Decisiones que se apartan de la letra del plan (y por qué)

1. **Orden de presentación por excepción**: primero «Posición sin respaldo», luego
   «Recomendación favorable», «Posición abierta», «Sin oportunidad» y «Sin datos suficientes».
   El plan enumeraba los estados, no el orden de lectura; se prioriza lo que exige atención sin
   convertirlo en una señal.
2. **`reduce`/`sell_exit` sin posición** se declaran `sin_datos` con el hueco «Dictamen de
   salida sin posición medida» en vez de inventar una posición o una categoría nueva. Coincide
   con el plan y se ancla en test.
3. **`structureProvenance` en la fila**: el plan pedía método, ventana, ATR, firma y pivotes en
   el detalle. Se resuelve añadiendo un bloque de procedencia a la fila pura, no consultando S2
   desde la UI.
4. **Termómetro solo sin posición**: con posición abierta se muestra la geometría de salida
   (stop/T1/T2). Mostrar ambos sugeriría una entrada sobre una posición ya abierta.
5. **`readCached` en el cargador**: la reutilización de la caché del gráfico se hace explícita y
   testeable en vez de depender del orden de montaje de React Query.

## 6 · Riesgo declarado

- S/R por fila exige N lecturas OHLCV mientras no exista endpoint batch. Se mitiga con
  concurrencia 4, `staleTime` de 5 min y reutilización de la caché `["ohlcv", id, "1d"]`.
- Un valor sin histórico declara el hueco en su fila; no bloquea la lista.
- Si `decision-studies` se trunca, la cabecera lo declara y la lista no afirma «sin plan».

## 7 · Pendiente, fuera de este slice

- Aprobación de producto de S3.
- Actualizar `PROJECT_STATE.md` solo tras esa aprobación.
- Rediseño maximizado de DECISIÓN, endpoint batch de OHLCV/key-levels y capturas E2E del
  cierre S5.
