# RELEVO — Higiene dev CERRADA → Research→Radar

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (Product / Ops).
> **Propósito:** texto de paso para el **NUEVO CHAT** tras higiene dev. **Siguiente = Research→Radar** (secuencia pactada: DS-03 → higiene → Research→Radar → tag beta).
> **AsOf:** 2026-08-24. Ancla `origin/main` = **`5100d23`**. **DS-03** en working tree (sin commit). Higiene dev **CERRADA** (dato local `bolsa_v1` only).
> **Protocolo:** máx. 1 writer + 1 verifier RO. Coordinador re-lee file:line. Pre-commit: batería de la fase + update-last.

---

## 1. Qué quedó hecho (higiene dev)

| Entrega         | Detalle                                                                                                                                                                                                                           |
| --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Script canónico | `scripts/verify/cleanup_dev_test_residues.py` (R-12 A6) — dry-run por defecto, `--apply` borra por `close_account`→`delete_simulated_account`                                                                                     |
| DB objetivo     | Local dev **`bolsa_v1`** (`localhost:5432`) — **nunca prod**                                                                                                                                                                      |
| m7-win / M2     | Re-run dry-run: **0 cuentas + 0 instrumentos** (ya limpio desde R-12 A6 2026-08-21)                                                                                                                                               |
| R8C huérfanas   | 3 cuentas `simulated` con ledger roto eliminadas por path canónico (mismo criterio v1.3.0/`acc_broken`): `acc_broken_c6b1d168ee81` ("R8C broken"), `acc_chain_c050010ead65` ("R8C chain"), `acc_final_8355f4c9f479` ("R8C final") |
| Verify          | `scripts/verify/verify_ledger_balance_chain.py` **EXIT 0** (pre-cleanup: EXIT 1 por las 3 R8C; post-cleanup: OK global A+B)                                                                                                       |
| Código          | **Sin cambios** — solo dato dev + docs                                                                                                                                                                                            |
| Freeze          | Intacto — sin Research→Radar · sin tag beta · sin `contract:gen`                                                                                                                                                                  |

**Conteos:**

| Patrón                           | Pre    | Post       |
| -------------------------------- | ------ | ---------- |
| `m7-win-*` / `M2 *` (script A6)  | 0 / 0  | 0 / 0      |
| R8C `acc_*` simulated huérfanas  | 3      | 0          |
| `verify_ledger_balance_chain.py` | EXIT 1 | **EXIT 0** |

---

## 2. Residuales honestos

| Hueco            | Estado                  | Notas                                                                                                            |
| ---------------- | ----------------------- | ---------------------------------------------------------------------------------------------------------------- |
| R8C re-aparición | Deuda datos             | Si `test_r8c*` corre contra DB compartida sin cleanup → pueden reaparecer; R000 cubre m7/m2, no R8C en script A6 |
| Script A6 scope  | Solo m7-win/M2/CHAOS m7 | R8C requiere mismo path canónico manual o ampliación futura del script (fuera de este slice)                     |
| DS-03 commit     | Pendiente coordinador   | Working tree mandate gate sin commit                                                                             |

---

## 3. Freeze (sigue intacto)

OrderProposal · Journal · Attribution · orquestador · Daily Mission · Track B B1–B12 · Belief · `PAPER_D_EXECUTE` **off** · sin broker live · Lab→spine · `contract:gen` salvo fase pactada · **no bypass human confirm** · **no cambio H3 orphan execute**.

---

## 4. Siguiente · Research→Radar

Secuencia pactada por propietario:

```
DS-03 (working tree)  →  higiene dev (este relevo)  →  Research→Radar  →  tag beta
```

**Abrir chat Research→Radar** con:

```
CONTEXTO: Higiene dev CERRADA (dato local bolsa_v1). DS-03 Mandate de cuenta en working tree (sin commit).
Ancla origin/main = 5100d23. verify_ledger_balance_chain EXIT 0. cleanup_dev_test_residues --list = 0/0.
Freeze intacto. Siguiente fase = Research→Radar (no tag beta todavía).
Relevo: traspaso-relevo-higiene-dev-cierre-apertura-research-radar-2026-08-24.md
```

---

## 5. Commit sugerido (docs-only — coordinador)

```
docs(higiene): cierre dev residue cleanup + relevo Research→Radar

Re-verifica R-12 A6 (0/0 m7-win/M2) y limpia 3 R8C orphans en bolsa_v1 local;
verify_ledger_balance_chain EXIT 0. Siguiente = Research→Radar.
```
