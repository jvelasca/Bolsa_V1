# Dictamen de aceptación — cierre técnico de los siete to-dos

- **Fecha:** 2026-10-26
- **Rama:** `audit/c1-c4-integrity-fold-2026-10-25`
- **Naturaleza:** **registro de aceptación**. No es una re-auditoría, no modifica código, CI,
  migraciones, `package.json`, PR [#76](https://github.com/jvelasca/Bolsa_V1/pull/76), tags, pin
  PAPER ni `operability_runs/`.
- **Objeto:** aceptar como **publicado y respaldado por CI** el cierre de los siete to-dos
  derivados de [`dictamen-paper-multidia-operativa-auto-2026-10-26.md`](./dictamen-paper-multidia-operativa-auto-2026-10-26.md),
  contrastados en [`verificacion-dictamen-paper-multidia-2026-10-26.md`](./verificacion-dictamen-paper-multidia-2026-10-26.md) §8.
- **C-4 no se reabre.** Este dictamen no certifica rentabilidad ni autoriza dinero real.

Este documento fija en qué nivel queda cada afirmación. Mantiene **tres niveles separados** —cierre
del trabajo, certificación técnica y validación operativa— y conserva visibles los tres residuales
declarados, que no se cierran aquí ni se reclasifican.

---

## 1. Baseline verificado

### 1.1 Run de CI

| Elemento | Valor comprobado |
| --- | --- |
| Run | [`40314593833`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40314593833) (`Python CI`) |
| `headSha` | `2fa7d33dcc7bc92b0f34b84aeb04adaa476c469e` |
| `status` / `conclusion` | `completed` / **`success`** |
| Jobs | **5/5 `success`**: `quality`, `auto-v2-durable-pg`, `paper-forward-pg`, `lifecycle-pg`, `grammar-discovery-pg` |

Dentro de `auto-v2-durable-pg` corren, además del lote durable, los pasos propios de este cierre:

- `Pytest HardKill recovery` con `AUTO_HARDKILL_PG_REQUIRED=1` — **126 passed**.
- `Pytest C-4 coste ambiguo PG (fail if skipped)` — **3 passed**.
- Ruta REAL del productor — **7 passed**.
- Cadena diaria — **1 passed**.
- Guarda anti-skip de C-4 — `success`.

En `quality`: **`5405 passed, 50 skipped`**, con `ruff` sobre la configuración **raíz**,
`lint-imports` 4/4 y `mypy` de árbol completo. Los `50 skipped` **no** son la suite de este cierre:
`test_auto_v2_audit_regressions.py` es hermética (sin PostgreSQL ni red) y no contiene marcadores de
skip; la suite PG corre en los pasos propios de `auto-v2-durable-pg` con guarda anti-skip.

### 1.2 Commits publicados

| SHA | Contenido | Alcance |
| --- | --- | --- |
| `b11e26ae` | Motor, pruebas y **cableado de CI** del cierre (`P-1`, `R-1`, `R-2`, `P-2`, `R-4`, `W-1`, y el gate de `P-3`) | 20 ficheros |
| `fe0ea524` | Anexo de verificación y runbook | 2 ficheros |
| `2fa7d33d` | Corrección de Ruff (**sólo lint**) | 3 ficheros |
| `c1d2d9da` | Certificación documental del cierre y corrección del veredicto del stop | 1 fichero |

**Cuál certifica el run:** `2fa7d33d`. `c1d2d9da` es el commit **documental** posterior y **no** es
el `headSha` del run. La distinción es la misma que ya rige para C-4 (`b3456897` certifica el run
`40287111793`; `6a9f7cab` publica el documento).

**El cableado de CI dentro de `b11e26ae` no es cosmético.** Ese commit modifica
`.github/workflows/python-ci.yml` en dos puntos: añade `AUTO_HARDKILL_PG_REQUIRED: '1'` al job
`auto-v2-durable-pg` y mete `test_auto_v46_hardkill_recovery_pg.py` en su lista explícita de
ficheros. Es lo que convierte el HALT durable en certificación **por commit** en vez de sólo en el
tag, y es la premisa de la frase de §1.1 sobre las guardas anti-skip. El rótulo anterior («motor y
pruebas») lo omitía; se corrige aquí.

### 1.3 Alcance de la comprobación

Esta aceptación se apoya en la consulta de los jobs y de los metadatos de los cuatro commits. **No**
se ha inspeccionado línea por línea todo el código de producción ni se ha reproducido la suite
completa en esta sesión. Por tanto no se presenta como auditoría funcional exhaustiva independiente;
la certificación técnica es la del run, y su alcance es el que el propio CI declara.

---

## 2. Dictamen por frente

Los siete to-dos son las siete filas de cierre de
[`verificacion-dictamen-paper-multidia-2026-10-26.md`](./verificacion-dictamen-paper-multidia-2026-10-26.md) §8.1:
`R-1`, `R-2`, `P-1`, `P-2` (contable), `P-2` (MAE), `W-1` y `R-4`.

| Frente | Estado declarado | Qué lo sostiene | Qué sigue abierto |
| --- | --- | --- | --- |
| **Siete to-dos** | **Implementados y publicados** | `b11e26ae` + CI verde `40314593833` sobre `2fa7d33d` | Residuales de §4 |
| **P-1 · parada dura** | **Contrato de bloqueo reforzado** | Latch `KILL_STATE_UNREADABLE` fail-closed en cada tick; liberación **sólo** con lectura válida (sin fila o fila liberada con `reconciliation_id`); veto también en el camino legacy (`AUTO_ENGINE_SIM_V2=0`), con SELL permitido | **Permanencia** durante fallos persistentes: el latch es local y no deja evidencia durable del tramo ilegible |
| **R-1 · readopción** | **Recuperación transitoria cubierta** | Latch `_projection_read_failed` veta aperturas de cualquier símbolo; el fallo del canónico **no** consume la readopción (`_readopted` queda `False`) y el tick siguiente reintenta; se limpia sólo tras lectura + reconciliación válidas | El fail-open exige que falle **sólo** la proyección (si la equity también es ilegible, el BUY ya estaba vetado). No es un cierre de todos los modos de fallo |
| **R-2 · filas duplicadas** | **Invariante medible; no apropia la cantidad de otro motor** | Con más de una fila viva el motor conserva la cantidad de **su** fila y declara `UNKNOWN` (aperturas vetadas); `live_row_invariant_report()` publica `Σ filas vivas` frente al canónico (`delta`, `consistent`); el cierre multi-motor se declara `position_row_unreconciled` y se acota a la fila propia | **Reparación de datos históricos:** una fila ya inflada **no se cura sola**; exige reconciliación explícita de operador. Prohibida la reparación heurística: el reparto entre motores no es determinable desde el total |
| **P-2 · MAE y fill D1** | **Semántica explícita** | El precio declarado (`settle_price` si es válido, si no `price`) se calcula una vez y gobierna settlement, hecho aplicado, `_sim_realized_pnl` y `_v2_track_reduce`; el MAE por barra declara `source="bars"` cuando viene de un extremo de la barra | El **fill D1 es un precio contable, no ejecutable**: con barras diarias se desconoce el orden intrabar. No debe presentarse como ejecución real |
| **R-4 · configuración** | **Documentada** | `AUTO_ENGINE_SIM_ENGINE_ID` en `.env.example` y en el runbook de la ventana forward; el arranque durable falla de forma explícita sin ella (`EngineIdentityMissingError`) y el scheduler acota el fallo a AUTO sin tumbar el resto de workers | La guarda protege el arranque durable; no obliga a un operador que lance el script forward a mano con la variable correcta |
| **W-1 · vigía** | **Fail-closed en el gate ausente** | `MEDIDO` sin gate verificable pasa a `INCONCLUSIVE` con severidad `alert` (`gate_missing` si no hay bloque o es `null`, `gate_inconclusive` si existe pero no acredita); un gate declarado o con ciclos > 0 sigue `OK` | **Días históricos sin gate:** no pueden re-certificarse como `OK` desde el ledger. El cierre exige que el runner publique el gate del día |
| **PAPER / AUTO** | **Sin cambio operativo** | Pin `.161` autoconsistente; AUTO **OFF**; operativa **100 % PAPER virtual** | Ventana **`INCONCLUSIVE`**: `d=5 e=0 c=0` |
| **Rentabilidad** | **No demostrada** | — | `0/32` ciclos medibles, `evidence_ready = false`. Un CI verde no es evidencia estadística |

**P-3 queda cerrado por el mismo run, pero no cuenta en los siete.** El anexo §8 lista ocho huecos:
los siete de la tabla más `P-3` (cobertura de CI asimétrica de la durabilidad, que dejaba la
recuperación del HALT sólo en el tag). `b11e26ae` lo cierra al mover
`test_auto_v46_hardkill_recovery_pg.py` a `auto-v2-durable-pg` con `AUTO_HARDKILL_PG_REQUIRED=1`, y
el run lo ejecuta (`126 passed`). Se declara aquí porque el cierre técnico lo incluye, pero la
aceptación explícita se limita a los **siete to-dos** que originaron este dictamen.

**Salvedad sobre la fila PAPER/AUTO.** «Pin `.161` autoconsistente» no es una medición de este
commit: se hereda de
[`auditoria-pr-76-vigia-ventana-2026-10-25.md`](./auditoria-pr-76-vigia-ventana-2026-10-25.md) (H2,
`freezeStatus` compara `appsHash`/`packagesHash` y `commit` es etiqueta). Este registro no re-mide el
pin ni lo mueve.

---

## 3. Tres niveles que no se pueden fundir

| Nivel | Qué acredita | Qué no acredita |
| --- | --- | --- |
| **Cierre del trabajo** | Los siete to-dos están implementados, publicados en `audit/c1-c4-integrity-fold-2026-10-25` y cubiertos por pruebas que el CI ejecuta | Que la muestra operativa sea suficiente, ni que no queden residuales |
| **Certificación técnica** | El run `40314593833` sobre `2fa7d33d` está verde 5/5; los contratos se cumplen y las regresiones no vuelven | Que el comportamiento medido bajo un árbol anterior al pin sea válido bajo el pin; que el HALT durable esté certificado en un push arbitrario más allá de lo que el job declara |
| **Validación operativa** | Nada nuevo: los tres `MEDIDO` siguen con `0` episodios y `0` ciclos medibles | Que la ventana avance, que los días históricos se reinterpreten o que la estrategia sea rentable |

Dos precisiones que este dictamen mantiene de forma explícita:

1. **Un cierre contable coherente no equivale a una ejecución bursátil real.** Que settlement, hecho
   aplicado, P&L y reducción de estado usen **el mismo** precio declarado es una garantía de
   consistencia interna (§8.2 del anexo), no una afirmación sobre lo que el mercado habría permitido
   ejecutar.
2. **Una suite verde no demuestra que los indicadores generen señales rentables.** El CI mide
   integridad de rutas y ausencia de regresiones; la ventaja estadística exigiría muestra,
   intervalo de confianza y comparación con un benchmark, y no existe ninguna de las tres.

---

## 4. Residuales visibles (no cerrados por este cambio)

Los tres se mantienen abiertos y **no** se reclasifican como resueltos:

1. **P-1 · permanencia.** El latch `KILL_STATE_UNREADABLE` es local: no se persiste porque la
   escritura puede fallar por la misma causa que la lectura. Cada proceso nuevo lo re-deriva
   (fail-closed en ambos casos), pero **no queda evidencia durable** del tramo en que el latch fue
   ilegible. Diseñar esa evidencia, si se requiere, es trabajo pendiente.
2. **R-2 · fila histórica inflada.** `live_row_invariant_report()` **mide** pero no repara. La
   cantidad ya inflada necesita un **procedimiento controlado de reconciliación** antes de dar por
   buena una cuenta que operó con el defecto, y mientras siga abierta el cierre se declara
   (`position_row_unreconciled`). No se backfillea y no se reparte el total por heurística.
3. **W-1 · días históricos sin gate.** Tratar `MEDIDO` sin gate como `INCONCLUSIVE` es fail-closed,
   pero implica que **ningún día histórico sin gate puede re-certificarse como `OK`** desde el
   ledger: la acreditación exige que el runner publique el gate del día. No se reclasifica ningún
   día y no se reinterpreta el material existente.

Ninguno de los tres se cierra con una prueba nueva: `P-1` y `W-1` son de diseño/evidencia y `R-2`
es operativo. Declararlos es el cierre correcto en este nivel.

---

## 5. Límites y no-cambios

- **No** es una auditoría funcional exhaustiva independiente: no se ha revisado todo el código de
  producción ni reproducido la suite completa en esta sesión.
- **C-4 no se reabre.** Los tres escenarios de coste ambiguo siguen certificados en `b3456897`
  (run `40287111793`). `R-2` es un hueco **adyacente de cantidad**, no una refutación del coste.
- **No se modifican** el pin PAPER, los tags, la PR #76 ni las ramas. Este registro es
  exclusivamente documental.
- **Estados operativos sin cambio:** AUTO **OFF**, operativa **PAPER virtual**, ventana
  **`INCONCLUSIVE`**, `evidence_ready = false`, rentabilidad **no demostrada**.

---

## 6. Estado de publicación de los documentos de auditoría

Los dos dictámenes de origen se publican **en este mismo commit**, junto con este registro y con la
evidencia C-4:

| Fichero | Estado en git | Contenido |
| --- | --- | --- |
| [`dictamen-c4-postgresql-real-2026-10-26.md`](./dictamen-c4-postgresql-real-2026-10-26.md) | **publicado aquí** | Dictamen C-4 completo |
| [`dictamen-paper-multidia-operativa-auto-2026-10-26.md`](./dictamen-paper-multidia-operativa-auto-2026-10-26.md) | **publicado aquí** | Auditoría PAPER multi-día, como **snapshot** de `6a9f7cab` |
| [`evidencia-c4-coste-ambiguo-pg-2026-10-26.md`](./evidencia-c4-coste-ambiguo-pg-2026-10-26.md) | **publicado aquí** | Enlace al dictamen C-4 (antes en el working tree) |

La evidencia que interpretan ya estaba publicada: el anexo
[`verificacion-dictamen-paper-multidia-2026-10-26.md`](./verificacion-dictamen-paper-multidia-2026-10-26.md)
(`fe0ea524`), la corrección de Ruff (`2fa7d33d`) y la certificación documental (`c1d2d9da`).

Dos precisiones que evitan leer esta publicación como una reescritura:

1. El dictamen PAPER **no se retoca**: se publica tal como se midió en `6a9f7cab` y lleva una **nota
   de publicación** fechada que declara qué secciones son históricas (§1, §2.1, §2.2, §11.6) y cuál
   es el estado vigente. Sus veredictos `PARCIAL`/`HUECO DECLARADO` son pre-fix.
2. Los enlaces cruzados resuelven porque los tres ficheros entran **en el mismo commit**. Publicar
   el bloque de `PROJECT_STATE.md` sin ellos sí habría dejado los enlaces rotos para un lector de
   GitHub.

**Commit local, no publicado todavía.** Este registro se amenda sobre el commit local que aún no se
ha empujado; hasta que exista `push`, nada de esto está en GitHub y `main`, la rama remota, el tag
`v2.88.161-beta`, la PR [#76](https://github.com/jvelasca/Bolsa_V1/pull/76) y el pin PAPER siguen
intactos.

---

## 7. Reproducción y cierre

```bash
gh run view 40314593833 --json headSha,conclusion,workflowName,status
gh run view 40314593833 --json jobs
git show --stat --oneline b11e26ae fe0ea524 2fa7d33d c1d2d9da
git status --short
```

**Cierre.** Se acepta el cierre técnico de los siete to-dos como **publicado y respaldado por CI**,
con los límites de §5 y los tres residuales de §4 visibles. No corresponde reabrir C-4 por estos
cambios, ni modificar el pin PAPER o los tags como consecuencia de este dictamen. La operativa sigue
en **AUTO OFF**, **PAPER virtual**, ventana **`INCONCLUSIVE`** y **rentabilidad no demostrada**.
