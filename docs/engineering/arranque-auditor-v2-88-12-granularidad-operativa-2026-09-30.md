# Arranque del auditor — `v2.88.12-beta` / `GRANULARIDAD-OPERATIVA`: rethink `config-driven` de la cadencia del motor AUTO

> **Objeto auditado:** tag anotado **`v2.88.12-beta`** · **Versión:** `2.11.12-beta` (**bump**
> `2.11.11-beta → 2.11.12-beta`) · **Base (diff):** `v2.88.11-beta` · **AsOf:** 2026-09-30 ·
> **Alembic head:** `046_fill_reference_mid` (**SIN migración**).
> **Remote:** `github.com/jvelasca/Bolsa_V1.git` (**PÚBLICO**).
> **Naturaleza:** **`docs`-only** — el **motor NO cambia** (diff de `packages/`/`apps/*/src` **vacío**).
> **Documento a auditar:** [`rethink-granularidad-operativa-auto-2026-09-30.md`](./rethink-granularidad-operativa-auto-2026-09-30.md).
> **Entrega (preguntas concretas + prompt):** [`entrega-auditoria-externa-mia-v2.88.12-2026-09-30.md`](./entrega-auditoria-externa-mia-v2.88.12-2026-09-30.md).

---

## 0. Qué se audita (y qué no)

Se audita **una propuesta de arquitectura**, no un cambio de código. El objetivo es que el auditor externo
dé su **opinión técnica** y ayude a **consensuar el siguiente trabajo**. **No** hay bug que buscar en `src`:
un `git diff` vacío del motor **es el objeto**, no un fallo.

Diseño en una frase: la **granularidad del dato** (barras `1d`) y la **cadencia del bucle** (60 s) están
desacopladas ⇒ ~**1.440 ticks/día** para **~1 decisión real**; se propone **una única fuente de verdad**
(`OperativeGranularity`) que derive toda la cadena, y un **planificador por barra cerrada**.

---

## 1. Cita del CI (lo primero que hay que comprobar)

### 1.1 CI del tag `v2.88.12-beta` — **POST-TAG**

Límite estructural (`OBS-3`/`OBS-4`): `Release tag CI` **sólo corre al empujar** el tag ⇒ su resultado no
puede preexistir dentro del propio tag. La cita del run **verde** viaja en `main` (commit **POST-TAG**).
Comprobación:

```
git log --format=%h:%s -1 --grep "cita POST-TAG del CI del tag v2.88.12-beta"
gh run list --workflow "Release tag CI" --limit 5     # buscar el run de v2.88.12-beta
```

El workflow certifica **también** sellos `docs-only` (no lleva path-filter: «docs-only stamp también
certifica», cabecera de `.github/workflows/release-tag-ci.yml`). Jobs agregados por `certify`: `security`,
`shared`, `spine`, `frontend`, `python`, `playwright-mock`, `lifecycle-pg`, `replay-repro`, `dr-verify`,
`a7-gate`.

### 1.2 Qué cubre el CI en este sello (motor intacto)

Aunque no haya cambio de motor, el tag **revalida** el objeto sellado: `python` (ruff/import-linter/mypy/
pytest offline), `lifecycle-pg` (Alembic + golden restart + suites PG con *fail-if-skipped*), `replay-repro`
(regenera y asserta el artefacto del replay) y `dr-verify` (batería DR por TCP). Ver §2.

---

## 2. Firma de estado verificada **antes** de auditar

| # | Comprobación | Comando | Resultado esperado |
| --- | --- | --- | --- |
| 1 | Clon anónimo (repo público) | `git clone https://github.com/jvelasca/Bolsa_V1` | OK |
| 2 | Tag **anotado** | `git cat-file -t v2.88.12-beta` | `tag` |
| 3 | Versión | `git show v2.88.12-beta:package.json` | `2.11.12-beta` |
| 4 | Árbol limpio | `git status --porcelain` | vacío |
| 5 | **Motor INTACTO** | `git diff --name-only v2.88.11-beta v2.88.12-beta -- packages/py apps/api-python/src` | **vacío** |
| 6 | Contenido = docs + bump | `git diff --name-status v2.88.11-beta v2.88.12-beta` | docs + `CHANGELOG.md` + `package.json` |
| 7 | **No** se toca CI/config | `git diff --name-only v2.88.11-beta v2.88.12-beta -- .github pyproject.toml` | ninguno |
| 8 | **No** se borran tests | `git diff --diff-filter=DR --name-status v2.88.11-beta v2.88.12-beta` | **0** |
| 9 | CI del tag | `Release tag CI` (cita **POST-TAG** en `main`) | **SUCCESS** |

**Hueco declarado:** al ser `docs`-only, **no** hay matriz de mutaciones nueva ni test nuevo (no procede).
La verificación local del autor coincide con el CI porque no hay `src` que pueda derivar.

---

## 3. Alcance sugerido de la auditoría

1. **El diagnóstico (§2 del diseño)**, con sus citas a fichero/línea: ¿es correcto y completo?
2. **El modelo `OperativeGranularity` (§3)**: ¿seam correcto? ¿`platform_kernel` sería mejor hogar?
3. **Las 3 opciones de cadencia (§4)**: ¿el ranking A/B/C y «F1 primero» son sensatos?
4. **Coherencia con `P3-2`/`P3-3` (§6)**: cubos de evidencia vs granularidad.
5. **Riesgos**: grace window de reservas y settlement ante la nueva cadencia.
6. **ADR 010**: alcance de la enmienda (intradía) y si `1wk` está ya cubierto.

Las **7 preguntas concretas** y el **prompt listo para pegar** están en
[`entrega-auditoria-externa-mia-v2.88.12-2026-09-30.md`](./entrega-auditoria-externa-mia-v2.88.12-2026-09-30.md) §4 y §7.

---

## 4. Reproducción (PowerShell / bash)

```
git clone https://github.com/jvelasca/Bolsa_V1.git && cd Bolsa_V1
git checkout v2.88.12-beta

# El motor NO cambió (debe salir vacío)
git diff --name-only v2.88.11-beta v2.88.12-beta -- packages/py apps/api-python/src

# Es docs-only + bump
git diff --name-status v2.88.11-beta v2.88.12-beta

# Leer el objeto
cat docs/engineering/rethink-granularidad-operativa-auto-2026-09-30.md
```

---

## 5. Deuda viva que debe encontrarse declarada (no oculta)

`P3-2`/`P3-3` (ventana PAPER real ≥4 días con material), `OBS-14.b`, `OBS-15`, `OBS-16`, `OBS-22`,
`OBS-19`, `OBS-13`, `OBS-11`, `H-4`, `OBS-9`, `P3-5`, `OBS-5`. **Este sello no cierra ninguna.**
`OBS-21` quedó **cerrada** en `v2.88.11-beta` (no reabrir).

---

## 6. Entregable esperado

Un informe `docs/engineering/auditoria-v2-88-12-granularidad-operativa-2026-XX-XX.md` con veredicto de
**viabilidad del diseño** (`VIABLE` / `VIABLE CON CAMBIOS` / `NO VIABLE`), respuestas a las 7 preguntas,
riesgos y vacíos (separando hallazgo nuevo de deuda declarada), lo que **no** se pudo medir, y la
**recomendación de siguiente trabajo** (candidato propuesto: **F1**).
