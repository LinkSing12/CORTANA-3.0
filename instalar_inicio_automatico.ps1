# Registra una Tarea Programada de Windows para que Eco se abra
# sola (minimizada) cada vez que inicias sesion, sin necesitar
# permisos de administrador.
#
# USO (desde PowerShell, en la carpeta del proyecto):
#   powershell -ExecutionPolicy Bypass -File instalar_inicio_automatico.ps1
#
# PARA QUITARLO despues, desde PowerShell:
#   Unregister-ScheduledTask -TaskName "Eco - Inicio automatico"

$ErrorActionPreference = "Stop"

$nombreTarea = "Eco - Inicio automatico"

# Si antes registraste la tarea con el nombre viejo, se quita para que no
# queden DOS tareas arrancando el asistente al mismo tiempo.
Unregister-ScheduledTask -TaskName "Cortana - Inicio automatico" -Confirm:$false -ErrorAction SilentlyContinue
$proyecto = $PSScriptRoot
$bat = Join-Path $proyecto "iniciar_eco.bat"

if (-not (Test-Path $bat)) {
    Write-Host "No encontre iniciar_eco.bat en $proyecto"
    Write-Host "Ponlo en la misma carpeta que este script e intenta de nuevo."
    exit 1
}

$accion = New-ScheduledTaskAction -Execute $bat -WorkingDirectory $proyecto

# Solo cuando INICIAS SESION TU (no otros usuarios de la PC, si la
# compartes con alguien mas).
$disparador = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

# IgnoreNew: si por alguna razon la tarea ya esta corriendo (ej. la
# abriste tu mismo antes de reiniciar), no abre una segunda Eco
# escuchando el microfono al mismo tiempo.
$config = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable

Register-ScheduledTask -TaskName $nombreTarea `
    -Action $accion -Trigger $disparador -Settings $config -Force | Out-Null

Write-Host "Listo. Eco se va a abrir sola (minimizada) la proxima vez que inicies sesion."
Write-Host ""
Write-Host "Para probarlo ahora mismo sin reiniciar:"
Write-Host "  Start-ScheduledTask -TaskName '$nombreTarea'"
Write-Host ""
Write-Host "Para quitar el inicio automatico mas adelante:"
Write-Host "  Unregister-ScheduledTask -TaskName '$nombreTarea'"
