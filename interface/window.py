"""
ECO - Interfaz gráfica: cara de robot 3D en una esquina.

Reemplaza el panel grande anterior por una ventanita pequeña, sin
bordes, siempre encima de las demás, anclada a una esquina de la
pantalla, con una cara de robot renderizada en 3D REAL (con
profundidad y rotación) usando transformaciones 3D de CSS — sin
necesitar Three.js ni ninguna librería externa de JavaScript, así que
no depende de internet ni de un CDN para verse bien.

IMPORTANTE — no pude ver esto renderizado en una pantalla real
(este entorno no tiene una GUI de Windows), así que trátalo como una
PRIMERA VERSIÓN: la lógica de Python (conexión con assistant.py,
hilos, etc.) la puedo garantizar, pero el detalle visual exacto
(tamaños, animación) casi seguro va a necesitar un ajuste o dos
una vez que lo veas en tu pantalla.

Requiere: pip install pywebview
(usa el motor de Edge WebView2 en Windows, que ya viene instalado de
fábrica en Windows 11 y en la mayoría de instalaciones de Windows 10
con Edge actualizado).

Mantiene EXACTAMENTE los mismos métodos públicos que la ventana
anterior (set_status, set_listened, set_analysis, set_intent,
set_target, set_response, set_on_submit, ready, run) — así que
core/assistant.py y main.py no necesitan ningún cambio para usar
esta versión.
"""

import ctypes
import os
import sys
import threading
import time
import unicodedata

try:
    import webview
except ImportError:
    webview = None


def safe_print(*values, sep=" ", end="\n"):
    try:
        print(*values, sep=sep, end=end)
        return
    except UnicodeEncodeError:
        cleaned = []
        for value in values:
            text = str(value)
            try:
                text.encode(sys.stdout.encoding or "utf-8", errors="strict")
            except UnicodeEncodeError:
                text = unicodedata.normalize("NFKD", text)
                text = text.encode("ascii", "ignore").decode("ascii")
            cleaned.append(text)
        print(*cleaned, sep=sep, end=end)


# Tamaño y posición de la ventanita (esquina inferior derecha, con
# margen). Ajusta ANCHO/ALTO/MARGEN aquí si la quieres más grande o
# en otra esquina.
ANCHO = 200
ALTO = 200
MARGEN_DERECHA = 30
MARGEN_ABAJO = 90  # deja espacio para no tapar la barra de tareas

# Segundos sin actividad después de los cuales la carita se oculta sola.
# Va por su CUENTA aquí (y no depende de core/assistant.py) porque allá el
# vencimiento solo se revisa cuando se oye OTRA frase: si decías "eco",
# te respondía y te quedabas callado, la carita nunca volvía a ocultarse.
AUTO_OCULTAR_SEGUNDOS = 30

# Estilos de ventana de Windows (para mostrarla sin robar el foco y para
# que no tenga botón propio en la barra de tareas).
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
TITULO_VENTANA = "ECO"


