# Descarga el motor de IA de Eco: llama.cpp oficial, version para
# tarjetas NVIDIA (CUDA 12.4). Comprueba la huella SHA-256 de cada
# archivo antes de usarlo.
#
# USO (en la carpeta del proyecto):
#   powershell -ExecutionPolicy Bypass -File instalar_motor_ia.ps1
#
# Usa el modelo qwen2.5:7b que ya descargo Ollama (no baja otro).

$ErrorActionPreference = "Stop"
$proyecto = $PSScriptRoot
$destino = Join-Path $proyecto "engines\llama.cpp"
$descargas = Join-Path $proyecto "engines\_descargas"

$archivos = @(
    @{ url = "https://github.com/ggml-org/llama.cpp/releases/download/b12387/llama-b12387-bin-win-cuda-12.4-x64.zip"; sha = "939c94e827c8bc74e2841c5b05643cf35a81b46ec01c6fb0d2732ed41970c2e7" },
    @{ url = "https://github.com/ggml-org/llama.cpp/releases/download/b12387/cudart-llama-bin-win-cuda-12.4-x64.zip"; sha = "8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6" }
)

if (Test-Path (Join-Path $destino "llama-server.exe")) {
    Write-Host "El motor de IA ya esta instalado."
    exit 0
}

New-Item -ItemType Directory -Force -Path $destino, $descargas | Out-Null

foreach ($archivo in $archivos) {
    $zip = Join-Path $descargas ([IO.Path]::GetFileName($archivo.url))
    Write-Host "Descargando $([IO.Path]::GetFileName($zip))..."
    & curl.exe -sSL --fail -o $zip $archivo.url
    if ($LASTEXITCODE -ne 0) { throw "No pude descargar $($archivo.url)" }

    $huella = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
    if ($huella -ne $archivo.sha) {
        Remove-Item $zip
        throw "La huella de $zip no coincide: el archivo no es el esperado."
    }
    Expand-Archive -Path $zip -DestinationPath $destino -Force
}

Remove-Item $descargas -Recurse -Force

# En esta PC (i9-11900K) las versiones del motor optimizadas para CPUs
# mas nuevas se cierran con "instruccion ilegal". Se deja solo la de
# AVX2 (haswell), que funciona en cualquier CPU de los ultimos 10 anos.
$apartadas = Join-Path $destino "cpu_variantes_no_usadas"
New-Item -ItemType Directory -Force -Path $apartadas | Out-Null
Get-ChildItem $destino -Filter "ggml-cpu-*.dll" |
    Where-Object { $_.Name -ne "ggml-cpu-haswell.dll" } |
    Move-Item -Destination $apartadas -Force

Write-Host "Motor de IA instalado en $destino"
