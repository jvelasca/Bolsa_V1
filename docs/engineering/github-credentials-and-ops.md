# GitHub — credenciales y gestión (Bolsa V1)

> **Propósito:** una sola ficha para (1) tus credenciales de GitHub, (2) cómo se usan, (3) el flujo de repo/release V1.  
> **Regla de oro:** este doc puede ir al repo; **los valores reales no**. Copia la plantilla a un fichero local ignorado.

| | |
|--|--|
| Cuenta GitHub | `jvelasca` (CLI `gh` ya autenticada en este PC) |
| Repo propuesto | `https://github.com/jvelasca/Bolsa_V1` (**privado**) |
| Tag release | `v1.0.0` |
| Checklist push | [`github-v1-release.md`](./github-v1-release.md) |
| Changelog | [`../../CHANGELOG.md`](../../CHANGELOG.md) |

---

## 1. Qué va dónde (no mezclar)

| Tipo | Dónde vive | ¿Git? |
|------|------------|-------|
| Token / password GitHub | Windows Credential Manager · o `gh auth` · o `.secrets/github.env` | **Nunca** |
| SSH key privada | `~/.ssh/id_ed25519` (o la que uses) | **Nunca** |
| `.env` de la app (DB, `APP_PASSWORD`, APIs) | raíz del proyecto `.env` | **Nunca** (ya en `.gitignore`) |
| Plantillas `.env.example` | repo | Sí |
| Este documento + checklist release | `docs/engineering/` | Sí |

Si un valor secreto aparece en un commit, **rota el token** en GitHub → Settings → Developer settings → Personal access tokens.

---

## 2. Plantilla local (rellena tú)

1. Crea la carpeta (ya ignorada por `.gitignore` → `.secrets/`):

```powershell
New-Item -ItemType Directory -Force -Path .secrets | Out-Null
Copy-Item docs/engineering/templates/github-credentials.local.example .secrets/github.env
notepad .secrets/github.env
```

2. Rellena solo en `.secrets/github.env` (ese fichero **no** se sube).

Contenido de la plantilla (referencia):

```env
# === Bolsa V1 · GitHub (LOCAL ONLY — no commit) ===

# Cuenta
GITHUB_USER=jvelasca
GITHUB_REPO=Bolsa_V1
GITHUB_VISIBILITY=private

# Auth: usa UNA de estas vías (preferida = gh CLI, sin pegar token aquí)
# A) Ya hecho en este PC:  gh auth login
# B) Token fine-grained / classic (solo si no usas gh):
# GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Remoto tras crear el repo
GITHUB_REMOTE=https://github.com/jvelasca/Bolsa_V1.git

# Release
GITHUB_DEFAULT_BRANCH=main
GITHUB_RELEASE_TAG=v1.0.0
```

---

## 3. Autenticación en este PC (gestión diaria)

### Opción recomendada — GitHub CLI

```powershell
gh auth status
# Si caduca o cambias de cuenta:
gh auth login
# Host: GitHub.com · HTTPS · Login with browser · scopes: repo, workflow
```

Comprueba:

```powershell
gh api user --jq .login
# esperado: jvelasca
```

### Opción alternativa — HTTPS + Credential Manager

Al primer `git push`, Windows pedirá login; el token queda en **Administrador de credenciales de Windows** (no en el repo).

### Opción SSH

```powershell
# Si ya tienes clave:
Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub
# Añadir en GitHub → Settings → SSH and GPG keys
git remote set-url origin git@github.com:jvelasca/Bolsa_V1.git
```

---

## 4. Gestión del repo V1 (orden operativo)

Estado actual del árbol local:

| Paso | Estado |
|------|--------|
| Empaquetado (`CHANGELOG`, checklist, versión 1.0.0) | Hecho |
| `git init -b main` | Hecho |
| Primer commit | Pendiente (tu OK) |
| `gh repo create` + push | Pendiente (tu OK) |
| Tag `v1.0.0` + GitHub Release | Pendiente (tu OK) |

Cuando digas **sí**, el agente ejecutará (o tú a mano):

```powershell
# Desde la raíz Bolsa_V1
git add -A
git status   # verificar: NO aparece .env ni .secrets/

git commit -m "release: Bolsa V1.0.0 — embudo, DÍA D, CORE-P/R, FA"

gh repo create Bolsa_V1 --private --source=. --remote=origin --push

git tag -a v1.0.0 -m "Bolsa V1.0.0"
git push origin v1.0.0
gh release create v1.0.0 --title "Bolsa V1.0.0" --notes-file CHANGELOG.md
```

Día a día después:

```powershell
git pull
git checkout -b feat/mi-cambio
# ... trabajo ...
git push -u origin HEAD
gh pr create
```

---

## 5. Tokens: scopes mínimos

| Uso | Scopes |
|-----|--------|
| Push repo privado + releases | `repo` |
| GitHub Actions (si tocas workflows) | `workflow` |
| Solo lectura | `repo` read o fine-grained Contents: Read |

**No** uses el token de GitHub como `APP_PASSWORD` de la app ni lo pongas en `.env` de la API.

---

## 6. Credenciales de la *app* (distintas de GitHub)

Van en `.env` (raíz), nunca en GitHub:

| Variable | Rol |
|----------|-----|
| `DATABASE_URL` | PostgreSQL local |
| `APP_PASSWORD` | Login opcional de la plataforma |
| `APP_AUTH_SECRET` | Firma de sesión |
| Keys de brokers / Yahoo / LLM | Solo si las activas; siempre local |

Plantilla pública: [`.env.example`](../../.env.example).

---

## 7. Checklist anti-fuga (antes de cada push)

- [ ] `git status` no lista `.env` ni `.secrets/`
- [ ] No hay `ghp_` / `gho_` / `github_pat_` en diffs
- [ ] `gh auth status` OK si vas a `gh repo create` / `gh release`
- [ ] Repo **private** salvo que decidas lo contrario

---

## 8. Si algo falla

| Síntoma | Qué hacer |
|---------|-----------|
| `git push` 403 / auth | `gh auth login` o renovar token |
| `gh` apunta a otra cuenta | `gh auth switch` / `gh auth logout` + login |
| Subiste un secreto por error | Rotar token en GitHub; opcionalmente `git filter-repo` (pedir ayuda) |
| Repo ya existe | `gh repo view jvelasca/Bolsa_V1` y solo `git remote add origin …` + push |

---

*Última actualización: 2026-08-01 · Empaquetado V1 local; push pendiente de confirmación.*
