@echo off
REM Lanza Eco usando el Python de SU PROPIO entorno virtual
REM (.venv), sin depender de que actives el venv a mano antes.
REM %~dp0 = la carpeta donde esta este .bat, sin importar desde
REM donde lo ejecutes (doble clic, Programador de tareas, etc.)

cd /d "%~dp0"

REM Eco funciona como administrador. Si este .bat se abrio sin esos
REM permisos (doble clic), se relanza: primero por la tarea programada,
REM que ya tiene permiso y no pregunta nada; si no existe, Windows pide
REM permiso con su ventana de "¿Quieres permitir...?".
net session >nul 2>&1
if errorlevel 1 (
    schtasks /query /tn "Eco - Inicio automatico" /xml 2>nul | find "HighestAvailable" >nul
    if not errorlevel 1 (
        schtasks /run /tn "Eco - Inicio automatico" >nul
    ) else (
        powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    )
    exit /b
)

if not exist ".venv\Scripts\python.exe" (
    echo No encontre .venv\Scripts\python.exe en esta carpeta.
    echo Ajusta la ruta en este archivo si tu entorno virtual
    echo se llama distinto o esta en otro lugar.
    pause
    exit /b 1
)

REM Eco usa su propio motor de IA (engines\llama.cpp) y lo arranca solo.
REM Ollama solo hace falta si ese motor no esta instalado.
if exist "engines\llama.cpp\llama-server.exe" goto abrir_eco

where ollama >nul 2>nul
if not errorlevel 1 (
    tasklist /FI "IMAGENAME eq ollama.exe" | find /I "ollama.exe" >nul
    if errorlevel 1 powershell -NoProfile -WindowStyle Hidden -Command "Start-Process ollama -ArgumentList 'serve' -WindowStyle Hidden"
)

:abrir_eco

REM /min: abre la ventana minimizada en vez de al frente. Puedes
REM restaurarla desde la barra de tareas si quieres escribir un
REM comando por texto en vez de decirlo por voz.
start "Eco" /min ".venv\Scripts\python.exe" main.py
