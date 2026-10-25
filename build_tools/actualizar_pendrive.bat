@echo off
setlocal

REM =========================================================
REM  Compila Cortana.exe Y lo sincroniza al pendrive, en un
REM  solo paso. Corre esto cada vez que quieras llevar tus
REM  cambios mas recientes al pendrive.
REM =========================================================

REM ---------------------------------------------------------
REM  AJUSTA ESTO: la letra de tu pendrive
REM ---------------------------------------------------------
set PENDRIVE=G:

cd /d "%~dp0.."

echo.
echo ========================================
echo  PASO 1/2 - Compilando Cortana.exe
echo ========================================
python -m pip install pyinstaller >nul
python -m PyInstaller --noconfirm --onefile --console --name Cortana ^
  --hidden-import=pyttsx3.drivers ^
  --hidden-import=pyttsx3.drivers.sapi5 ^
  --hidden-import=win32timezone ^
  --hidden-import=pywintypes ^
  --hidden-import=win32com.client ^
  main.py

if not exist "dist\Cortana.exe" (
    echo.
    echo ERROR: la compilacion fallo. Revisa los mensajes de arriba.
    pause
    exit /b 1
)

echo.
echo ========================================
echo  PASO 2/2 - Copiando al pendrive %PENDRIVE%
echo ========================================

if not exist "%PENDRIVE%\" (
    echo.
    echo ERROR: no encuentro el pendrive en %PENDRIVE%
    echo Conecta el pendrive, confirma su letra real, y ajusta
    echo la linea "set PENDRIVE=" al inicio de este archivo si
    echo cambio de letra.
    pause
    exit /b 1
)

robocopy "%cd%" "%PENDRIVE%\CORTANA 3.0" /E /XD build .git __pycache__ /XF *.pyc

echo.
echo ========================================
echo  LISTO
echo ========================================
echo Cortana.exe actualizado y copiado a:
echo %PENDRIVE%\CORTANA 3.0\dist\Cortana.exe
echo.
echo Recuerda tener "Iniciar Cortana.bat" en la raiz del pendrive
echo (%PENDRIVE%\) para poder abrirlo con doble clic.
pause
