@echo off
REM =========================================================
REM  Lanzador portable de Cortana.
REM  Funciona sin importar que letra de unidad (E:, F:, G:...)
REM  le asigne Windows al pendrive en cada PC, porque busca el
REM  ejecutable en una ruta RELATIVA a este mismo archivo.
REM =========================================================

start "" "%~dp0CORTANA 3.0\dist\Cortana.exe"
