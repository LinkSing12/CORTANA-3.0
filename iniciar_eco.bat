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

REM /min: abre la ventana minimizada en vez de al frente. Puedes
REM restaurarla desde la barra de tareas si quieres escribir un
REM comando por texto en vez de decirlo por voz.
start "Eco" /min ".venv\Scripts\python.exe" main.py
