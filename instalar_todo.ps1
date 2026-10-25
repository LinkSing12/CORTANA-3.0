# =====================================================================
# INSTALADOR COMPLETO DE ECO
#
# Pensado para correr UNA VEZ en un Windows recien formateado/instalado
# de cero. Deja todo listo: Python, Ollama (+ el modelo que usa
# core/brain.py), Tesseract-OCR (para el boton Jugar de Riot Client),
# el entorno virtual del proyecto, todas las dependencias de pip, y de
# regalo intenta descargar la voz de Piper (si falla, Eco igual
# funciona con la voz clasica de Windows).
#
# USO (parado en la carpeta del proyecto, con PowerShell):
#   powershell -ExecutionPolicy Bypass -File instalar_todo.ps1
#
# Requiere que Windows ya tenga winget (viene de fabrica en Windows 10
# 1809+ y Windows 11; si falta, se actualiza "App Installer" desde la
# Microsoft Store).
# =====================================================================

$ErrorActionPreference = "Stop"
$proyecto = $PSScriptRoot
Set-Location $proyecto

# AJUSTA esto si tu core/brain.py usa un modelo distinto a este.
$MODELO_OLLAMA = "qwen2.5:7b"

function Actualizar-Path {
    # Winget instala cosas y actualiza el PATH del REGISTRO, pero esta
    # sesion de PowerShell ya cargo su copia del PATH al abrirse. Sin
    # esto, "python" u "ollama" recien instalados no se encontrarian
    # hasta cerrar y volver a abrir la terminal.
    $machine = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
}

function Comando-Existe($nombre) {
    return [bool](Get-Command $nombre -ErrorAction SilentlyContinue)
}

function Instalar-Winget($id) {
    winget install --id $id -e --accept-package-agreements --accept-source-agreements
    Actualizar-Path
}

Write-Host "=== 1/7: Verificando winget ===" -ForegroundColor Cyan
if (-not (Comando-Existe "winget")) {
    Write-Host "No encontre winget. Actualiza 'App Installer' desde la Microsoft Store e intenta de nuevo." -ForegroundColor Red
    exit 1
}

Write-Host "`n=== 2/7: Python ===" -ForegroundColor Cyan
if (Comando-Existe "python") {
    Write-Host "Python ya esta instalado: $(python --version)"
} else {
    Write-Host "Instalando Python 3.12 con winget..."
    Instalar-Winget "Python.Python.3.12"
}

if (-not (Comando-Existe "python")) {
    Write-Host "Python se instalo pero esta sesion todavia no lo ve en el PATH." -ForegroundColor Yellow
    Write-Host "Cierra esta ventana, abre PowerShell de nuevo en esta carpeta y vuelve a correr este script." -ForegroundColor Yellow
    exit 1
}

Write-Host "`n=== 3/7: Ollama y el modelo $MODELO_OLLAMA ===" -ForegroundColor Cyan
if (Comando-Existe "ollama") {
    Write-Host "Ollama ya esta instalado."
} else {
    Write-Host "Instalando Ollama con winget..."
    Instalar-Winget "Ollama.Ollama"
    Start-Sleep -Seconds 3
}

if (Comando-Existe "ollama") {
    Write-Host "Descargando el modelo $MODELO_OLLAMA (puede tardar varios minutos, son varios GB)..."
    try {
        & ollama pull $MODELO_OLLAMA
    } catch {
        Write-Host "Ollama no respondio de una. Arrancando el servicio e intentando de nuevo..."
        Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 5
        & ollama pull $MODELO_OLLAMA
    }
} else {
    Write-Host "No pude confirmar que 'ollama' quedo en el PATH. Cierra y abre PowerShell de nuevo, y corre a mano: ollama pull $MODELO_OLLAMA" -ForegroundColor Yellow
}

Write-Host "`n=== 4/7: Tesseract-OCR (para el boton Jugar de Riot Client) ===" -ForegroundColor Cyan
if (Comando-Existe "tesseract") {
    Write-Host "Tesseract ya esta instalado."
} else {
    Instalar-Winget "UB-Mannheim.TesseractOCR"
}

Write-Host "`n=== 5/7: Entorno virtual y dependencias de Python ===" -ForegroundColor Cyan
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt

Write-Host "`n=== 6/7: Voz de Piper (opcional, en espanol) ===" -ForegroundColor Cyan
$carpetaVoz = "data\piper_voice"
$modeloVoz = "$carpetaVoz\es_ES-davefx-medium.onnx"
if (Test-Path $modeloVoz) {
    Write-Host "La voz de Piper ya estaba descargada."
} else {
    New-Item -ItemType Directory -Force -Path $carpetaVoz | Out-Null
    $base = "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/davefx/medium"
    try {
        Invoke-WebRequest -Uri "$base/es_ES-davefx-medium.onnx" -OutFile $modeloVoz
        Invoke-WebRequest -Uri "$base/es_ES-davefx-medium.onnx.json" -OutFile "$modeloVoz.json"
        Write-Host "Voz de Piper descargada."
    } catch {
        Write-Host "No pude descargar la voz de Piper (sin internet ahora mismo, o el enlace cambio)." -ForegroundColor Yellow
        Write-Host "No pasa nada: Eco habla con la voz clasica de Windows mientras tanto." -ForegroundColor Yellow
    }
}

Write-Host "`n=== 7/7: Inicio automatico con Windows ===" -ForegroundColor Cyan
$scriptInicio = Join-Path $proyecto "instalar_inicio_automatico.ps1"
if (Test-Path $scriptInicio) {
    & $scriptInicio
} else {
    Write-Host "No encontre instalar_inicio_automatico.ps1 junto a este script, asi que me lo salto." -ForegroundColor Yellow
    Write-Host "Sin eso, vas a tener que abrir Eco a mano con iniciar_eco.bat cada vez."
}

Write-Host "`n¡Listo! Todo instalado." -ForegroundColor Green
Write-Host ""
Write-Host "Para arrancar Eco ahora mismo, sin esperar a la proxima vez que inicies sesion:"
Write-Host "  .\iniciar_eco.bat"
