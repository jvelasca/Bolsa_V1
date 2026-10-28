# Adenda de precisión — filtros que explican la ausencia de CI en el corpus `.170`

> **AsOf:** 2026-10-28 · **Rama:** `ui/auto-hold-provenance-2026-10-28` (**no** `main`) · **Objeto certificado:**
> tag anotado `v2.88.170-beta` (objeto `3e7948417c22bf9e767848331fe0d57fc2154e98` → commit
> `babfe228f9d81eb2b18be787465af588b5ff170b`), **intacto**.
> **Naturaleza:** adenda **documental** POST-TAG, read-only sobre el sello. **Precisa** el fundamento de la ausencia
> de run en el corpus documental; **no** reescribe ninguno de los documentos que cita, **no** cambia su veredicto,
> **no** altera código, CI, migraciones, `package.json`, tags ni el pin PAPER, y **no** abre PR ni merge a `main`.
> **Veredicto:** el **hecho** (el corpus no disparó CI) era correcto; el **fundamento** escrito en dos documentos
> era incompleto. Se corrige el fundamento sin reabrir el cierre.

---

## 0. Qué es medición propia y qué es cita

Esta adenda sí repite las consultas, a diferencia del [acta de cierre
documental](./acta-cierre-documental-v2.88.170-beta-2026-10-28.md) §0, que declaró aceptar sobre evidencia
aportada.

| Afirmación | Procedencia | ¿Medida al firmar? |
| --- | --- | --- |
| Filtros y disparadores de los seis workflows | Lectura de `.github/workflows/*.yml` en esta rama | **Sí** (ficheros) |
| `0` runs para `09434fbd` y para `bf1433e7` | `gh api "repos/jvelasca/Bolsa_V1/actions/runs?head_sha=<sha>"` ⇒ `total_count: 0` | **Sí** (API de Actions) |
| `9` runs sobre `babfe228`, **todos** `success` | Misma consulta por `head_sha` | **Sí** |
| `Release tag CI` [`40727162474`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40727162474) `completed`/`success`, `head_sha` `babfe228…`, `event: push` | `gh api repos/jvelasca/Bolsa_V1/actions/runs/40727162474` | **Sí** |
| Identidad del tag igual en local y en `origin` | `git rev-parse` y `git ls-remote --tags origin` | **Sí** |
| El corpus `.170` no está en `origin/main` (`26250187`) ni en el `main` local (`815ed4d0`) | `git ls-tree -r --name-only` sobre ambas referencias | **Sí** |
| Sin PR para esta rama | `gh pr list --head ui/auto-hold-provenance-2026-10-28 --state all` ⇒ sin salida | **Sí** |
| CI del árbol certificado (14 jobs `success`, `replay-repro` `REPRODUCIDO`, artefacto `GREEN`) | Nucleo del [audit pack](./audit-pack-v2.88.170-beta-2026-10-28.md) y de la [auditoría independiente](./auditoria-independiente-v2.88.170-beta-2026-10-28.md) | **No** (se citan; esta adenda no re-audita el sello) |

---

## 1. Las tres causas, no una

La formulación rigurosa es esta: **existen rutas documentales concretas cubiertas por algunos workflows, pero
ninguna cubre este corpus**, y el workflow de release se activa por la publicación de tags `v*`. Por tanto, que un
commit documental no haya disparado CI es compatible con el diseño observado, pero **no** porque «los workflows
excluyan la documentación»: es porque ninguna de las rutas documentales que sí están en un filtro alcanza a estos
ficheros, y porque los dos workflows restantes no se disparan por push a esta rama.

### 1.1 Cuatro workflows filtran por `paths`, y sus rutas `docs/` son ficheros concretos

| Workflow | Filtro | Rutas `docs/` incluidas |
| --- | --- | --- |
| `frontend-ci` | `apps/web/**`, `packages/shared/**`, `package.json`, `pnpm-lock.yaml`, `pnpm-workspace.yaml`, `turbo.json`, `eslint.config.js`, módulo de calibración, el propio workflow | **Ninguna** |
| `python-ci` | `apps/api-python/**`, `packages/py/**`, `scripts/verify/**`, `pyproject.toml`, `Makefile`, el propio workflow | **Ninguna** |
| `fase2-scientific` | `packages/py/{application,domain,infrastructure}/**`, rutas de `research.py`, `packages/database/prisma/**`, `scripts/research/verify_fase2*`, el propio workflow | [`.github/workflows/fase2-scientific.yml`](../../.github/workflows/fase2-scientific.yml) L15-16 y L28-29: `docs/engineering/research-lifecycle.md` y `docs/adr/018-fase2-evidence-store-v0.md` |
| `optimize-lab` | `apps/web/src/features/backtests/**`, rutas de `backtests.py`, `packages/py/analytics/**`, `packages/shared/src/cognitive/**`, `packages/py/application/**`, `packages/shared/src/optimize-api.ts`, `scripts/research/verify_optimize*`, `verify_oos_warmup.py`, `package.json`, `pnpm-lock.yaml`, el propio workflow | [`.github/workflows/optimize-lab.yml`](../../.github/workflows/optimize-lab.yml) L19 y L35: `docs/engineering/research-lifecycle.md` |

