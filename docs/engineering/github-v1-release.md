# GitHub V1 — checklist de release

> Empaquetar el árbol actual como **v1.0.0** en GitHub.  
> Cuenta gh: `jvelasca` · propuesta de repo: **`Bolsa_V1`** (privado, alineado con `Bolsa_V2_2`).  
> Credenciales y gestión diaria: [`github-credentials-and-ops.md`](./github-credentials-and-ops.md).

## Preflight (local)

```bash
pnpm db:ensure
pnpm test:coach
pnpm test:operativa
pnpm test:fa
# Con API arriba:
# CORE_P_API_REQUIRED=1 pnpm test:coach:smoke
# OPERATIVA_API_REQUIRED=1 pnpm test:operativa:smoke
```

- [x] `.env` en `.gitignore` (no subir secretos)
- [x] `CHANGELOG.md` · versión producto 1.0.0
- [x] `git init -b main`
- [ ] Primer commit
- [ ] `gh repo create` + push `main`
- [ ] Tag `v1.0.0` + release notes (desde CHANGELOG)

## Comandos (cuando el usuario confirme)

```bash
git init -b main
git add -A
git status   # revisar: sin .env, sin logs, sin node_modules
git commit -m "release: Bolsa V1.0.0 — embudo, DÍA D, CORE-P/R, FA"

gh repo create Bolsa_V1 --private --source=. --remote=origin --push

git tag -a v1.0.0 -m "Bolsa V1.0.0"
git push origin v1.0.0
gh release create v1.0.0 --title "Bolsa V1.0.0" --notes-file CHANGELOG.md
```

## Fuera de V1 (congelado)

Ver `AI_PRODUCT_FROZEN` en Ayuda → Plataforma IA.

## Post-release

- BETA1: simulaciones; issues cortas en `research/observations/ISSUES.md`
- No reabrir tracks congelados sin decisión explícita
