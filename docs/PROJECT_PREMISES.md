# Premisas de proyecto — Bolsa V1

> **AsOf:** 2026-08-03  
> **Qué es:** reglas de producto y de ingeniería que aplican a **todo** el monorepo.  
> **Para quién:** equipo, auditores externos, quien retome el código.  
> No sustituye ADRs: las ADRs deciden arquitectura; estas premisas fijan *cómo se trabaja y se documenta*.

---

## 0. Índice de premisas

| Premisa | Documento |
|---------|-----------|
| **Documentar todo** (docs + código) | §1 de este archivo · [code-documentation-standard](./engineering/code-documentation-standard-2026-08-03.md) |
| UI configurable → `localStorage` | [UI_PREFS_LOCALSTORAGE.md](./UI_PREFS_LOCALSTORAGE.md) |
| Responsive (chart / trading) | [RESPONSIVE_PREMISES.md](./RESPONSIVE_PREMISES.md) |
| Cuentas DEMO vs Paper | [account-premises-demo-vs-paper-2026-07-31.md](./engineering/account-premises-demo-vs-paper-2026-07-31.md) |
| Backtesting DÍA D | [backtesting-dia-d-premises-2026-07-31.md](./engineering/backtesting-dia-d-premises-2026-07-31.md) |
| LAB ≠ TRADING | [ADR-019](./adr/019-dual-universes-lab-vs-trading.md) · [diseño](./engineering/dual-universes-lab-trading-design-2026-08-02.md) |
| Freeze post-auditorías | [post-audit-decision-freeze-2026-08-03.md](./engineering/post-audit-decision-freeze-2026-08-03.md) |

Entrada auditoría: [audit-pack-post-audits-2026-08-03.md](./engineering/audit-pack-post-audits-2026-08-03.md).  
Índice ingeniería (docs): [engineering-index-2026-08-03.md](./engineering/engineering-index-2026-08-03.md).  
Round 2 externas: [audit-ext-round2-triage-2026-08-03.md](./engineering/audit-ext-round2-triage-2026-08-03.md).
Respuesta auditoría 1 (gaps A/B): [audit1-response-ingest-fie-2026-08-03.md](./engineering/audit1-response-ingest-fie-2026-08-03.md).

---

## 1. Premisa — Documentar todo (producto **y** código)

### Regla

**Todo cambio relevante se documenta en la capa que corresponde.** No se considera “hecho” un feature o fix de dominio si solo existe el código.

| Capa | Obligatorio | Dónde |
|------|-------------|-------|
| Producto / decisión / auditoría | Sí, si cambia comportamiento visible, contratos o política | `docs/` · HELP · trackers · ADR si aplica |
| Contrato HTTP | Sí (schemas + OpenAPI) | `bolsa_api/schemas/*` · [API_REFERENCE.md](./API_REFERENCE.md) si el endpoint es público |
| Comportamiento interno | Sí (forward-only) | **Docstrings** de módulo y símbolos públicos · JSDoc en exports de `@bolsa/shared` / helpers de dominio |
| Ops / flags | Sí | [github-credentials-and-ops.md](./engineering/github-credentials-and-ops.md) §9 · freeze si cambia política |

### Docstrings / JSDoc

Detalle normativo: [code-documentation-standard-2026-08-03.md](./engineering/code-documentation-standard-2026-08-03.md).

Resumen:

1. Al **crear o tocar** código público: docstring de módulo + de clase/función pública (Python); JSDoc breve en exports de dominio (TS).  
2. **Forward-only:** no reescribir histórico solo por docs (misma filosofía que no reescribir \(K\)).  
3. Lotes 1–4 de cobertura Lab/API/application **cerrados** (2026-08-03); lo nuevo sigue la regla al tocarse.  
4. Medición: `python scripts/research/docstring_coverage_report.py`.

### Qué no exige esta premisa

- Docstring en cada getter trivial, test o componente UI puramente presentacional.  
- Duplicar un ADR dentro del código (el docstring dice *qué hace*; el ADR *por qué del sistema*).  
- Documentar secretos, tokens o `.env` reales en el repo.

### Consecuencia para PRs

Un PR que introduce API, use-case, indicador o ruta nueva **incluye** docs de producto/HELP si cambia la experiencia, **y** docstrings/JSDoc en los símbolos públicos tocados.

---

## 2. Otras reglas globales (recordatorio)

- Identificadores de código/commits en **inglés**; UI y docs de producto en **español**.  
- Decisiones de arquitectura → ADR en `docs/adr/`.  
- BD = fuente de verdad de mercado/ledger; Yahoo/XTB solo actualizan.  
- API por defecto: Python `:8000`.  
- Preferencias UI → `localStorage` ([premisa](./UI_PREFS_LOCALSTORAGE.md)).

---

## 3. Visibilidad del repositorio

Repo GitHub: `https://github.com/jvelasca/Bolsa_V1` — **público** (2026-08-03) para que auditorías externas lean código + `docs/` sin invitación.

Secretos (`.env`, tokens, `.secrets/`) **nunca** van al remoto. Ver [github-credentials-and-ops.md](./engineering/github-credentials-and-ops.md).

---

*Premisas vivas: al añadir una regla transversal, enlázala en §0 y anúnciala en [HELP.md](./HELP.md) / [README.md](./README.md).*
