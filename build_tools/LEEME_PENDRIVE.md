# Cortana en pendrive: guía completa

## Aviso importante

Windows **no permite** que un `.exe` en una unidad USB se ejecute solo con
conectarla, en ninguna PC, desde hace más de una década (protección
anti-malware tipo Conficker). Por eso este flujo se divide en dos partes:

- Un `.exe` portable que puedes llevar en el pendrive y usar en cualquier PC
  (con un doble clic, o un acceso directo).
- Un "watcher" opcional que instalas UNA VEZ en tu propia PC, para que esa
  PC en particular lance Cortana sola cada vez que conectes el pendrive.

---

## Paso 1 — Compilar Cortana.exe

En tu PC con Windows, dentro de la carpeta del proyecto (donde está `main.py`):

```
pip install -r requirements.txt
build_tools\build.bat
```

Esto genera `dist\Cortana.exe`. Cópialo (junto con la carpeta `data\` que se
crea al primer uso) a tu pendrive, por ejemplo en:

```
E:\Cortana\dist\Cortana.exe
```

Recuerda: Cortana sigue necesitando que **Ollama** esté corriendo en la PC
donde la ejecutes (`ollama pull qwen3:14b`), y micrófono/altavoces si usas voz.

## Paso 2 — Acceso directo de un clic (funciona en cualquier PC)

Dentro del pendrive, crea un acceso directo a `Cortana.exe` en la raíz de la
unidad con un nombre llamativo, por ejemplo `▶ Iniciar Cortana.lnk`. Así, en
cualquier PC, conectas el pendrive, abres el explorador y con un solo doble
clic la arrancas. Esto es lo máximo que se puede automatizar de forma segura
en una PC que no es tuya.

## Paso 3 — Arranque automático SOLO en tu propia PC (opcional)

Si quieres que, específicamente en tu PC, Cortana se lance sola al conectar
el pendrive:

1. Ponle un nombre (etiqueta) al pendrive, por ejemplo `CORTANA_USB`:
   clic derecho sobre la unidad en el Explorador → **Cambiar nombre**.

2. Abre `build_tools\usb_watcher.py` y confirma que:
   - `VOLUME_LABEL` coincide con el nombre que le pusiste al pendrive.
   - `EXE_RELATIVE_PATH` coincide con la ruta real del .exe dentro del
     pendrive (por defecto `Cortana\dist\Cortana.exe`).

3. Ejecuta:

   ```
   build_tools\install_watcher.bat
   ```

   Esto compila el watcher y lo copia a tu carpeta de Inicio de Windows
   (`shell:startup`), para que arranque solo cada vez que inicies sesión.

4. Desde ese momento, en esa PC: conectas el pendrive → en unos segundos
   (poll cada 3s) el watcher lo detecta por su etiqueta y lanza
   `Cortana.exe` automáticamente.

   - Si desconectas y vuelves a conectar el pendrive, se relanza.
   - El watcher NO hace nada en ninguna otra PC — solo en la que lo
     instalaste.

### Desinstalar el watcher

Borra `CortanaWatcher.exe` de:
`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`

---

## Preguntas frecuentes

**¿Puedo hacer que se ejecute solo en la PC de un amigo, sin instalar nada
ahí?** No. Cualquier método que lograra eso sería, por definición, la misma
técnica que usa el malware de USB, y Windows la bloquea a propósito.

**¿Y si desactivo esa protección en el registro?** Se puede, pero no te
ayudo a hacerlo: es exactamente la puerta que permitió que gusanos como
Conficker se propagaran por USB en su momento, y desactivarla deja tu PC
expuesta a cualquier pendrive infectado, no solo al tuyo.
