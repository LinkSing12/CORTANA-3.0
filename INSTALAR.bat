@echo off
REM ============================================================
REM  UN SOLO DOBLE CLIC: instala Python, Ollama (+ modelo),
REM  Tesseract-OCR, el entorno virtual, las dependencias de
REM  Python, la voz de Piper si se puede, y deja Eco
REM  arrancando sola con Windows.
REM
REM  Uso: despues de formatear/instalar Windows de cero, pon
REM  esta carpeta del proyecto donde quieras y hazle doble
REM  clic a este archivo. Nada mas.
REM ============================================================

cd /d "%~dp0"

echo Instalando todo lo que Eco necesita...
echo Esto puede tardar varios minutos (Ollama descarga unos GB).
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "instalar_todo.ps1"

echo.
echo ============================================================
echo  Si no viste ningun error arriba, ya quedo todo listo.
echo  Eco va a abrirse sola la proxima vez que inicies sesion.
echo ============================================================
pause
