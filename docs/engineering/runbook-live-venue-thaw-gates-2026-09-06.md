# Runbook — Broker LIVE venue thaw gates (diseño; fail-closed)

> **AsOf:** 2026-09-06 · tip `v2.10.1-beta` → `a060af37`.  
> **Padre:** [audit pack LIVE design](./audit-pack-live-venue-thaw-design-2026-09-06.md).  
> **Regla de esta sesión:** **NO ejecutar** el flip a live. Este runbook documenta el orden **futuro** y el abort/restore. Default siempre **paper**.

Freeze: NO LIVE hoy · `PAPER_D_EXECUTE` off · Confirm = firma · Arm ≠ Execute · Ranking ≠ BUY.

---

## 0. Precondiciones (lectura)

```text
node scripts/health-check.mjs
GET /api/risk/kill-switch
  → paperDExecuteEnv=false · brokerVenue=paper · effective=false
node scripts/ops_operativa_self_eval.mjs --account=<id>
  → SEMI measure · operationalReadiness venue paper
```

Si `brokerVenue≠paper` o kill on o execute on → **ABORT** diseño; restaurar paper/kill off/execute off antes de continuar docs.

---

## 1. Checklist ordenada (futuro thaw — no correr ahora)

| Paso | Acción                                    | Pass criteria                                                      | Abort si                             |
| ---- | ----------------------------------------- | ------------------------------------------------------------------ | ------------------------------------ |
| 1    | Owner word explícito «thaw LIVE venue»    | Documentado                                                        | Sin palabra owner                    |
| 2    | L6–L10 scorecard audit pack               | TRUSTED_PROXIES + auth prod + Nivel 4 policy acordados             | OR-06 / auth / chaos sin decisión    |
| 3    | Bridge: URL + mock/real policy            | Fail-closed default documentado; ALLOW/FILL solo opt-in consciente | Encender FILL «por probar» sin stamp |
| 4    | Preflight LR-1 read-only (cash/positions) | `clean` o decision explícita sobre `unavailable`                   | Ignorar `unavailable` en live        |
| 5    | OI-6 portfolio `clean`                    | Sin drift                                                          | Drift sin review                     |
| 6    | Kill off · execute off                    | Ambos false                                                        | Execute on «para live»               |
| 7    | Flip venue (API o mesa)                   | Solo tras 1–6                                                      | Flip antes de scorecard              |
| 8    | OR-6                                      | Esperar `LIVE_EXPERIMENTAL` o documentar `LIVE_BLOCKED` reasons    | Tratar EXPERIMENTAL como Accepted    |
| 9    | Confirm humano                            | CTA «Ejecutar en LIVE» = firma                                     | AUTO execute autónomo                |
| 10   | Post-trade                                | LR-1 + OI-6 · submitted≠fill≠executed                              | Asumir submitted=fill                |

---

## 2. Abort / restore paper (obligatorio conocer)

```text
# Preferido: API global
POST /api/risk/broker-venue  {"venue":"paper"}

# Verificar
GET /api/risk/kill-switch → brokerVenue=paper · paperDExecuteEnv=false · effective=false

# Si se armó kill por pánico
POST /api/risk/kill-switch  {"enabled":false}   # solo tras estabilizar; o dejar ON si incidente abierto
```

Cuenta PA-1: si preferencia cuenta quedó `live`, `PATCH .../broker-venue` → `paper` o unset. Override memory/Redis global gana hasta clear.

Mock flags: **no** dejar `XTB_BRIDGE_ALLOW_ORDERS` / `XTB_BRIDGE_FILL_ORDERS` en default-on en repo.

---

## 3. Escalera de honestidad (recordatorio)

```text
not_wired → rejected → submitted → filled → executed
              ↑ default mock        ↑ no ledger    ↑ solo filled+execute_trade OK
```

Confirm: `rejected`/`not_wired` → skipped · `submitted` → unknown `live_submitted_no_fill` · `executed` → ledger.

---

## 4. Qué este runbook NO autoriza

- Ejecutar pasos 7–9 bajo PRODUCT FREEZE V2.10.1.
- Mezclar thaw `PAPER_D_EXECUTE` / Accept estricto con venue LIVE.
- Commit de IPs `TRUSTED_PROXIES` o secretos.
- Afirmar PASS LIVE por completar solo lectura de este doc.
