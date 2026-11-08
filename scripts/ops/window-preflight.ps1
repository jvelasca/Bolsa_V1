#Requires -Version 5.1
<#
.SYNOPSIS
    Preflight READ-ONLY de la ventana PAPER: los 6 puntos del runbook.

.DESCRIPTION
    Comprueba, en este orden, las seis precondiciones que el expediente
    `docs/engineering/cierre-medicion-2026-11-06.md` exige antes de dejar que la
    tarea programada mida un dia:

      1. la tarea `BolsaV1_WindowForward` apunta al `.cmd` esperado;
      2. `window-pin --check` da `freeze OK` en la raiz Y en el arbol sellado;
      3. el sello esta en el commit esperado, limpio, con los tree hashes del pin
         y con su propio `.venv` resolviendo dentro del sello;
      4. no hay candado activo ni proceso del runner que pueda bloquear la corrida;
      5. la maquina no se suspende por CA (espera/disco/hibernacion a 0) y esta
         enchufada;
      6. el sello tiene `.env`, el venue es `paper` y no hay variables LIVE.

    NO modifica NADA: no escribe ficheros, no lanza `run-day`, no toca la BD, no
    reclama ni borra locks. Solo lee el registro de energia, `git`, el pin y el
    programador de tareas.

    Codigos de salida: 0 = todo OK (los WARN no bloquean); 1 = al menos un FAIL;
    2 = error inesperado (p. ej. falta `node` o el sello no existe).

.PARAMETER Day
    Dia de la ventana en formato `yyyyMMdd`. Por defecto, hoy.

.PARAMETER Main
    Raiz del arbol de desarrollo.

.PARAMETER Seal
    Worktree sellado del que mide la tarea.

.PARAMETER TaskName
    Nombre de la tarea programada.

.EXAMPLE
    powershell -NoProfile -File scripts\ops\window-preflight.ps1 -Day 20261109

.EXAMPLE
    powershell -NoProfile -File scripts\ops\window-preflight.ps1 -Day 20261109 -Verbose
#>
[CmdletBinding()]
param(
    [string]$Day = (Get-Date -Format 'yyyyMMdd'),
    [string]$Main = 'C:\Users\josea\Documents\Informatica\Typescript\Bolsa_V1',
    [string]$Seal = '',
    [string]$TaskName = 'BolsaV1_WindowForward'
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($Seal)) {
    $Seal = Join-Path $Main '.cursor\worktrees\window-seal-183'
}

$script:Results = New-Object System.Collections.Generic.List[object]

function Add-Result {
    param(
        [Parameter(Mandatory)][string]$Check,
        [Parameter(Mandatory)][ValidateSet('OK', 'WARN', 'FAIL', 'SKIP')][string]$Status,
        [Parameter(Mandatory)][string]$Detail
    )
    $script:Results.Add([pscustomobject]@{ Check = $Check; Status = $Status; Detail = $Detail })
    Write-Host ("[{0,-4}] {1,-28} {2}" -f $Status, $Check, $Detail)
}

function Get-AcIndex {
    param(
        [Parameter(Mandatory)][string]$SubGroup,
        [Parameter(Mandatory)][string]$Setting
    )
    $schemes = 'HKLM:\SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes'
    $scheme = (Get-ItemProperty -Path $schemes -ErrorAction SilentlyContinue).ActivePowerScheme
    if (-not $scheme) { return $null }
    $path = Join-Path $schemes "$scheme\$SubGroup\$Setting"
    if (-not (Test-Path $path)) { return $null }
    $value = (Get-ItemProperty -Path $path -ErrorAction SilentlyContinue).ACSettingIndex
    if ($null -eq $value) { return $null }
    return [uint32]$value
}

