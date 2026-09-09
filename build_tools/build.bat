@echo off
REM =========================================================
REM  Compila Cortana a un .exe portable con PyInstaller.
REM  Ejecuta este .bat DENTRO de la carpeta raiz del proyecto
REM  (donde esta main.py), en tu PC con Windows.
REM =========================================================

cd /d "%~dp0.."

echo Instalando PyInstaller si hace falta...
pip install pyinstaller

echo.
echo Compilando Cortana.exe ...
pyinstaller --noconfirm --onefile --console --name Cortana ^
  --hidden-import=pyttsx3.drivers ^
  --hidden-import=pyttsx3.drivers.sapi5 ^
  --hidden-import=win32timezone ^
  main.py

echo.
if exist "dist\Cortana.exe" (
    echo LISTO. El ejecutable esta en: dist\Cortana.exe
) else (
    echo Algo fallo. Revisa los mensajes de arriba.
)
pause
