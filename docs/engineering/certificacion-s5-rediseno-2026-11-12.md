# Certificación S5 — Rediseño S1–S4 (2026-11-12)

- **Alcance**: certificación global del rediseño de la ventana **DECISIÓN** (S1 dictamen, S2 contexto técnico, S3 cartera/Asesor, S4 vía de actuación) sin modificar S4.
- **Método**: matriz ejecutable en Vitest + suite E2E determinista con capturas y axe + pase visual sobre el stack real.
- **Veredicto**: **PASS funcional con una reserva de accesibilidad declarada** (ver §8), **aprobado por producto el 2026-11-12** (acta en §11).
- **Invariantes**: `Δ motor = 0`, `Δ decisión = 0`, sin migraciones, `contract:check` limpio, sin cambios en `PROJECT_STATE.md`/`CHANGELOG.md`, sin `git add` ni commit, S0/F4-067 sin tocar. El cierre es **documental**: `HEAD` sigue en `bcdc4584`, índice vacío y rama `feat/f4-067-opinion-account-scope` sin cambios.

## 1 · Qué se certifica

La ventana maximizada de DECISIÓN debe contar **una sola historia**: qué recomienda el motor
(S1), qué contexto técnico la acompaña sin autorizar (S2), qué hay en cartera (S3) y qué vía
de actuación existe (S4). La certificación comprueba, para cada escenario de producto:

1. el **estado del hero** (`data-state`, etiqueta canónica de S3);
2. la **vía de actuación** (`data-action-hint`, etiqueta y motivo de bloqueo de S4);
3. el **dictamen único** (S1) dentro del hero, sin claves internas ni términos retirados;
4. la **coherencia con el cockpit real** (ACCIÓN): fase, CTA de preparar y ausencia de «COMPRAR»;
5. que el **contexto técnico informa y no autoriza** (S2);
6. la coherencia en **dock** y **estrecha**, y en los cortes 1600 / 1200 / 403 px.

## 2 · Matriz de los seis escenarios

Matriz ejecutable: `apps/web/src/features/trading/trading-operativa-panel.maximized.test.tsx`
(bloque `S5 · escenarios de producto`, 11 pruebas nuevas; el archivo suma 18).
E2E gemelo: `apps/web/e2e/gp-s5-rediseno-s1-s4.spec.ts` (11 pruebas).

| # | Escenario | Dictamen / cartera | Hero (`data-state`) | Actuación (`data-action-hint`) | Cockpit |
|---|---|---|---|---|---|
| 1 | Recomendación favorable sin posición | `buy` 85, cartera medida sin posición | `recomendacion_favorable` · «Recomendación favorable» | `entrada_disponible` · «Entrada disponible» | fase `preparada`, CTA habilitado |
| 2 | Posición abierta con respaldo | `hold_watch` 72 + posición | `posicion_abierta` · «Posición abierta» | `salida_en_accion` · «Salida en ACCIÓN» | fase `posicion`, sin CTA de entrada |
| 3 | Posición sin respaldo | `overbought` 61 + posición | `posicion_sin_respaldo` · «Posición sin respaldo» | `salida_en_accion` · «Salida en ACCIÓN» | fase `posicion`, sin CTA de entrada |
| 4 | Sin datos suficientes | cartera no medida | `sin_datos` · «Sin datos suficientes» | `sin_actuacion` · «Sin actuación» | sin CTA; aviso «Cartera no medida» |
| 5 | Entrada bloqueada | `buy` 85 sin posición, kill switch | `recomendacion_favorable` · «Recomendación favorable» | `entrada_bloqueada` · «Entrada bloqueada», `data-blocked-reason="entradas_bloqueadas"` | CTA deshabilitado con etiqueta «Entradas bloqueadas» |
| 6 | Salida permitida con entradas bloqueadas | `hold_watch` 72 + posición, kill switch | `posicion_abierta` · «Posición abierta» | `salida_en_accion` · «Salida en ACCIÓN» (sin `data-blocked-reason`) | fase `posicion`, sin CTA de entrada |

Comprobaciones transversales de la matriz: un único `operativa-dictamen` y siempre dentro del
hero; la etiqueta de postura coincide con `marketStanceLabel` (S1) en las seis posturas; el
aviso de alcance («la recomendación no ejecuta») está presente en todas las vías; `sin_actuacion`
nunca se lee como «sin posición»; y `entrada_bloqueada` solo aparece con el motivo que evalúa
`canPropose`.

### Matiz verificado en el E2E (no es un fallo)

