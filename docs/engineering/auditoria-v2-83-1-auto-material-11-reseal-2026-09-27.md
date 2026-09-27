# Auditoría externa — `v2.83.1-beta` / `AUTO-MATERIAL-11` (RE-SELLO): `APROBADO CON OBSERVACIONES`

> **Objeto auditado:** tag anotado **`v2.83.1-beta`** (objeto `e939bbf0` → commit `42c97bab`) ·
> **Versión:** `2.08.1-beta` · **Base (diff):** `v2.83-beta` (`2.08.0-beta`) · **AsOf:** 2026-09-27 ·
> **Alembic head:** `046_fill_reference_mid` · **Auditor:** externo, **desde un clon fresco de GitHub**
> (`github.com/jvelasca/Bolsa_V1.git`), nunca sobre el árbol local.
> **Veredicto:** **APROBADO CON OBSERVACIONES — 0 bloqueantes** (8 puntos: 6 PASS, 2 PARTIAL).

## 0. Alcance y método

El auditor clonó el repositorio en un directorio temporal, hizo `checkout` del tag `v2.83.1-beta` y
trabajó **solo** contra ese snapshot (árbol del clon verificado limpio antes y después de cada sonda).
Los hallazgos **no** impugnan la naturaleza docs-only ni el sellado del objeto: son del **instrumento de
`v2.83`** (`operability_audit.py`), **byte-idéntico** en este tag.

## 1. Identidad verificada del objeto

| Comprobación | Comando | Resultado |
|---|---|---|
| Tipo de objeto | `git cat-file -t v2.83.1-beta` | `tag` (**anotado**) |
| Objeto tag | `git rev-parse v2.83.1-beta` | `e939bbf00dee29213417d6f05fb0c266988a7bb6` |
| Commit del sello | `git rev-parse 'v2.83.1-beta^{commit}'` | `42c97bab64ea30dd3e211434654b42a87f250000` |
| Base del diff | `git rev-parse 'v2.83-beta^{commit}'` | `0ebf66302f41a4b226add449d0da4e8ad2397d5b` |
| Objeto tag base | `git rev-parse v2.83-beta` | `8cfe7f6f4f8f447e787d0619726c74f248a557e3` |
| Versión | `package.json` | `2.08.1-beta` |

## 2. Tabla de los 8 puntos

| # | Punto | Veredicto | Evidencia (comando → resultado) |
|---|---|---|---|
| 1 | Naturaleza del objeto | **PASS** | `cat-file -t` = `tag`; `^{commit}` = `42c97bab`; `package.json` = `2.08.1-beta`; `git status --porcelain` vacío antes/después |
| 2 | Diff acotado | **PASS** | `git diff --name-only v2.83-beta..v2.83.1-beta` = `package.json` + `CHANGELOG.md` + 10 `docs/engineering/*` (12 ficheros); filtro de ficheros prohibidos (`operability_audit`, `v2_83_window_audit`, `test_operability_audit`, `auto_simulation_worker`, gobernador, `alembic`…) → **0 coincidencias** |
| 3 | Semántica del instrumento | **PARTIAL** | `counts`/`coverage`/`rSum` suman solo días medidos y marcan `partial` (PASS); `window_rates` → `rate=None` sin días/denominador 0 y las 6 tasas con `numerator/denominator/coveredDays/source` (PASS); `render_window_audit` determinista cross-proceso y `n/d` en huecos (PASS); `enrich` preserva escalares (PASS) — **pero** ver `OBS-6`/`OBS-7` |
| 4 | Read-only de verdad | **PASS** | `--render`/`--json` sin `--out` → `exit 0`; listado recursivo del árbol idéntico antes/después; `operability_runs`/`evidence_runs`/`evidence_validations` inexistentes; único escritor = `out_path.write_text` (bajo `--out`); sin material → `exit 2` |
| 5 | Compuertas reproducidas | **PARTIAL** | `ruff` → `All checks passed!`; `lint-imports` → `Contracts: 4 kept, 0 broken`; `mypy` → `0 issues` (507 fuentes); `alembic heads` → `046_fill_reference_mid (head)`; `test_operability_audit.py` → **16 passed**; `packages/py/application/tests` → **2082 passed, 5 skipped** (2087 recogidos; los 5 son PG-gated) |
| 6 | Matriz adversarial | **PASS** | `MUTATIONS = 230` (M1..M230); matriz completa → `medidas: 230/230`, `0` «NADA», árbol intacto |
| 7 | Registro en CI | **PASS** | `test_operability_audit.py` explícito en el job `quality` de `python-ci.yml` y en el job `python` de `release-tag-ci.yml` |
| 8 | Citas CI dentro del tag | **PASS** | Dentro del tag, `evidencia-ci-tag-v2.83-2026-09-27.txt` trae la **cita real** (`36329460515`, SUCCESS), no el placeholder; `gh run view` confirma `36333090789` (tag `v2.83.1`, `headSha 42c97bab`) en success |

## 3. Hallazgos

| ID | Sev. | Defecto | Ubicación |
|---|---|---|---|
| **OBS-6** | **MEDIUM** | `enrich_rows_with_evidence` **sobrescribe** un funnel ya medido (reconstruye el funnel incondicionalmente) | `operability_audit.py:379` |
| **OBS-7** | LOW | el bloque `funnel` de `window_totals` suma filas `measured=False` (itera `rows`, no `measured_rows`) | `operability_audit.py:174` |
| **OBS-8** | LOW | códigos de salida del CLI documentados inexactos (`argparse` sale con `2`, la doc dice `1`) | doc de `v2_83_window_audit.py` / `plan-v2-83` §3.2 |

Reproducción de `OBS-6` (evidencia cruda del auditor):

```text
row funnel universe before: 8 orders before: 2
row funnel universe after : 999 orders after: 99
symbolsObserved preserved : 8
OVERWRITTEN
```

Reproducción de `OBS-7`:

```text
(A3 diagnostic: row measured=False universe=8 orders=2)
(A3 observed funnel aggregate: universe=8 orders=2 days=1)   # daysMeasured=0
```

## 4. Limitaciones declaradas (honestidad)

- **Ventana PAPER ≥4 días (`P3-2`/`P3-3`) NO certificada**: `operability_runs/` está gitignoreado y no
  existe bundle real; la tabla/`TOTAL`/tasas solo se re-derivan con fixtures deterministas.
- **`H-4` (LOW) sigue ABIERTO**: esta fase lo hace visible (`warnings: reason_contract`), no lo cierra.
- **Compuertas PG no reproducibles en local** (sin PostgreSQL): `2087 passed` se midió como
  `2082 passed + 5 skipped`.
- `lint-imports` no pudo lanzarse por su `.exe` (bloqueo de Control de aplicaciones de Windows); se
  reprodujo invocando el mismo CLI por módulo → `4 kept, 0 broken`.

## 5. Veredicto global

**APROBADO CON OBSERVACIONES — 0 bloqueantes.** El re-sello cumple lo que promete (versión, tag anotado,
diff acotado a `package.json` + docs, CLI estrictamente read-only, matriz 230/230, registro explícito del
test y cita real del CI **dentro** del tag). Las observaciones (`OBS-6` MEDIUM, `OBS-7`/`OBS-8` LOW) son
del instrumento de `v2.83`, quedan **ABIERTAS y declaradas** en la
[deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md) y **no** impugnan el sellado.
