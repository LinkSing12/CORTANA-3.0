"""
ECO - Ícono de bandeja del sistema.

Sin esto, la única forma de "volver a ver" la consola (para escribir
un comando en vez de decirlo) sería dejarla visible en la barra de
tareas todo el tiempo. Con esto, la consola se puede ocultar por
completo y queda un ícono en la bandeja (la flechita de "iconos
ocultos" junto al reloj) con un menú para mostrarla, ocultarla, o
cerrar Eco del todo.

Requiere: pip install pystray Pillow

Si falta cualquiera de los dos paquetes, Eco sigue funcionando
igual (consola + voz), solo sin el ícono de bandeja — no hay forma
de volver a mostrar la consola oculta en ese caso, así que main.py
decide si oculta la consola según si esto pudo arrancar o no.
"""

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    pystray = None


def _icono_imagen():
    """
    Dibuja un ícono simple (círculo cian sobre fondo oscuro) a mano,
    para no depender de ningún archivo .ico externo que haya que
    distribuir aparte.
    """
    size = 64
    imagen = Image.new("RGBA", (size, size), (11, 15, 20, 255))
    dibujo = ImageDraw.Draw(imagen)
    dibujo.ellipse((10, 10, size - 10, size - 10), fill=(0, 217, 255, 255))
    return imagen


class TrayIcon:

    def __init__(self, on_toggle_console=None, on_exit=None):
        """
        on_toggle_console: función que recibe True (mostrar la
        consola) o False (ocultarla).
        on_exit: función sin argumentos, llamada antes de cerrar todo.
        """
        self._on_toggle_console = on_toggle_console
        self._on_exit = on_exit
        self._icon = None

    def disponible(self):
        return pystray is not None

    def _mostrar_consola(self, icon, item):
        if self._on_toggle_console:
            self._on_toggle_console(True)

    def _ocultar_consola(self, icon, item):
        if self._on_toggle_console:
            self._on_toggle_console(False)

    def _salir(self, icon, item):
        if self._on_exit:
            try:
                self._on_exit()
            except Exception:
                pass
        icon.stop()

    def run(self):
        """
        Bloquea este hilo mientras el ícono esté activo — por eso
        main.py lo corre en su propio hilo, no en el principal (el
        principal lo necesita la ventana de la carita).
        """
        if not self.disponible():
            print(
                "ℹ️ Falta 'pystray' y/o 'Pillow' (pip install pystray "
                "Pillow) — Eco sigue funcionando, solo sin ícono "
                "en la bandeja del sistema."
            )
            return

        menu = pystray.Menu(
            pystray.MenuItem("Mostrar consola", self._mostrar_consola),
            pystray.MenuItem("Ocultar consola", self._ocultar_consola),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir", self._salir),
        )

        self._icon = pystray.Icon("eco", _icono_imagen(), "Eco", menu)
        self._icon.run()

    def detener(self):
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass
