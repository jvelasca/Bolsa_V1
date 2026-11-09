# Evidencia — control de entradas aleatorias frente a AUTO (`2026-11-09`)

## 1. Qué publica

El resultado del experimento nulo que decide **señal o geometría**: se comparan las entradas reales de
AUTO (`CSV`) contra 100 conjuntos de entradas aleatorias (`RANDOM`) y contra un cruce de momentum
(`MOMENTUM`), con **idéntica** geometría de salida, dimensionado, veto por hueco y coste.

- **Implementación:** [`scripts/random_entry_control.py`](../../../../scripts/random_entry_control.py).
- **Ventana:** `2022-01-27` → `2026-10-26`.
- **Coste:** `12,7 bps` por lado (cifra de calibración).
- **Semillas:** `100` (`--seed-base 20260101`), reparto uniforme.
- **Universo:** los 10 símbolos con entrada real (`--universe csv`).
- **Entradas reales:** `entradas_auto.csv` (`date,yahoo_symbol`), 183 entradas en ventana.
- **Ledger de referencia:** `operability_runs/dia-d-auto/v2_93_2026-11-09.cycles.json` (192 ciclos).

## 2. Artefactos y por qué no viajan en el ZIP

Los tres JSON viven en `operability_runs/dia-d-auto/`, que está **ignorado** por `.gitignore` (línea 102:
`/operability_runs/`). No entran en el ZIP del tag. Por eso las cifras quedan **fijadas en este
documento** y la reproducción es un comando (§4), no un fichero adjunto.

| Artefacto | Ruta de origen | Geometría |
| --- | --- | --- |
| `control_entradas_aleatorias.json` | `operability_runs/dia-d-auto/` | `policy` (motor actual) |
| `control_entradas_aleatorias_structural.json` | idem | `structural` |
| `control_entradas_aleatorias_timeonly.json` | idem | `time-only` |
| `entradas_auto.csv` | raíz del repo | lista de entradas reales |

## 3. Cifras congeladas

### 3.1 `policy` — geometría del motor

| Métrica | p5 | p25 | Mediana | p75 | p95 | CSV (AUTO) | Percentil CSV |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Neto % | -26,651 | -12,872 | -3,943 | 6,754 | 17,711 | **-18,644** | **12 %** |
| Expectancy R | -0,166 | -0,049 | 0,015 | 0,083 | 0,174 | **-0,056** | **23 %** |
| Net expectancy R | -0,244 | -0,126 | -0,062 | 0,006 | 0,097 | **-0,131** | **23 %** |
| Max drawdown % | 10,331 | 14,029 | 17,999 | 23,373 | 31,126 | **24,273** | **77 %** |
| Sharpe | -0,722 | -0,296 | -0,059 | 0,202 | 0,437 | **-0,492** | **9 %** |
| Tasa de acierto % | 43,839 | 47,296 | 49,081 | 51,339 | 54,149 | **46,154** | **20 %** |
| Payoff | 0,899 | 1,001 | 1,051 | 1,106 | 1,182 | **1,069** | **58 %** |

`MOMENTUM`: neto **+43,307 %**, expectancy **+0,102 R**, net expectancy **+0,024 R**, 659 ciclos,
668 entradas, drawdown 23,389 %, exposición media **119,7 %**.

**Verificación (2026-11-09 11:30):** las cifras se recalcularon desde
`operability_runs/dia-d-auto/control_entradas_aleatorias.json` (100 ramas `random#0`…`random#99`,
`mode = csv`/`momentum` aparte) y coinciden en las siete métricas. Dos hechos nuevos quedan fijados:
CSV tiene **exposición media 32,2 %** (percentil **1**) frente a 39,8 % de mediana aleatoria, y
**182 ciclos** (percentil **7**) frente a 204. Detalle en
[§1.1](../../control-entradas-aleatorias-2026-11-09.md).

### 3.2 El mismo CSV con tres salidas