Las **dos** únicas rutas `docs/` que aparecen en un filtro de este repositorio son, por tanto,
`docs/engineering/research-lifecycle.md` y `docs/adr/018-fase2-evidence-store-v0.md`. **Ninguna** de ellas cubre
`docs/engineering/acta-cierre-documental-…`, `docs/engineering/dictamen-tecnico-…`,
`docs/engineering/audit-pack-…`, `docs/engineering/PROJECT_STATE.md` ni `docs/engineering/evidence/v2.88.170/**`.

### 1.2 `gitleaks` no se excluye por `paths`, sino por rama

[`.github/workflows/gitleaks.yml`](../../.github/workflows/gitleaks.yml) L4-6 fija `push` solo para
`branches: [main, master, 'stage/**']` y `pull_request` sin filtro. Un push a
`ui/auto-hold-provenance-2026-10-28` **no** lo activa por rama, no por ruta. Atribuir su ausencia al filtro de
`paths` es, literalmente, falso: ese workflow no tiene filtro de `paths`.

### 1.3 `release-tag-ci` solo se dispara por tag

[`.github/workflows/release-tag-ci.yml`](../../.github/workflows/release-tag-ci.yml) L6-10 declara `push: tags:
['v*']` y `workflow_dispatch`, sin filtro de rutas (su propia cabecera lo dice: «docs-only stamp también
certifica»). Un commit en rama no lo activa **de ninguna manera**, ni con cambios de código; solo un tag `v*`.

---

## 2. Lo medido sobre los runs

| Sha | Naturaleza | Runs (`total_count`) |
| --- | --- | --- |
| `babfe228…` | Commit sellado por `v2.88.170-beta` | **9**, todos `success`: 4 de rama (`Frontend CI`, `Python CI`, `Optimize lab`, `Fase 2 scientific`, `16:28:08Z`) + 4 del push del tag (mismos cuatro, `head_branch: v2.88.170-beta`, `16:33:41Z`) + `Release tag CI` `40727162474` |
| `bf1433e7…` | Corpus del dictamen (`4` ficheros, `+269/−17`, solo `docs/`) | **0** |
| `09434fbd…` | Publicación del acta (`3` ficheros, `+187/−0`, solo `docs/`) | **0** |

Comando reproducible para cualquier sha:

```bash
gh api "repos/jvelasca/Bolsa_V1/actions/runs?head_sha=<sha>" --jq '.total_count'
```

Consecuencia: la ausencia de run en el corpus **está medida contra la API**, no inferida solo del YAML. Lo que el
YAML aporta es la **causa**; la API aporta el **hecho**.

---

## 3. Las dos formulaciones que esta adenda precisa

| Documento | Línea | Formulación publicada | Precisión |
| --- | --- | --- | --- |
| [`auditoria-independiente-v2.88.170-beta-2026-10-28.md`](./auditoria-independiente-v2.88.170-beta-2026-10-28.md) | 49 | «no dispara ningún workflow porque **los cuatro de rama** están filtrados por `paths` y `docs/**` no está en la lista» | Incompleto en dos puntos: (a) no todo `docs/**` está fuera de los filtros —hay dos rutas documentales dentro—, aunque ninguna alcance al corpus; (b) omite que `gitleaks` se filtra **por rama** y que `release-tag-ci` solo responde a tags `v*` |
| [`audit-pack-v2.88.170-beta-2026-10-28.md`](./audit-pack-v2.88.170-beta-2026-10-28.md) | 87-90 | «no dispara workflows: **los cuatro** workflows de rama filtran por `paths` (…)» | Atribuye al filtro de rutas la totalidad de la ausencia; la causa es triple (§1.1–§1.3) |

**Qué no se corrige y por qué.** El **hecho afirmado** —no hubo run para ese sha— es correcto y está confirmado en
§2. Lo impreciso es el **fundamento**. Esta adenda lo precisa; los dos documentos citados **no se reescriben**, en
coherencia con la política del corpus (un acto nuevo por encima, no una enmienda del pasado). Quien lea solo
aquellos dos documentos obtiene la conclusión correcta con un razonamiento incompleto; leyendo esta adenda obtiene
el razonamiento completo.

