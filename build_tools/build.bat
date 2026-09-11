@echo off
REM =========================================================
REM  Compila Cortana a un .exe portable con PyInstaller.
REM  Ejecuta este .bat DENTRO de la carpeta build_tools, en tu
REM  PC con Windows, con el .venv del proyecto activado.
REM =========================================================

cd /d "%~dp0.."

echo Instalando PyInstaller si hace falta...
python -m pip install pyinstaller

echo.
echo Compilando Cortana.exe ...
python -m PyInstaller --noconfirm --onefile --console --name Cortana ^
  --hidden-import=pyttsx3.drivers ^
  --hidden-import=pyttsx3.drivers.sapi5 ^
  --hidden-import=win32timezone ^
  --hidden-import=pywintypes ^
  --hidden-import=win32com.client ^
  main.py

echo.
if exist "dist\Cortana.exe" (
    echo LISTO. El ejecutable esta en: dist\Cortana.exe
    echo.
    echo IMPORTANTE: junto al .exe en el pendrive tambien debes llevar
    echo la carpeta "data" con el JSON de programas cacheados, o dejar
    echo que Cortana la genere sola en el primer uso.
) else (
    echo Algo fallo. Revisa los mensajes de arriba.
)
pause
