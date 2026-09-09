# Cómo publicar actualizaciones de Cortana

## Configuración inicial (una sola vez)

1. **Crea un repositorio en GitHub** (si no tienes uno):
   - Ve a https://github.com/new
   - Nómbralo como quieras, ej. `cortana-ia`
   - Márcalo como **público** (necesario para que el auto-actualizador
     lo pueda leer sin necesitar una contraseña/token).

2. **Sube tu proyecto** (en la carpeta de tu proyecto, en PowerShell):

   ```powershell
   git init
   git add .
   git commit -m "Primera version"
   git branch -M main
   git remote add origin https://github.com/TU_USUARIO/cortana-ia.git
   git push -u origin main
   ```

3. **MUY IMPORTANTE — crea un `.gitignore`** para que tus datos
   personales (memoria, comandos aprendidos, caché de programas)
   NUNCA se suban al repositorio ni se sobreescriban al actualizar.
   Crea un archivo llamado `.gitignore` en la raíz del proyecto con:

   ```
   data/*.json
   .venv/
   __pycache__/
   *.pyc
   ```

   Si ya habías subido esos `.json` antes de crear el `.gitignore`,
   quítalos del repositorio (no de tu PC) con:
   ```powershell
   git rm --cached data/*.json
   git commit -m "Dejar de trackear datos personales"
   git push
   ```

4. **Configura `core/updater.py`** — cambia esta línea:

   ```python
   GITHUB_REPO = "TU_USUARIO/TU_REPO"
   ```

   por, por ejemplo:

   ```python
   GITHUB_REPO = "junel/cortana-ia"
   ```

## Cada vez que quieras publicar una versión nueva

1. Haz tus cambios de código normal.

2. Sube el número de versión en el archivo `VERSION` (raíz del
   proyecto), por ejemplo de `1.0.0` a `1.1.0`.

3. Sube los cambios a GitHub:

   ```powershell
   git add .
   git commit -m "Descripcion de lo que cambio"
   git push
   ```

4. En GitHub, ve a tu repositorio → pestaña **"Releases"** →
   **"Draft a new release"**:
   - En "Tag": escribe `v1.1.0` (con la "v" adelante, y que coincida
     con lo que pusiste en `VERSION`)
   - En "Release title": lo que quieras, ej. "Versión 1.1.0"
   - En la descripción: qué cambió (esto es lo que Cortana podría
     leerte como changelog, si se lo pides)
   - Clic en **"Publish release"**

   No necesitas subir ningún archivo .zip manualmente — GitHub genera
   uno automáticamente con todo el código de esa versión.

## Cómo se entera Cortana

- **Al arrancar**, Cortana revisa en silencio si hay una versión más
  nueva y te avisa por consola si la hay (no instala sola).
- **Cuando tú quieras**, dile: *"busca actualizaciones"* — revisa,
  descarga, instala, y te pide reiniciar el programa.

## Notas

- Esto actualiza el código porque Cortana corre con `python main.py`
  (el archivo se puede sobreescribir mientras corre; el que
  realmente se ejecuta es `python.exe`, no `main.py` directamente).
  Si en algún momento conviertes esto en un `.exe` con PyInstaller
  para el pendrive, ese `.exe` **no** se auto-actualiza con este
  mecanismo — para el pendrive sigue el flujo manual de
  `build_tools\build.bat` que ya tienes.
- El repositorio debe ser público para que esto funcione sin
  configurar autenticación. Si prefieres privado, se puede hacer,
  pero hay que agregar un token de acceso personal — avísame si
  quieres esa versión.