function Invoke-PinCheck {
    param([Parameter(Mandatory)][string]$Path)
    Push-Location -LiteralPath $Path
    try {
        $output = & node 'scripts/window-pin.mjs' --check 2>&1 | Out-String
        $code = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
    return [pscustomobject]@{ ExitCode = $code; Output = $output.Trim() }
}

function Get-PinAppsHash {
    $file = Join-Path $Main 'scripts\lib\window-forward.mjs'
    if (-not (Test-Path $file)) { return $null }
    $match = Select-String -Path $file -Pattern "appsHash:\s*'([0-9a-f]+)'" | Select-Object -First 1
    if (-not $match) { return $null }
    return $match.Matches[0].Groups[1].Value
}

Write-Host ''
Write-Host "Preflight ventana PAPER -- dia $Day"
Write-Host "  raiz : $Main"
Write-Host "  sello: $Seal"
Write-Host ''

if (-not (Test-Path -LiteralPath $Seal)) {
    Write-Host "[FAIL] el sello no existe: $Seal"
    exit 2
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host '[FAIL] `node` no esta en el PATH'
    exit 2
}

# --- 1. Tarea programada ----------------------------------------------------
try {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    $info = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction Stop
    $action = @($task.Actions)[0].Execute
    if ($action -like '*window-forward-task.cmd') {
        Add-Result -Check 'task.cmd' -Status 'OK' -Detail $action
    }
    else {
        Add-Result -Check 'task.cmd' -Status 'FAIL' -Detail "accion inesperada: $action"
    }
    $state = [string]$task.State
    if ($state -eq 'Ready') {
        Add-Result -Check 'task.state' -Status 'OK' -Detail "Ready / NextRunTime $($info.NextRunTime)"
    }
    else {
        Add-Result -Check 'task.state' -Status 'FAIL' -Detail "estado $state (NextRunTime $($info.NextRunTime))"
    }
    Add-Result -Check 'task.history' -Status 'OK' -Detail ("LastRun {0} / LastResult {1}" -f $info.LastRunTime, $info.LastTaskResult)

    # El primer disparo pendiente debe caer EN el dia que se va a medir: si cae
    # antes, la tarea todavia tiene por delante un dia que no es el objetivo (ese
    # dia escribira su propia fila y puede dejar un lock).
    $target = [datetime]::ParseExact($Day, 'yyyyMMdd', [Globalization.CultureInfo]::InvariantCulture)
    if ($info.NextRunTime -and $info.NextRunTime.Date -ne $target.Date) {
        Add-Result -Check 'task.nextrun' -Status 'WARN' -Detail ("NextRunTime {0} != dia objetivo {1}" -f $info.NextRunTime, $target.ToString('yyyy-MM-dd'))
    }
    else {
        Add-Result -Check 'task.nextrun' -Status 'OK' -Detail ("proximo disparo el dia objetivo: {0}" -f $info.NextRunTime)
    }
}
catch {
    Add-Result -Check 'task' -Status 'FAIL' -Detail "no se pudo leer la tarea '$TaskName': $($_.Exception.Message)"
}

# --- 2. Freeze en la raiz y en el sello -------------------------------------
$pinApps = Get-PinAppsHash
foreach ($target in @(@{ Name = 'freeze.root'; Path = $Main }, @{ Name = 'freeze.seal'; Path = $Seal })) {
    try {
        $pin = Invoke-PinCheck -Path $target.Path
        if ($pin.ExitCode -eq 0) {
            $hashLine = ($pin.Output -split "`r?`n" | Where-Object { $_ -match 'appsHash' } | Select-Object -First 1)
            $hash = if ($hashLine) { ($hashLine -replace '^.*appsHash\s+', '').Trim() } else { '?' }
            if ($pinApps -and $hash -ne $pinApps) {
                Add-Result -Check $target.Name -Status 'FAIL' -Detail "freeze OK pero apps=$hash != pin $pinApps"
            }
            else {
                Add-Result -Check $target.Name -Status 'OK' -Detail "freeze OK / apps $hash"
            }
        }
        else {
            $first = ($pin.Output -split "`r?`n" | Select-Object -First 1)
            Add-Result -Check $target.Name -Status 'FAIL' -Detail "exit $($pin.ExitCode): $first"
        }
    }
    catch {
        Add-Result -Check $target.Name -Status 'FAIL' -Detail $_.Exception.Message
    }
}

# --- 3. Identidad del sello -------------------------------------------------
try {
    $head = (& git -C $Seal rev-parse --short HEAD).Trim()
    $branch = (& git -C $Seal rev-parse --abbrev-ref HEAD).Trim()
    $sealApps = (& git -C $Seal rev-parse 'HEAD:apps').Trim()
    $sealPackages = (& git -C $Seal rev-parse 'HEAD:packages').Trim()
    $dirty = (@(& git -C $Seal status --porcelain) | Where-Object { $_ }).Count

    if ($pinApps -and $sealApps -ne $pinApps) {
        Add-Result -Check 'seal.tree' -Status 'FAIL' -Detail "HEAD:apps $sealApps != pin $pinApps"
    }
    else {
        Add-Result -Check 'seal.tree' -Status 'OK' -Detail "$head ($branch) / apps ${sealApps}".Substring(0, [Math]::Min(120, "$head ($branch) / apps ${sealApps}".Length))
    }
    if ($dirty -eq 0) {
        Add-Result -Check 'seal.clean' -Status 'OK' -Detail 'arbol limpio'
    }
    else {
        Add-Result -Check 'seal.clean' -Status 'FAIL' -Detail "$dirty fichero(s) sin commitear; el pin debe estar COMMITEADO"
    }

    $py = Join-Path $Seal '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $py)) {
        Add-Result -Check 'seal.venv' -Status 'FAIL' -Detail 'falta .venv\Scripts\python.exe en el sello'
    }
    else {
        $module = (& $py -c "import bolsa_application; print(bolsa_application.__file__)" 2>&1 | Out-String).Trim()
        if ($module -like "$Seal*") {
            Add-Result -Check 'seal.venv' -Status 'OK' -Detail 'bolsa_application resuelve dentro del sello'
        }
        else {
            Add-Result -Check 'seal.venv' -Status 'FAIL' -Detail "bolsa_application resuelve FUERA del sello: $module"
        }
    }
    Write-Verbose "seal packages tree: $sealPackages"
}
catch {
    Add-Result -Check 'seal' -Status 'FAIL' -Detail $_.Exception.Message
}

