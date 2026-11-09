# Verificación de la medición PAPER del `2026-11-09`

**Estado:** plantilla **sin rellenar**. Se completa el `2026-11-10`, en frío, leyendo solo material
durable. Nada de lo que sigue es una medición hasta que tenga fecha, comando y artefacto.

**Objeto medido:** árbol de `v2.88.186-beta` — tag anotado `db919045…` → commit
`a5013f75`; `HEAD:apps` = `d39a04a7f544704d05033dc8ea8772ebb22272d0`, `HEAD:packages` =
`2de53cda49ed847dbd5d4b9572c826c6368ddc52`; `WINDOW_CONFIG` con esa misma pareja.

**Para qué:** la corrida `20261106` cerró con `292/400` ticks, `263` ciegos, cobertura `62→84/181` y
`0/32` ciclos cerrados (`PAPER INCONCLUSIVE`). Este documento fija **de antemano** qué se aceptará
como medición válida del lunes, para no negociar el criterio después de ver el resultado.

---

## 0. El instrumento, verificado antes de la ventana (`2026-11-08`)

El validador se contrastó contra los artefactos durables que ya existen, no contra fixtures:

| Comando | Dictamen | Qué demuestra |
| --- | --- | --- |
| `node scripts\window-measurement-check.mjs --day 20261105 --historical` | `INCONCLUSIVE` | Con un `forward-market` real de 400 ticks y `0` ciclos, el dictamen no es `GREEN`; la cobertura ausente sale `UNKNOWN`, no `0` |
| `node scripts\window-measurement-check.mjs --day 20261106` | `PREMATURE_TERMINATION` | Sin `forward-market-20261106.json` la medición no cuenta; el sábado `2026-11-07` del `dayList` se declara `WARN` |
| `node --test scripts\lib\window-forward.test.mjs scripts\lib\window-measurement-check.test.mjs` | 70 pass / 0 fail | Reglas puras (sello, prematura, 0 ciclos, umbrales, huecos) |

**Hallazgo de artefacto (no de motor):** el `window-runs/20261106/manifest.json` durable es el intento
de las `19:40:53Z` sobre el árbol antiguo (`apps 0c64a560`, copia en `attempt-1940z-oldtree/`), no la
corrida de **292** ticks lanzada a las `22:12:35Z`; esa corrida no dejó manifest ni `forward.json`
propios. Por eso el validador marca `S1.config` como `FAIL` **informativo** (sin `forward` no hay
medición que invalidar) y dictamina `PREMATURE_TERMINATION`. Ninguna cifra del expediente se corrige
aquí: se declara de dónde sale cada artefacto.

## 1. Antes de la ventana (`2026-11-09`, 18:15)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\ops\window-preflight.ps1 -Day 20261109
```

Debe salir **0 FAIL** y el `WARN` de `task.nextrun` debe haber desaparecido (el primer disparo
pendiente ya es el día objetivo). Guardar `preflight.json` junto al resto de artefactos.

Comprobaciones que el preflight ya cubre y que **no** se dan por buenas de memoria: tarea `Ready` y
`NextRunTime` en el día, `freeze OK` en raíz **y** sello, worktree del sello limpio con su `.venv`,
sin `20261109` ni `.run.lock`, suspensión por CA a `0`, `.env` con `BROKER_VENUE=paper` y `0`
variables `LIVE`.

## 2. Durante la ventana

- Disparo de la tarea a las `18:30` desde el **sello**, no desde la raíz.
- Tope previsto: **400 ticks**.
- Si el equipo se suspende o se apaga, la corrida queda **inválida como medición** (la causa se
  declara, no se rellena). Comprobar conexión a corriente.

## 3. Cierre (`2026-11-10`, read-only)

```powershell
# 1) paquete del dia (anadir --declare-termination SOLO si no hubo forward.json)
.venv\Scripts\python.exe scripts\ops\final_package.py --day 20261109 --expected-ticks 400 --json-out <ruta> --md-out <ruta>

# 2) certificacion y export de ciclos
node scripts\window-certify.mjs --out operability_runs\paper-window-certification\cert-20261109.json

.venv\Scripts\python.exe apps\api-python\scripts\paper_cycles_export.py `
  --account-id 1484e253d2d54645945a6b1d7 `
  --strategy-version v283-window-a --strategy-version v283-window-b |
  Out-File -Encoding utf8 operability_runs\paper-cycles-20261109.json

