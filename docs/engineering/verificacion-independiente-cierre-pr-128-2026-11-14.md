# Verificación independiente del cierre de PR #128 — PASS dentro del alcance declarado

**Fecha:** 2026-11-14 · **PR verificado:** [#128](https://github.com/jvelasca/Bolsa_V1/pull/128) *(squash en
`main`)* · **Commit integrado:** `ca0dcfe9` · **Bump verificado:** `2.11.192-beta` · **Naturaleza:** verificación
**independiente y complementaria**. No cambia código, no toca umbrales, no reabre el cierre ni modifica ningún
veredicto publicado.

Este documento **no sustituye** los cierres previos. Se conserva como expediente de la verificación que los reprodujo
y que precisó dos matices de interpretación y dos observaciones de robustez.

---

## 1 · Dictamen consolidado

**PASS.** El cierre de PR #128 queda verificado dentro del alcance declarado: integración, CI, reproducción local de
los tests dirigidos, reproducción del descubrimiento y de los cuatro replays de cohorte, y reproducción del sello de
cohorte.

Las cuatro fronteras declaradas se mantienen **intactas** (§7).

## 2 · Integración y CI

| Comprobación | Resultado |
| --- | --- |
| Estado del PR | **MERGED** |
| `main` tras la integración | **`ca0dcfe9`** |
| Checks de CI | **17/17 satisfactorios** |

La discrepancia del asunto del *squash* (`#128` repetido en el título) es **cosmética** y no afecta al contenido
integrado ni a la trazabilidad del commit.

## 3 · Reproducción local

| Comprobación | Resultado |
| --- | --- |
| `ruff check` sobre los ficheros tocados | **limpio** |
| Tests dirigidos del cierre | **76 pasados** |
| Subconjunto amplio ejecutado en local | **5.254 pasados** |
| `mypy` local | **6 errores**, atribuidos a dependencias (§3.1) |

### 3.1 Los seis errores locales de `mypy` no son regresión de #128

Se reproducen seis errores que **no aparecen en CI**. La causa identificada es la diferencia de dependencias entre el
entorno local y el `uv sync --frozen` que usa CI: el entorno local resuelve versiones de paquetes distintas de las
selladas en el lockfile, y `mypy` analiza contra esos stubs.

Conclusión: **no hay evidencia de regresión de #128**. La verificación de tipos que cuenta es la del job de CI, que
pasa sobre el entorno congelado.

## 4 · Cohorte: descubrimiento y rejuegos reproducidos

Se reprodujeron el descubrimiento de días y los **cuatro replays** (`2026-11-05`, `2026-11-06`, `2026-11-09`,
`2026-11-10`) sobre la cuenta de la ventana.

**El sello de cohorte coincide bit a bit:**

| Campo | Valor reproducido |
| --- | --- |
| `samples` | **4** |
| `required` | **12** |
| `verdict` | `insufficient_sample` |
| `reasons` | `insufficient_sample:4/12` |
| `hash` | `c2a42b99b96ae0a8561664b832386ac242ba97a2f2711e7f45822c43d6208ccc` |

Que el hash de cohorte sea **estable entre rejuegos** es correcto por construcción: `_payload_hash` cubre solo
veredicto, muestra, días certificados, fallos y motivos
([`dia_d_certification.py`](../../packages/py/application/src/bolsa_application/dia_d_certification.py),
`DiaDCohortCertificationV1.to_dict`). No incluye marcas de tiempo.

## 5 · Dos matices de interpretación que se conservan expresamente

### 5.1 Trazabilidad: el 100 % son las referencias **usadas**, no todas las **emitidas**

La afirmación «los cuatro días resuelven el **100 %** de sus referencias por ciclo» es correcta solo si se lee sobre
las **referencias de riesgo efectivamente utilizadas**: **12/12** por día. No debe leerse sobre las referencias
**emitidas**, que la reproducción cuenta como **9/18 por ciclo y día**. Son dos conjuntos distintos y el «100 %»
habla solo del primero.