# --- 4. Locks y procesos ----------------------------------------------------
$runs = Join-Path $Main 'operability_runs\window-runs'
$dayDir = Join-Path $runs $Day
if (Test-Path -LiteralPath $dayDir) {
    $locks = @(Get-ChildItem -LiteralPath $dayDir -Recurse -Force -Filter '.run.lock' -ErrorAction SilentlyContinue)
    if ($locks.Count -gt 0) {
        Add-Result -Check 'lock.day' -Status 'FAIL' -Detail "existe $($locks[0].FullName) para el dia $Day"
    }
    else {
        Add-Result -Check 'lock.day' -Status 'WARN' -Detail "el dia $Day ya tiene directorio (intento previo) pero sin lock"
    }
}
else {
    Add-Result -Check 'lock.day' -Status 'OK' -Detail "sin directorio previo para $Day"
}

$allLocks = @(Get-ChildItem -LiteralPath $runs -Recurse -Force -Filter '.run.lock' -ErrorAction SilentlyContinue)
if ($allLocks.Count -eq 0) {
    Add-Result -Check 'lock.any' -Status 'OK' -Detail 'ningun .run.lock en window-runs'
}
else {
    Add-Result -Check 'lock.any' -Status 'WARN' -Detail ("{0} lock(s) de otros dias: {1}" -f $allLocks.Count, (($allLocks | ForEach-Object { $_.Directory.Parent.Name }) -join ', '))
}

$nodeProcs = @(Get-CimInstance -ClassName Win32_Process -Filter "Name = 'node.exe'" -ErrorAction SilentlyContinue)
$runners = @($nodeProcs | Where-Object { $_.CommandLine -like '*window-forward-runner*' })
if ($runners.Count -eq 0) {
    Add-Result -Check 'proc.runner' -Status 'OK' -Detail 'ningun window-forward-runner vivo'
}
else {
    Add-Result -Check 'proc.runner' -Status 'FAIL' -Detail ("PIDs: " + (($runners | ForEach-Object { $_.ProcessId }) -join ', '))
}

# --- 5. Energia -------------------------------------------------------------
$never = @{
    STANDBYIDLE  = @('238c9fa8-0aad-41ed-83f4-97be242c8f20', '29f6c1db-86da-48c5-9fdb-f2b67b1f44da')
    HIBERNATEIDLE = @('238c9fa8-0aad-41ed-83f4-97be242c8f20', '9d7815a6-7ee4-497e-8888-515a05f02364')
    DISKIDLE     = @('0012ee47-9041-4b5d-9b77-535fba8b1442', '6738e2c4-e8a5-4a42-b16a-e040e769756e')
}
foreach ($name in @('STANDBYIDLE', 'DISKIDLE', 'HIBERNATEIDLE')) {
    $idx = Get-AcIndex -SubGroup $never[$name][0] -Setting $never[$name][1]
    if ($null -eq $idx) {
        Add-Result -Check "power.$name" -Status 'WARN' -Detail 'no se pudo leer el indice AC en el registro'
    }
    elseif ($idx -eq 0) {
        Add-Result -Check "power.$name" -Status 'OK' -Detail 'AC = 0 (nunca)'
    }
    else {
        Add-Result -Check "power.$name" -Status 'FAIL' -Detail ("AC = {0} s; la maquina se suspenderia" -f $idx)
    }
}