# 3) validador de la medicion (NUEVO)
node scripts\window-measurement-check.mjs --day 20261109 --expected-ticks 400
```

Si hace falta declarar a mano datos que el artefacto no trae (ticks ciegos, cobertura), se pasan como
`--blind-ticks`, `--coverage-start` y `--coverage-midnight` **con su procedencia escrita** en §5. Nunca
se pasan valores inventados ni se usa `--historical`: esa bandera existe para auditar corridas
anteriores al sello y **no** certifica el árbol actual.

## 4. Criterios de aceptación

Se rellenan el `2026-11-10`. Un solo `FAIL` duro invalida la medición; los `WARN` se declaran.

| # | Criterio | Cómo se mide | Resultado |
| --- | --- | --- | --- |
| A1 | Árbol del tag = pin | `node scripts\window-measurement-check.mjs` → `S1.seal` | _pendiente_ |
| A2 | Corrida congelada en `d39a04a7` / `2de53cda` | `manifest.json` → `configMode`, `freeze.ok`, `S1.config` | _pendiente_ |
| A3 | La corrida dejó `forward-market-20261109.json` con `stopReason completed` | `S2.run` | _pendiente_ |
| A4 | Ticks durables = tope declarado (400) | `S3.ticks` | _pendiente_ |
| A5 | Ticks ciegos declarados y turnos evaluables > 0 | `S3.blind` (si el artefacto no lo trae: `--blind-ticks` con procedencia) | _pendiente_ |
| A6 | Cobertura inicial y de medianoche declaradas frente al ESTUDIO (181), separadas de los operables | `S4.universe` | _pendiente_ |
| A7 | Ciclos cerrados > 0 y medibles ≥ 32; episodios ≥ 2 | `S5.cycles`, `certificación` | _pendiente_ |
| A8 | Umbrales sin rebajar (`4/2/32`) | `S6.thresholds` | _pendiente_ |
| A9 | `days` sin días sin sesión | `S6.days` | _pendiente_ |
| A10 | Export de ciclos no vacío (`paper_forward_results`) | `paper_cycles_export.py` | _pendiente_ |

**Dictamen del validador:** _pendiente_ (`GREEN` / `INCONCLUSIVE` / `PREMATURE_TERMINATION` /
`INVALID`).

`GREEN` exige A1-A10. Un `0` de ciclos **nunca** produce `GREEN`; produce `INCONCLUSIVE`, que es un
resultado legítimo y **no** un fallo de CI.

## 5. Procedencia de los datos declarados a mano

| Dato | Valor | De dónde sale | Quién lo midió |
| --- | --- | --- | --- |
| Ticks ciegos | _pendiente_ | | |
| Cobertura al arrancar | _pendiente_ | | |
| Cobertura en medianoche | _pendiente_ | | |

Sin esta tabla, un `--blind-ticks` o un `--coverage-*` es una afirmación sin fuente y no se acepta.

## 6. Qué invalida la medición

- Ejecutar sobre un árbol distinto de `a5013f75` / `d39a04a7` / `2de53cda`.
- `configMode` distinto de `FROZEN`, `freeze.ok = false` o pin sin commitear.
- Terminar sin `forward.json` (→ `PREMATURE_TERMINATION`; la corrida **no cuenta**).
- Presentar ticks ciegos (`idle`) como turnos evaluables.
- Presentar la cobertura del ESTUDIO como universo operable.
- Contar un día sin sesión como día de ventana (deuda abierta: `2026-11-07`).
- Declarar `GREEN` con `0` ciclos cerrados o con umbrales rebajados.

## 7. Registro del cierre

- Run / artefactos: _pendiente_
- `manifest.json`: _pendiente_
- `forward-market-20261109.json`: _pendiente_
- Certificación (`window-certify`): _pendiente_
- Export de ciclos: _pendiente_
- Validación (`window-measurement-check`, salida completa): _pendiente_
- Comentario sobre la deuda `days`: _pendiente_

## 8. Límites

- AUTO **OFF**; operativa **100 % SIM**; sin autorización para dinero real.
- La ventana real es **OPERACIÓN**, no CI: este documento no la sustituye, solo la audita.
- Un hueco se declara: ausencias en `null`/`UNKNOWN`, nunca en `0`.