El [acta de cierre documental](./acta-cierre-documental-v2.88.170-beta-2026-10-28.md) §0 y §1 ya usa la formulación
precisa (nombra las dos rutas concretas y declara que `release-tag-ci` dispara solo por tag); **no requiere
corrección**.

---

## 4. Cadena de commits del corpus

| Commit | Papel | Diff |
| --- | --- | --- |
| `e77246d2` | Audit pack y auditoría independiente | solo `docs/`, sin run |
| `582d2cbf` | Declara que el commit POST-TAG es `docs`-only | solo `docs/`, sin run |
| `bf1433e7` | **Corpus aceptado** por el acta: dictamen técnico de aceptación | `4` ficheros, `+269/−17`, solo `docs/` |
| `09434fbd` | **Publicación** del acta de cierre documental | `3` ficheros, `+187/−0`, solo `docs/` |

Precisión formal: el acta declara «**Commit del corpus:** `bf1433e7`» en su cabecera. Eso identifica el **contenido
aceptado**, no el commit que la publica —el acta nace, junto con las 8 líneas añadidas al dictamen técnico, en
`09434fbd`—. Las dos referencias son correctas en su papel y **no se fusionan en una sola**: `bf1433e7` es lo que
se acepta; `09434fbd` es desde donde se lee el acta. El dictamen técnico, al decir «sobre el commit `bf1433e7`»,
tampoco nombra su propio commit de publicación; esta adenda lo fija aquí.

---

## 5. Invariantes que esta adenda no toca

- **Sin re-sello:** `v2.88.170-beta` sigue siendo objeto `3e794841…` → commit `babfe228…`, igual en local y en
  `origin`. `v2.88.169-beta` sigue `d31df9b3` → `3ce94048`.
- **Pin PAPER** sin tocar; los días previos siguen `STALE`.
- **AUTO OFF**; ventana PAPER **`INCONCLUSIVE`** (`0/2` episodios, `0/32` ciclos).
- **Sin PR** para la rama y **sin merge a `main`**; el corpus sigue viviendo solo en
  `ui/auto-hold-provenance-2026-10-28` y un clon por defecto no lo obtiene.
- `R-170-1`, `P2-03` y `P2-11` siguen **abiertos** y se abordan como trabajos separados.
- **Sin certificación financiera:** CI verde y `REPRODUCIDO` no demuestran rentabilidad, exactitud del P&L neto ni
  valoración multidivisa completa.

---

## 6. Cómo se falsa esta adenda

```bash
# §1.1 — las dos únicas rutas docs/ en filtros de paths
grep -rn "docs/" .github/workflows/*.yml     # solo fase2-scientific y optimize-lab (+ fixtures de release-tag-ci)

# §1.2 — gitleaks filtra por rama, no por paths
sed -n '3,7p' .github/workflows/gitleaks.yml

# §1.3 — release-tag-ci solo por tag v*
sed -n '6,10p' .github/workflows/release-tag-ci.yml

# §2 — el corpus no tiene run; el sello sí
gh api "repos/jvelasca/Bolsa_V1/actions/runs?head_sha=bf1433e7db1d5404fa68c41ef8c3f912fe907e53" --jq '.total_count'  # 0
gh api "repos/jvelasca/Bolsa_V1/actions/runs?head_sha=09434fbd938f8e23637443a708e29230cdaa7ebc" --jq '.total_count'  # 0
gh api repos/jvelasca/Bolsa_V1/actions/runs/40727162474 --jq '.conclusion'                                        # success

# §4 — los dos commits existen con esos diffs
git show --stat bf1433e7
git show --stat 09434fbd

# §5 — sello inmóvil y corpus fuera de main
git rev-parse 'v2.88.170-beta^{tag}'   # 3e7948417c22bf9e767848331fe0d57fc2154e98
git ls-tree -r --name-only origin/main docs/engineering | grep acta-cierre-documental   # sin salida
gh pr list --head ui/auto-hold-provenance-2026-10-28 --state all                        # sin salida
```

**Predicción falsable sobre este mismo commit:** por las tres causas de §1, el commit que publica esta adenda
tampoco debe producir run. Si `gh api "…/actions/runs?head_sha=<sha de esta adenda>"` devolviera algo distinto de
`0`, esta sección sería falsa en su fundamento y debería corregirse con un acto nuevo.

---

## 7. Recomendación

Conservar el corpus en la rama con esta adenda como **precisión trazable** del fundamento, sin re-sello, sin merge
a `main` y sin nueva publicación de versión. Cuando se aborde `R-170-1`, `P2-03` o `P2-11`, deben enlazar al §4 del
[dictamen técnico](./dictamen-tecnico-v2.88.170-beta-2026-10-28.md) y a esta adenda; su resolución futura **no**
debe confundirse con una certificación de rentabilidad ni de exactitud financiera.