| Modelo | Neto CSV | Pct. neto | Expectancy CSV | Pct. exp. | Net exp. CSV | Pct. net-exp | Momentum (exp.) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `policy` | -18,644 % | 12 % | -0,056 R | 23 % | -0,131 R | 23 % | +0,102 R |
| `structural` | -15,457 % | 12 % | -0,019 R | 26 % | -0,093 R | 27 % | +0,090 R |
| `time-only` | **+12,018 %** | 34 % | **+0,335 R** | **85 %** | **+0,256 R** | **85 %** | +0,408 R |

### 3.3 Fidelidad simulador/ledger (`policy`, variante ganadora)

`pairs 182` · `bias +0,1314 R` · `rmse 0,748` · `corr 0,888` · `signAgreement 0,929` ·
`simExpectancy -0,0558 R` · `realExpectancy -0,1872 R` · `unmatchedSim 0` · `unmatchedReal 10`.

| Grupo | n | Media real | Media sim | Sesgo |
| --- | ---: | ---: | ---: | ---: |
| Todos | 182 | -0,1872 R | -0,0558 R | +0,1314 R |
| Ganadores reales | 77 | +1,3450 R | +1,2851 R | -0,0599 R |
| Perdedores reales | 105 | -1,3109 R | -1,0392 R | +0,2717 R |
| Stop disparado sin fill | 26 | -0,4529 R | -0,1082 R | **+0,3447 R** |
| Resto | 156 | -0,1430 R | -0,0471 R | +0,0959 R |

## 4. Reproducción

```powershell
.venv\Scripts\python.exe scripts\random_entry_control.py `
  --start 2022-01-27 --end 2026-10-26 --seeds 100 `
  --entries-csv entradas_auto.csv --mode csv --calibrate `
  --json-out operability_runs\dia-d-auto\control_entradas_aleatorias.json

.venv\Scripts\python.exe scripts\random_entry_control.py `
  --start 2022-01-27 --end 2026-10-26 --seeds 100 `
  --entries-csv entradas_auto.csv --exit-mode structural `
  --json-out operability_runs\dia-d-auto\control_entradas_aleatorias_structural.json

.venv\Scripts\python.exe scripts\random_entry_control.py `
  --start 2022-01-27 --end 2026-10-26 --seeds 100 `
  --entries-csv entradas_auto.csv --exit-mode time-only `
  --json-out operability_runs\dia-d-auto\control_entradas_aleatorias_timeonly.json
```

Autoprueba hermética (sin BD): `python scripts\random_entry_control.py --selftest`.

## 5. Qué NO certifica

| No certifica | Por qué |
| --- | --- |
| **El nivel absoluto de RANDOM** | La geometría se calibró **in-sample** contra los mismos 182 ciclos que después se comparan (`selection: rmse`). Reproduce el nivel, no lo predice. |
| **Que momentum sea desplegable** | Su exposición media es 119,7 %: no es una rama comparable en neto ni operativamente viable tal cual. |
| **Rentabilidad de AUTO** | Con la geometría actual el CSV está en el percentil 12 de neto y 23 de expectancy. El documento describe por qué, no la arregla. |
| **Que el experimento cubra el universo forward** | El universo del control son 10 símbolos; `AI.PA`, `NOKIA.HE` y `OR.PA` no están en la BD y el forward usa otro conjunto. Ver §5 de [respuesta-auditoria-externa-2026-11-09.md](../../respuesta-auditoria-externa-2026-11-09.md). |

## 6. Reparos conocidos del artefacto

- **`mark = 0.0` como barra ausente** en el ledger real: 93 filas en 66 de 192 ciclos. Infla
  `stopTouchDays` y `firstTouchDay`. No afecta a la comparación RANDOM/CSV (el simulador no lee el
  timeline real), pero sí a la fidelidad ciclo a ciclo.
- **10 ciclos reales sin pareja** en el cruce (`unmatchedReal = 10`).
- **Coste 12,7 bps** es calibración, no el modelo del motor (10/2/5 bps).

Lectura completa: [control-entradas-aleatorias-2026-11-09.md](../../control-entradas-aleatorias-2026-11-09.md).