Con entradas bloqueadas y fase `preparada`, el propio CTA de preparar se rotula
**«Entradas bloqueadas»** y queda deshabilitado; por eso no se añade además el aviso
`operativa-cockpit-blocked-hint` (ese aviso aparece cuando la etiqueta primaria es distinta).
La UI no ofrece dos avisos redundantes.

## 3 · Superficies y responsive

| Superficie | Seeds | Evidencia |
|---|---|---|
| `maximized` (1600×1000) | `operativaMaximized: true` | 3 columnas del grid (`≥78rem`), hero visible |
| `maximized` (1200×900) | mismo seed | 2 columnas (`≥52rem`), hero visible |
| `narrow` (403×900) | mismo seed | `data-surface="narrow"`, sin hero (composición anterior) |
| `dock` | `operativaMaximized: false` | `data-surface="dock"`, sin hero; dictamen compacto dentro de Evidencia |

El corte de 403 px monta la composición estrecha de siempre aunque DECISIÓN esté maximizada:
la maximizada recompone solo en escritorio, como especifica S4.

## 4 · S2 y S3 dentro de la certificación

- **S2**: `operativa-contexto-tecnico` declara «Informan; no autorizan entradas» y el readout
  `market-structure-readout` se pinta con `data-status="ok"` en el escenario determinista
  (140 velas). No introduce CTA ni segunda recomendación.
- **S3**: en Asesor/Cartera, la misma cartera se clasifica con el mismo clasificador:
  `posicion_abierta` con posición y `recomendacion_favorable` sin posición. Las filas no
  ofrecen «COMPRAR». La columna «Posición» de Asesor sí puede decir «Sin posición»: es una
  medición propia de la columna, no el estado `sin_datos` de DECISIÓN (que nunca lo afirma).

## 5 · Pase visual sobre el stack real

Servidor ya levantado (`http://localhost:5173`, API en `:8000`), sin mocks, ventana 1600×1000
→ maximizar DECISIÓN. Instrumento activo: **BBVA**.

| Lectura real | Valor |
|---|---|
| Hero | `data-state="evaluado_sin_oportunidad"` · «Sin oportunidad» |
| Actuación | `data-action-hint="sin_actuacion"` · «Sin actuación» |
| Dictamen | «Mantener» · confianza 68/100 · ★★★★☆ · «Sin señal de entrada · Calidad de señal sin señal de compra» |
| Cockpit | fase `propuesta`, sin `data-position-id`; «No existe todavía un plan operativo»; «Revisar y confirmar (3)» |
| 1200×900 | idéntico (hero y actuación estables) |
| 403×900 | `data-surface="narrow"`, sin hero |
| Consola | 0 errores en `/trading` |
| Asesor (real) | 80 valores en Estudio, 0 con posición, 80 `sin_datos` («Sin dictamen») |

**Cobertura real vs determinista (declaración honesta).** La cartera real solo ejercita el
estado adicional `evaluado_sin_oportunidad` (dictamen sin compra, sin posición) y, en Asesor,
el estado `sin_datos` para los 80 valores sin dictamen. **Ninguno de los seis escenarios
semánticos se alcanza con los datos reales**: los seis quedan certificados por la matriz
determinista de Vitest + E2E. El pase real certifica composición, tipografía, responsive y
ausencia de incoherencias visibles con datos de producción.

## 6 · Evidencia

Carpeta: [`docs/engineering/evidence/s5-rediseno-2026-11-12/`](evidence/s5-rediseno-2026-11-12/README.md).

- `s5-favorable_sin_posicion-1600x1000.png`
- `s5-posicion_con_respaldo-1600x1000.png`
- `s5-posicion_sin_respaldo-1600x1000.png`
- `s5-sin_datos-1600x1000.png`
- `s5-entrada_bloqueada-1600x1000.png`
- `s5-salida_con_entradas_bloqueadas-1600x1000.png`
- `s5-responsive-1600x1000.png`, `s5-responsive-1200x900.png`, `s5-responsive-403x900.png`
- `s5-superficie-dock-1600x1000.png`
- `s5-s2-contexto-tecnico-1600x1000.png`
- `s5-s3-asesor-cartera-posicion-1600x1000.png`, `s5-s3-asesor-cartera-sin-posicion.png`
- `s5-real-maximizada-1600x1000.png`, `s5-real-maximizada-1200x900.png`, `s5-real-maximizada-403x900.png`
- `s5-real-asesor-cartera-1600x1000.png`

## 7 · Verificación ejecutada

