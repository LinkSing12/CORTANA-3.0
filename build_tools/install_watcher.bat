@echo off
REM =========================================================
REM  1) Compila usb_watcher.py a un .exe silencioso.
REM  2) Lo copia a la carpeta de Inicio de Windows para que
REM     arranque solo cuando enciendes/inicias sesion en tu PC.
REM =========================================================

cd /d "%~dp0"

echo Compilando CortanaWatcher.exe ...
pyinstaller --noconfirm --onefile --windowed --name CortanaWatcher usb_watcher.py

if not exist "dist\CortanaWatcher.exe" (
    echo Algo fallo compilando el watcher.
    pause
    exit /b 1
)

set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup

copy /Y "dist\CortanaWatcher.exe" "%STARTUP%\CortanaWatcher.exe"

echo.
echo LISTO. CortanaWatcher.exe se instalo en:
echo %STARTUP%
echo.
echo A partir de ahora, cada vez que inicies sesion en ESTA PC,
echo el watcher se activara solo y lanzara Cortana.exe en cuanto
echo detecte el pendrive con la etiqueta configurada en usb_watcher.py.
echo.
echo Para desinstalarlo: borra CortanaWatcher.exe de esa carpeta de Inicio.
pause