try {
    $battery = Get-CimInstance -ClassName Win32_Battery -ErrorAction Stop | Select-Object -First 1
    if (-not $battery) {
        Add-Result -Check 'power.source' -Status 'WARN' -Detail 'sin bateria detectada (equipo de sobremesa?)'
    }
    elseif ($battery.BatteryStatus -eq 2) {
        Add-Result -Check 'power.source' -Status 'OK' -Detail ("enchufado / carga {0}%" -f $battery.EstimatedChargeRemaining)
    }
    else {
        Add-Result -Check 'power.source' -Status 'FAIL' -Detail ("BatteryStatus {0}: NO esta en CA" -f $battery.BatteryStatus)
    }
}
catch {
    Add-Result -Check 'power.source' -Status 'WARN' -Detail $_.Exception.Message
}

# --- 6. Entorno del sello ---------------------------------------------------
$sealEnv = Join-Path $Seal '.env'
$mainEnv = Join-Path $Main '.env'
if (Test-Path -LiteralPath $sealEnv) {
    Add-Result -Check 'env.present' -Status 'OK' -Detail 'el sello tiene .env propio'
}
elseif (Test-Path -LiteralPath $mainEnv) {
    Add-Result -Check 'env.present' -Status 'WARN' -Detail 'sin .env en el sello; el .cmd lo copiara de la raiz'
}
else {
    Add-Result -Check 'env.present' -Status 'FAIL' -Detail 'no hay .env ni en el sello ni en la raiz'
}

$envFile = if (Test-Path -LiteralPath $sealEnv) { $sealEnv } else { $mainEnv }
if (Test-Path -LiteralPath $envFile) {
    $venue = Select-String -Path $envFile -Pattern '^\s*BROKER_VENUE\s*=\s*(.+?)\s*$' | Select-Object -First 1
    if ($venue -and $venue.Matches[0].Groups[1].Value.Trim("`"'") -eq 'paper') {
        Add-Result -Check 'env.venue' -Status 'OK' -Detail 'BROKER_VENUE=paper'
    }
    elseif ($venue) {
        Add-Result -Check 'env.venue' -Status 'FAIL' -Detail ('BROKER_VENUE=' + $venue.Matches[0].Groups[1].Value)
    }
    else {
        Add-Result -Check 'env.venue' -Status 'FAIL' -Detail 'sin BROKER_VENUE explicito'
    }

    $live = @(Select-String -Path $envFile -Pattern '^\s*[A-Za-z0-9_]*LIVE[A-Za-z0-9_]*\s*=')
    if ($live.Count -eq 0) {
        Add-Result -Check 'env.live' -Status 'OK' -Detail 'ninguna variable LIVE'
    }
    else {
        Add-Result -Check 'env.live' -Status 'FAIL' -Detail (($live | ForEach-Object { ($_.Line -split '=')[0].Trim() }) -join ', ')
    }
}

# --- Resumen ----------------------------------------------------------------
$fails = @($script:Results | Where-Object { $_.Status -eq 'FAIL' })
$warns = @($script:Results | Where-Object { $_.Status -eq 'WARN' })

Write-Host ''
Write-Host ("Resumen: {0} OK / {1} WARN / {2} FAIL" -f @($script:Results | Where-Object { $_.Status -eq 'OK' }).Count, $warns.Count, $fails.Count)

if ($fails.Count -gt 0) {
    Write-Host 'Dictamen: NO LANZAR -- hay precondiciones sin cumplir.' -ForegroundColor Red
    exit 1
}
if ($warns.Count -gt 0) {
    Write-Host 'Dictamen: ADELANTE con reservas (revisar los WARN).' -ForegroundColor Yellow
    exit 0
}
Write-Host 'Dictamen: ADELANTE -- las 6 precondiciones se cumplen.' -ForegroundColor Green
exit 0