| Comando | Resultado |
|---|---|
| `pnpm --filter @bolsa/web test` | **388 archivos, 2.899 pruebas OK** (incluye la matriz S5 y el ratchet de formato) |
| `pnpm --filter @bolsa/shared test` | **107 archivos, 1.024 OK + 1 todo** |
| `pnpm --filter @bolsa/web typecheck` | OK |
| `pnpm --filter @bolsa/web lint` | 0 errores, 23 warnings preexistentes |
| `pnpm --filter @bolsa/web build` | OK (4,81 s) |
| `pnpm --filter @bolsa/web contract:check` | OK — `openapi.json` y `schema.d.ts` coinciden con el commit |
| `E2E_RUN=1 playwright test gp-s5-rediseno` | **11/11 OK** (17,4 s) |
| `E2E_RUN=1 playwright test gp-e2e-ui5-0-axe-touched-routes-mock` | **34/35 OK**; reserva en §8 |

## 8 · Reserva declarada, aceptada en el cierre (no bloquea S5)

La suite de no regresión `gp-e2e-ui5-0-axe-touched-routes-mock` falla en `/trading @desktop`
por una violación **`heading-order`** (best-practice, impacto `moderate`): el readout de S2
emite `<h3>Estructura y niveles calculados</h3>` sin un `h2` previo en la ruta.

- **No es una regresión de S5**: el único cambio de S5 fuera de archivos nuevos es una opción
  opcional en `seedMercadoBrowserState` (por defecto `false`), y el readout pertenece al
  trabajo previo de S2 (archivo no rastreado `market-structure-readout.tsx`).
- **No es WCAG A/AA**: no hay violaciones `critical`/`serious`; el gate axe propio de S5
  (tags WCAG 2 A/AA) está limpio en la maximizada y en Asesor.
- **No se corrige en S5**: el plan prohíbe tocar código de producto. Se recomienda un
  seguimiento S2: degradar el `h3` a `h2` (o pasar `showHeading={false}` donde el bloque ya
  tiene cabecera visible). Queda a decisión de producto.

**Decisión de producto (2026-11-12).** La reserva se **acepta**: S5 se aprueba con ella, sin
reabrir §1–§7. La corrección de `heading-order` **no se ejecuta en este cierre** y se difiere a un
**seguimiento S2 independiente**, con su propia autorización. Este documento no abre ese slice,
no toca el readout de S2 ni modifica `showHeading`.

## 9 · Límites

- Playwright no corre en el CI de frontend: la evidencia E2E es reproducible en local, no un
  sello de CI.
- La matriz mock es determinista, no datos de producción.
- `PROJECT_STATE.md` y `CHANGELOG.md` no se tocan: producto aprobó el cierre y **decidió
  explícitamente excluirlos**. Conservan su última escritura (12/11 11:02 y 11/11 18:36) y este
  cierre no los abre para escritura.
- S0/F4-067 siguen sin autorizar; las modificaciones previas en `packages/py` y
  `apps/api-python` no forman parte de S5 y no se han tocado.
- Sin `git add` ni commit: el índice está vacío (`git diff --cached` vacío).

## 10 · Veredicto

**PASS funcional del rediseño S1–S4** en los seis escenarios, tres superficies y tres cortes,
con la reserva de accesibilidad de §8 **aceptada** y sin tocar producto. **Aprobado por producto
el 2026-11-12**; el acta de la aprobación vive en §11.

**No autorizado por esta aprobación.** Son decisiones distintas y ninguna se concede aquí:

- resolver S0 / sellar o commitear F4-067 (sigue sin autorizar);
- corregir `heading-order` (queda como seguimiento S2 independiente, no ejecutado);
- bump de versión, tag o publicación de una release;
- `git add`, commit, push o cambio de rama.

## 11 · Acta de aprobación de producto

| Dato | Valor |
|---|---|
| Fecha | 2026-11-12 |
| Decisión | Cierre documental de S5 **aprobado**, con la reserva de §8 aceptada |
| Alcance del acto | Solo este documento y el [`README.md`](evidence/s5-rediseno-2026-11-12/README.md) de su carpeta de evidencia |
| Excluido por decisión | `PROJECT_STATE.md`, `CHANGELOG.md`, bump, tag y Release |
| Estado de referencia | `HEAD` `bcdc4584` · índice vacío · rama `feat/f4-067-opinion-account-scope` |
| Git | Sin `git add`, sin commit, sin push, sin cambio de rama |

**Qué no cubre esta aprobación.** No se extiende a S0/F4-067 (sigue pendiente de autorización), ni
a la corrección de `heading-order` (seguimiento S2 independiente, no ejecutado), ni a la
publicación de una versión. Tampoco reabre S1–S5: §1–§7 se conservan tal como se certificaron y
las cifras de §7 no se re-miden en este acto documental.
