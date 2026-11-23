@echo off
REM Lanza Eco usando el Python de SU PROPIO entorno virtual
REM (.venv), sin depender de que actives el venv a mano antes.
REM %~dp0 = la carpeta donde esta este .bat, sin importar desde
REM donde lo ejecutes (doble clic, Programador de tareas, etc.)

cd /d "%~dp0"

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