No es un fallo: las referencias emitidas y no usadas son respaldo del instrumento para ciclos que ese día no llegan a
medirse, no descartes silenciosos. Pero la redacción original admitía la lectura equivocada, y se precisa en
[`reparacion-as-run-2026-11-13.md`](./reparacion-as-run-2026-11-13.md) §6.

### 5.2 Hashes: sellos de ejecución, no huellas reproducibles

`_seal()` recalcula el hash sobre el artefacto **completo**, incluida `meta.generatedAt`
([`v2_102_dia_d_as_run.py`](../../apps/api-python/scripts/v2_102_dia_d_as_run.py), `_seal` y `meta.generatedAt`).
Consecuencia:

- `artifact.hash` **identifica el artefacto de esa ejecución**; no es una huella reproducible entre rejuegos.
- Lo que **sí** es reproducible es la **igualdad de las mediciones** (mismos `realizedR`, `pnlCurrency`,
  `riskCurrency`, ciclos y tramos) y el **sello estable de cohorte**.
- La limitación **no invalida** el cierre: la certificación no prometió hashes reproducibles por artefacto
  individual.

Se precisa en [`cohorte-dia-d-as-run-2026-11-13.md`](./cohorte-dia-d-as-run-2026-11-13.md) §3.

## 6 · Dos observaciones de robustez

### 6.1 `rglob` puede incorporar copias de seguridad y duplicar días

`load_artifacts()` descubre con `rglob("as-run-*.json")` sobre todo el árbol de `operability_runs/dia-d-as-run/`
([`cohorte_as_run.py`](../../scripts/ops/cohorte_as_run.py), `load_artifacts`, con `_DAY_SUFFIX_RE` exigiendo
`as-run-AAAA-MM-DD.json`). Una copia guardada con ese mismo nombre en un subdirectorio del árbol (por ejemplo
`backup/as-run-2026-11-05.json`) **duplicaría el mismo día** en la cohorte y alteraría `samples`: el artefacto lleva
su `day` en el payload, así que se cuenta dos veces.

Recomendación: **mantener los respaldos fuera del árbol de entrada** de `load_artifacts()`. No se corrige el código
aquí; se documenta como observación para futuras ejecuciones.

### 6.2 Alcance no ejecutado en local

Los jobs dependientes de servicios y de Playwright se han comprobado por su **resultado publicado** en CI, **no**
mediante una ejecución local independiente. Se declara para no vender como reproducido lo que solo se leyó.

## 7 · Las cuatro fronteras, intactas

1. **No se infieren ni reconstruyen `cycle_id` ausentes** en registros históricos. El join es exacto por id de orden;
   sin orden en el linaje se declara **sin ciclo**.
2. **Cuatro días de muestra no alcanzan el mínimo de doce.** El veredicto sigue siendo `insufficient_sample`, no
   `certified`.
3. **`realizedR` es una medición reproducida, no una demostración de rentabilidad.** La muestra es insuficiente por
   construcción.
4. **Este cierre no autoriza activar `AUTO` ni operar con dinero real.** `activationAllowed` sigue en `false`.

## 8 · Recomendación

Conservar este informe como **verificación independiente complementaria**, **sin abrir ahora una corrección de código
ni modificar el cierre**. Las dos imprecisiones quedan precisadas en los documentos origen y las dos observaciones de
robustez quedan documentadas; ninguna justifica ampliar el alcance del PR ya integrado.

## 9 · Referencias

- [Cierre de auditoría del DÍA-D as-run](./cierre-auditoria-dia-d-as-run-2026-11-13.md)
- [Reparación del instrumento as-run y recertificación de la cohorte](./reparacion-as-run-2026-11-13.md) §6
- [Cohorte DÍA-D as-run con datos reales](./cohorte-dia-d-as-run-2026-11-13.md) §3–§4
- Código: [`dia_d_as_run.py`](../../packages/py/application/src/bolsa_application/dia_d_as_run.py),
  [`dia_d_certification.py`](../../packages/py/application/src/bolsa_application/dia_d_certification.py),
  [`v2_102_dia_d_as_run.py`](../../apps/api-python/scripts/v2_102_dia_d_as_run.py),
  [`cohorte_as_run.py`](../../scripts/ops/cohorte_as_run.py)
