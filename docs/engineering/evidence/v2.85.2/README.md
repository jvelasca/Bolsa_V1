# Evidencia cruda — ventana PAPER D1 (2026-09-28) · objeto `v2.85.2-beta`

> **AsOf:** 2026-09-28 · **Qué es:** copia **verbatim** de la evidencia del día **D1** de la ventana
> PAPER, capturada el 2026-09-28 y **incluida dentro del tag `v2.85.2-beta`** para que un auditor pueda
> **recomputar** el funnel sin depender del árbol local.
> **Por qué una copia:** `operability_runs/` y `logs/` están **gitignoreados** (`.gitignore:102` y
> `.gitignore:12`) ⇒ la evidencia original **no** viajaba a GitHub. Estos ficheros son la copia
> versionada de esa evidencia; los originales **no** se han alterado ni borrado.

## Ficheros y huella (SHA-256)

| Fichero | Qué es | SHA-256 (bytes **del tag**, LF) |
|---|---|---|
| `forward-market-20260928.json` | el `--out` del forward `v2_76` (400 ticks, `stopReason=completed`) | `6831DE3E42ABA0C651B27E646FEC60DDEB820E5407C2115250D4CD4972AE6264` |
| `forward-20260928.out.log` | cronología de los 40 informes de progreso (`ticks`/`prices`/`cycles`/`verdict`) | `7ECEA1FF11106088B6527B6176DCBBDF3566184286D35C1D2501044E1AA1EE44` |
| `forward-20260928.err.log` | `stderr` del forward (solo los `INFO` de Alembic) | `AFB79333AC305F770BB49F4F440720B235998E925942700A682159C02ED009CF` |
| `journal-d1-row-20260928.jsonl` | la fila del `v2_77` para el día `2026-09-28` (serie diaria de operabilidad) | `05D3A9D3443231BF1F6A7ED1F9D77D9BF4DB77CDC4F6C146D28A235B78189413` |

Copia realizada el 2026-09-28 tras terminar el pipeline (forward `16:16:19Z`, cierre `16:16:55Z`).

**Nota de fidelidad (declarada, no oculta).** Estos SHA-256 son de los **bytes tal y como quedan en el tag**
(normalizados a **LF** por `.gitattributes: * text=auto eol=lf`), **no** de la copia de trabajo en Windows
(que usa CRLF) ⇒ un `Get-FileHash` sobre un clon fresco coincide; sobre un árbol de trabajo Windows sin
normalizar, no. También se declara que los dos `.log` entran con `git add -f`, porque `.gitignore:7` (`*.log`)
los ignoraría: es **evidencia deliberada**, no un descuido. Además, `docs/engineering/evidence/` está
**excluida del formateo** en `.prettierignore` (si prettier reformatease el JSON, la huella publicada
dejaría de cuadrar). El contenido **semántico** (el JSON que `v2_77`
consume) es idéntico en ambos casos.

## Cómo recomputar (sin PostgreSQL)

```powershell
# El funnel y la serie diaria son funciones puras sobre esta evidencia:
uv run --no-sync python apps/api-python/scripts/v2_77_market_operability.py `
    --forward docs/engineering/evidence/v2.85.2/forward-market-20260928.json --render
```

`v2_80_market_window.py` y `v2_83_window_audit.py` **no** se pueden recomputar con esta evidencia: exigen
una **ventana** construida desde el journal **durable** de PostgreSQL (`fills ∪ cycles ∪ journal`), que
para la cuenta `1484e253d2d54645945a6b1d7` es **0** en las tres tablas. Por eso el veredicto de la ventana
es **`NO MEDIDO`** y no se fabrica una serie con estas fixtures.

## Límite declarado

Esto es **evidencia de UN día (D1)**, no una ventana ≥4 días. **No** cierra `P3-2`/`P3-3` ni se usa como
precedente: la ventana real exige material durable real. Ver
[cierre de la ventana](../ventana-paper-d1-cierre-no-medido-v2.85.2-2026-09-28.md).
