# Genera/regenera TODA la evidencia de gates de Cuentas / Perfil inversor en UTF-8.
#
# AUD-07: los .txt anteriores se escribieron con el Out-File por defecto de PowerShell 5.1
# (UTF-16LE) y contract-check.txt quedó corrupto (UTF-16 volcado como UTF-8). Este script
# es la vía reproducible: escribe siempre UTF-8 SIN BOM y guarda el código de salida.
#
# Once gates: los diez del lote original + ``pytest-integridad-061.txt`` (ciclo de vida de
# la migración 061 sobre BD scratch y carrera real asignación/borrado).
#
#   powershell -ExecutionPolicy Bypass -File ...\regen-evidence.ps1
#   pwsh -File ...\regen-evidence.ps1
#
# Sale con código 1 si algún gate falla. No hace commit, push, PR, tag ni Release.

param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..\..")).Path,
    [switch]$SkipSecondWebRun
)

$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$env:PYTHONIOENCODING = "utf-8"
$env:NO_COLOR = "1"

$OutDir = $PSScriptRoot
$results = New-Object System.Collections.Generic.List[object]

function Write-Utf8NoBom {
    param([string]$Path, [string]$Text)
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Text, $encoding)
}

function Invoke-Gate {
    param(
        [string]$File,
        [string]$WorkDir,
        [string[]]$Argv
    )
    Write-Host "==> $File"
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    Push-Location $WorkDir
    try {
        # `cmd /c` une stderr con stdout en el propio proceso: PowerShell solo ve texto,
        # así que no aparecen ErrorRecords de NativeCommandError en la evidencia, y el
        # código real queda en $LASTEXITCODE.
        $line = "chcp 65001>nul & " + ($Argv -join " ") + " 2>&1"
        $output = & cmd.exe /d /c $line | Out-String
        $code = $LASTEXITCODE
        if ($null -eq $code) { $code = 0 }
    }
    finally {
        Pop-Location
        $sw.Stop()
    }
    $seconds = [int]$sw.Elapsed.TotalSeconds
    $text = $output.TrimEnd() + "`r`n`r`n[exit $code · $seconds s]`r`n"
    Write-Utf8NoBom (Join-Path $OutDir $File) $text
    $results.Add([pscustomobject]@{ File = $File; Exit = $code; Seconds = $seconds })
    if ($code -ne 0) { Write-Host "    FALLO (exit $code)" -ForegroundColor Red }
}

$web = Join-Path $RepoRoot "apps\web"
$evidence = "docs/engineering/evidence/cuentas-perfil-2026-10-30"

$pytestArea = @(
    "uv", "run", "pytest",
    "packages/py/application/tests/test_investor_profiles.py",
    "packages/py/infrastructure/tests/test_investor_profile_delete_guard.py",
    "packages/py/infrastructure/tests/test_schema_contract.py",
    "packages/py/infrastructure/tests/test_061_profile_delete_restrict.py",
    "apps/api-python/tests/test_investor_profiles_assign.py",
    "-v"
)
# Integración de la 061 (base nueva / base heredada con datos / downgrade) y carrera
# real asignación-borrado. Las variables convierten un skip silencioso en fallo duro.
$env:PROFILE_DELETE_MIGRATION_PG_REQUIRED = "1"
$env:PROFILE_DELETE_RACE_PG_REQUIRED = "1"
$pytestIntegrity061 = @(
    "uv", "run", "pytest",
    "packages/py/infrastructure/tests/test_061_profile_delete_restrict_pg.py",
    "packages/py/infrastructure/tests/test_investor_profile_delete_race_pg.py",
    "-v"
)
$vitestArea = @(
    "npx", "vitest", "run",
    "src/features/accounts/investor-profile-panel.test.tsx",
    "src/features/accounts/accounts-page.test.tsx",
    "src/features/accounts/account-detail-panel.test.tsx",
    "src/features/accounts/account-investor-profile-select.test.tsx",
    "src/features/accounts/account-settings-panel.test.tsx",
    "--reporter=verbose"
)

Invoke-Gate "pytest-area.txt" $RepoRoot $pytestArea
Invoke-Gate "pytest-integridad-061.txt" $RepoRoot $pytestIntegrity061
Invoke-Gate "vitest-area.txt" $web $vitestArea
Invoke-Gate "vitest-web-full.txt" $web @("pnpm", "--filter", "@bolsa/web", "test")
if (-not $SkipSecondWebRun) {
    # Segunda ejecución INDEPENDIENTE: confirma que la primera no dependía de caché/orden.
    Invoke-Gate "vitest-web-full-run2.txt" $web @("pnpm", "--filter", "@bolsa/web", "test")
}
Invoke-Gate "tsc.txt" $RepoRoot @("pnpm", "--filter", "@bolsa/web", "typecheck")
Invoke-Gate "eslint.txt" $web @(
    "npx", "eslint", "src/features/accounts", "src/features/config", "src/features/help"
)
Invoke-Gate "contract-check.txt" $web @(
    "node", "scripts/sync-contract.mjs", "&",
    "node", "scripts/sync-contract.mjs", "--check"
)
Invoke-Gate "ruff.txt" $RepoRoot @(
    "uv", "run", "ruff", "check", "packages/py", "apps/api-python",
    "--config", "pyproject.toml", "--output-format=concise"
)
Invoke-Gate "mypy.txt" $RepoRoot @(
    "uv", "run", "mypy",
    "packages/py/domain/src", "packages/py/market/src",
    "packages/py/infrastructure/src", "packages/py/application/src",
    "apps/api-python/src", "--follow-imports=silent"
)
Invoke-Gate "api-responses.txt" $RepoRoot @(
    "uv", "run", "python", "$evidence/api-evidence.py"
)

Write-Host ""
Write-Host "Resumen:" -ForegroundColor Cyan
$results | Format-Table -AutoSize | Out-String | Write-Host
$failed = @($results | Where-Object { $_.Exit -ne 0 })
if ($failed.Count -gt 0) {
    Write-Host ("Gates con fallo: " + (($failed | ForEach-Object { $_.File }) -join ", ")) -ForegroundColor Red
    exit 1
}
Write-Host "Todos los gates verdes." -ForegroundColor Green
exit 0
