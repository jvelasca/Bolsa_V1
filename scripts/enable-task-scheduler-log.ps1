# Habilita el registro operativo del Programador de tareas (requiere elevacion).
#
# Por que existe: `Microsoft-Windows-TaskScheduler/Operational` estaba deshabilitado, asi
# que la caida del stack del 2026-11-08 a las 17:24 no dejo ni un evento 102/111/329. Con
# el registro activo, cada disparo y cada salida de las tareas de la ventana queda fechado.
#
# Uso (consola elevada):
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\enable-task-scheduler-log.ps1
#
# Idempotente: si ya esta activo, no cambia nada y lo declara.

$ErrorActionPreference = 'Stop'
$log = 'Microsoft-Windows-TaskScheduler/Operational'

$before = (wevtutil gl $log) -join "`n"
if ($before -match 'enabled:\s*true') {
  Write-Output "[scheduler-log] ya estaba habilitado; no se toca"
} else {
  wevtutil sl $log /e:true
  Write-Output "[scheduler-log] habilitado"
}

$after = (wevtutil gl $log) -join "`n"
if ($after -match 'enabled:\s*true') {
  Write-Output "[scheduler-log] verificado: enabled=true"
  exit 0
}
Write-Output "[scheduler-log] FALLO: sigue deshabilitado"
exit 1