_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    html, body {
        margin: 0;
        padding: 0;
        width: 100%;
        height: 100%;
        background: #0b0f14;
        overflow: hidden;
        -webkit-user-select: none;
        user-select: none;
    }

    .escena {
        width: 100%;
        height: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        perspective: 600px;
    }

    /* La cabeza: un "visor" con bordes definidos (no un glow suelto
       sin forma), que gira de lado a lado de verdad en 3D (rotateY
       real, con profundidad gracias al perspective del contenedor
       padre) — como un robot mirando a los lados, no como un anillo
       orbitando un planeta. */
    .cabeza {
        position: relative;
        width: 130px;
        height: 130px;
        border-radius: 30%;
        background: linear-gradient(145deg, #1a2531, #0a0e13);
        border: 1px solid rgba(0, 217, 255, 0.35);
        box-shadow:
            0 0 25px rgba(0, 217, 255, 0.25),
            inset 3px 3px 8px rgba(255, 255, 255, 0.04),
            inset -4px -4px 14px rgba(0, 0, 0, 0.6);
        transform-style: preserve-3d;
        transition: box-shadow 0.3s ease;
        animation: mirar 6s ease-in-out infinite;
    }

    @keyframes mirar {
        0%, 100% { transform: rotateY(-16deg); }
        50%      { transform: rotateY(16deg); }
    }

    .cabeza.escuchando {
        box-shadow:
            0 0 45px rgba(0, 217, 255, 0.6),
            inset 3px 3px 8px rgba(255, 255, 255, 0.06),
            inset -4px -4px 14px rgba(0, 0, 0, 0.6);
    }

    .ojos {
        position: absolute;
        top: 46px;
        left: 0;
        width: 100%;
        display: flex;
        justify-content: center;
        gap: 26px;
    }

    .ojo {
        width: 20px;
        height: 20px;
        border-radius: 50%;
        background: #00d9ff;
        box-shadow: 0 0 12px #00d9ff, 0 0 26px rgba(0, 217, 255, 0.7);
        transition: transform 0.15s ease, background 0.3s ease;
    }

    .ojo.parpadeo {
        transform: scaleY(0.15);
    }

    .boca {
        position: absolute;
        bottom: 36px;
        left: 50%;
        width: 40px;
        height: 5px;
        margin-left: -20px;
        border-radius: 3px;
        background: #00d9ff;
        box-shadow: 0 0 10px rgba(0, 217, 255, 0.8);
        transition: height 0.08s ease, width 0.08s ease;
    }
</style>
</head>
<body>

<div class="escena">
    <div class="cabeza" id="cabeza">
        <div class="ojos">
            <div class="ojo" id="ojoIzq"></div>
            <div class="ojo" id="ojoDer"></div>
        </div>
        <div class="boca" id="boca"></div>
    </div>
</div>

<script>
    var hablando = null;

    function setStatus(modo) {
        var cabeza = document.getElementById("cabeza");
        if (modo === "escuchando") {
            cabeza.classList.add("escuchando");
        } else {
            cabeza.classList.remove("escuchando");
        }
    }

    function startTalking() {
        stopTalking();
        var boca = document.getElementById("boca");
        hablando = setInterval(function () {
            var alto = 3 + Math.random() * 10;
            var ancho = 24 + Math.random() * 20;
            boca.style.height = alto + "px";
            boca.style.width = ancho + "px";
            boca.style.marginLeft = (-ancho / 2) + "px";
        }, 110);
    }

    function stopTalking() {
        if (hablando) {
            clearInterval(hablando);
            hablando = null;
        }
        var boca = document.getElementById("boca");
        boca.style.height = "4px";
        boca.style.width = "34px";
        boca.style.marginLeft = "-17px";
    }

    function flashHeard() {
        var izq = document.getElementById("ojoIzq");
        var der = document.getElementById("ojoDer");
        izq.classList.add("parpadeo");
        der.classList.add("parpadeo");
        setTimeout(function () {
            izq.classList.remove("parpadeo");
            der.classList.remove("parpadeo");
        }, 150);
    }

    function setTooltip(texto) {
        document.body.title = texto;
    }
</script>

</body>
</html>
"""


class EcoWindow:

    def __init__(self):

        self._pywebview_window = None
        self._ready = False
        self._on_submit = None
        self._visible = False
        self._hide_timer = None

        # Últimos valores recibidos, guardados aunque no haya un
        # lugar visible para mostrarlos todos — quedan disponibles
        # como tooltip (pasa el mouse por encima de la carita) para
        # no perder del todo la info de depuración que sí mostraba
        # el panel grande anterior.
        self._ultimo_intent = "—"
        self._ultimo_target = "—"

        if webview is None:
            safe_print(
                "Info: falta 'pywebview' (pip install pywebview) - Eco "
                "va a seguir funcionando sin la carita en pantalla, "
                "solo por consola y voz."
            )

    # =========================================================
    # POSICIÓN EN LA ESQUINA
    # =========================================================

    @property
    def _user32(self):
        if os.name != "nt" or not hasattr(ctypes, "windll"):
            return None
        return getattr(ctypes.windll, "user32", None)

    def _posicion_esquina(self):
        user32 = self._user32
        if user32 is not None:
            try:
                ancho_pantalla = user32.GetSystemMetrics(0)
                alto_pantalla = user32.GetSystemMetrics(1)
            except Exception:
                ancho_pantalla, alto_pantalla = 1920, 1080
        else:
            ancho_pantalla, alto_pantalla = 1920, 1080

        x = ancho_pantalla - ANCHO - MARGEN_DERECHA
        y = alto_pantalla - ALTO - MARGEN_ABAJO
        return max(x, 0), max(y, 0)

    def _on_loaded(self):
        self._ready = True
        # No basta con hidden=True al crearla: algunas versiones de
        # pywebview lo ignoran y la carita quedaba visible desde el
        # arranque. Se oculta explícitamente en cuanto carga.
        self._quitar_de_barra_de_tareas()
        self.hide()

    def _run_js(self, codigo):
        if not self._ready or not self._pywebview_window:
            return
        try:
            self._pywebview_window.evaluate_js(codigo)
        except Exception:
            pass

    # =========================================================
    # ENTRADA DE TEXTO
    #
    # Esta ventanita no tiene un cuadro de texto (es solo la carita).
    # Para escribir un comando en vez de decirlo, sigue funcionando
    # escribir directamente en la consola donde corre Eco — eso
    # no cambió. set_on_submit() se conserva por compatibilidad, por
    # si más adelante se conecta a algo (ej. un atajo de teclado).
    # =========================================================

    def set_on_submit(self, callback):
        self._on_submit = callback

    # =========================================================
    # ESTADO / EVENTOS -> ANIMACIÓN DE LA CARITA
    # =========================================================

    def set_status(self, text):
        texto = str(text or "").upper()
        if "ESCUCH" in texto:
            self._run_js("setStatus('escuchando')")
        else:
            self._run_js("setStatus('idle')")

    def set_listened(self, text):
        self._run_js("flashHeard()")
        self._reiniciar_reloj_si_visible()

    def set_analysis(self, text):
        pass

    def set_intent(self, text):
        self._ultimo_intent = str(text or "—")
        self._actualizar_tooltip()

    def set_target(self, text):
        self._ultimo_target = str(text or "—")
        self._actualizar_tooltip()

    def _actualizar_tooltip(self):
        tooltip = f"Intención: {self._ultimo_intent}\\nObjetivo: {self._ultimo_target}"
        self._run_js(f"setTooltip({tooltip!r})")

    def set_response(self, text):
        # La sincronización REAL de la boca con la voz la dispara
        # Speaker (ver voice/speaker.py: start_talking/stop_talking),
        # no esto — aquí no se anima nada para no pisarse con eso.
        pass

    # =========================================================
    # HABLAR (llamado por Speaker, sincronizado con el audio real)
    # =========================================================

    def start_talking(self):
        self._run_js("startTalking()")

    def stop_talking(self):
        self._run_js("stopTalking()")
        self._reiniciar_reloj_si_visible()

    # =========================================================
    # MOSTRAR / OCULTAR
    #
    # Arranca oculta y solo se ve mientras le estás hablando: show() la
    # muestra (core/assistant.py lo llama al oír "eco") y se oculta SOLA
    # AUTO_OCULTAR_SEGUNDOS después de la última actividad (cada vez que
    # se oye algo o termina de hablar, el reloj se reinicia).
    # =========================================================

    def _hwnd(self):
        user32 = self._user32
        if user32 is None:
            return 0
        try:
            return user32.FindWindowW(None, TITULO_VENTANA)
        except Exception:
            return 0

    def _quitar_de_barra_de_tareas(self):
        """
        Se hace con la ventana oculta: le quita el botón propio en la
        barra de tareas (estilo "ventana de herramientas"), para que al
        aparecer no deje un icono ahí.
        """
        user32 = self._user32
        if user32 is None:
            return
        try:
            hwnd = self._hwnd()
            if not hwnd:
                return
            estilo = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            estilo = (estilo & ~WS_EX_APPWINDOW) | WS_EX_TOOLWINDOW
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, estilo)
        except Exception:
            pass

    def _cancelar_ocultar(self):
        if self._hide_timer:
            self._hide_timer.cancel()
            self._hide_timer = None

    def _programar_ocultar(self):
        self._cancelar_ocultar()
        self._hide_timer = threading.Timer(AUTO_OCULTAR_SEGUNDOS, self.hide)
        self._hide_timer.daemon = True
        self._hide_timer.start()

    def _reiniciar_reloj_si_visible(self):
        if self._visible:
            self._programar_ocultar()

    def show(self):
        if not self._pywebview_window:
            return

        self._visible = True

        # SW_SHOWNOACTIVATE: aparece SIN quitarle el foco a lo que estés
        # usando (ej. un juego). pywebview.show() sí lo roba.
        mostrada = False
        user32 = self._user32
        try:
            hwnd = self._hwnd()
            if hwnd and user32 is not None:
                user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
                mostrada = True
        except Exception:
            pass

        if not mostrada:
            try:
                self._pywebview_window.show()
            except Exception:
                pass

        self._programar_ocultar()

    def hide(self):
        self._visible = False
        self._cancelar_ocultar()

        if not self._pywebview_window:
            return

        try:
            self._pywebview_window.hide()
        except Exception:
            pass

        # Respaldo directo: si pywebview no la ocultó, se oculta igual.
        user32 = self._user32
        try:
            hwnd = self._hwnd()
            if hwnd and user32 is not None:
                user32.ShowWindow(hwnd, SW_HIDE)
        except Exception:
            pass

    # =========================================================
    # LISTA
    # =========================================================

    def ready(self):
        self.set_status("● ECO LISTA")

    # =========================================================
    # EJECUTAR INTERFAZ
    # =========================================================

    def run(self):

        if webview is None:
            # Sin pywebview no hay ventana que correr, pero el hilo
            # principal tiene que quedarse vivo (ahí es donde vive el
            # hilo de Eco, que es daemon=True en main.py).
            threading.Event().wait()
            return

        x, y = self._posicion_esquina()

        self._pywebview_window = webview.create_window(
            "ECO",
            html=_HTML,
            width=ANCHO,
            height=ALTO,
            x=x,
            y=y,
            frameless=True,
            easy_drag=True,
            on_top=True,
            resizable=False,
            transparent=True,
            hidden=True,
        )

        try:
            self._pywebview_window.events.loaded += self._on_loaded
        except Exception:
            # Si esta versión de pywebview no tiene .events.loaded,
            # se asume que ya cargó después de un momento — más
            # simple que fallar del todo.
            threading.Timer(1.5, self._on_loaded).start()

        webview.start()


if __name__ == "__main__":

    app = EcoWindow()

    app.ready()
    app.run()