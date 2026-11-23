# Registra una Tarea Programada de Windows para que Eco se abra
# sola (minimizada) y COMO ADMINISTRADOR cada vez que inicias sesion.
# Al ser una tarea con "privilegios mas altos", Windows no pregunta
# nada al iniciar sesion: solo pide permiso una vez, al registrarla.
#
# USO (desde PowerShell, en la carpeta del proyecto):
#   powershell -ExecutionPolicy Bypass -File instalar_inicio_automatico.ps1
#
# PARA QUITARLO despues, desde PowerShell como administrador:
#   Unregister-ScheduledTask -TaskName "Eco - Inicio automatico"

$ErrorActionPreference = "Stop"

# Registrar una tarea de administrador requiere ser administrador.
# Si no lo eres en esta ventana, se vuelve a abrir este script pidiendo
# permiso a Windows (la ventana de "¿Quieres permitir...?").
$esAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $esAdmin) {
    Write-Host "Pidiendo permiso de administrador para registrar la tarea..."
    $proceso = Start-Process powershell -Verb RunAs -Wait -PassThru -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$PSCommandPath`""
    )
    exit $proceso.ExitCode
}

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
# AllowStartIfOnBatteries: por defecto Windows no arranca la tarea si
# una laptop esta desenchufada.
$config = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

# RunLevel Highest = se ejecuta como administrador, sin preguntar.
$usuario = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $usuario -LogonType Interactive -RunLevel Highest

Register-ScheduledTask -TaskName $nombreTarea `
    -Action $accion -Trigger $disparador -Settings $config -Principal $principal -Force | Out-Null

Write-Host "Listo. Eco se va a abrir sola (minimizada y como administrador) la proxima vez que inicies sesion."
Write-Host ""
Write-Host "Para probarlo ahora mismo sin reiniciar:"
Write-Host "  Start-ScheduledTask -TaskName '$nombreTarea'"
Write-Host ""
Write-Host "Para quitar el inicio automatico mas adelante:"
Write-Host "  Unregister-ScheduledTask -TaskName '$nombreTarea'"
