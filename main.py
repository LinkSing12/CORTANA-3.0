import ctypes
import os
import threading
import time

from core.assistant import Eco
from interface.window import EcoWindow
from interface.tray_icon import TrayIcon


SW_HIDE = 0
SW_SHOW = 5


# Se guarda el "mutex" mientras el proceso viva: es lo que marca "ya hay un
# Eco corriendo". Windows lo libera solo al cerrarse el proceso.
_MUTEX = None


def _ya_hay_otra_instancia():
    """
    Evita que corran DOS Ecos a la vez (los dos escuchando el micrófono,
    dos caritas, dos íconos de bandeja). Pasa fácil con el inicio
    automático: si ya hay uno corriendo oculto y abres otro a mano, o si
    quedan dos mecanismos de arranque. Si no se puede comprobar, se deja
    arrancar (mejor dos Ecos que ninguno).
    """
    global _MUTEX
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CreateMutexW.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p
        ]
        _MUTEX = kernel32.CreateMutexW(
            None, False, "Local\\EcoAsistenteUnaSolaInstancia"
        )
        return ctypes.get_last_error() == 183  # ERROR_ALREADY_EXISTS
    except Exception:
        return False


def _consola_visible(mostrar):
    """
    Oculta o muestra la ventana de consola de VERDAD (no solo
    minimizada) — por eso no aparece en la barra de tareas mientras
    está oculta. Si no se puede (ej. no hay consola real, como al
    correr desde algunos IDEs), simplemente no hace nada.
    """
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, SW_SHOW if mostrar else SW_HIDE)
    except Exception:
        pass


def _salir():
    # os._exit en vez de sys.exit: hay varios hilos en segundo plano
    # (voz, Eco, la ventana) que no van a terminar solos a tiempo
    # con un cierre "educado" — esto corta todo de una.
    os._exit(0)


def main():

    if _ya_hay_otra_instancia():
        print(
            "Eco ya está corriendo (búscala en el ícono de la bandeja del "
            "sistema, junto al reloj). Esta segunda copia se cierra."
        )
        time.sleep(5)
        return

    window = EcoWindow()

    eco = Eco()
    eco.set_interface(window)

    # Lo que escribas en la ventana se procesa exactamente igual
    # que un comando por voz o por consola (mismo respond()).
    window.set_on_submit(eco.respond)

    # Eco (consola + hilo de voz) corre en su propio hilo,
    # porque Tkinter (la ventana) solo puede correr su mainloop
    # en el hilo principal.
    eco_thread = threading.Thread(
        target=eco.start,
        daemon=True
    )
    eco_thread.start()

    # =====================================================
    # ÍCONO DE BANDEJA (oculta la consola de la barra de tareas,
    # deja un ícono para volver a mostrarla cuando haga falta)
    # =====================================================

    tray = TrayIcon(
        on_toggle_console=_consola_visible,
        on_exit=_salir,
    )

    if tray.disponible():
        tray_thread = threading.Thread(
            target=tray.run,
            daemon=True
        )
        tray_thread.start()

        # Solo se oculta la consola si de verdad queda el ícono de
        # bandeja para volver a mostrarla — si faltan pystray/Pillow,
        # se deja la consola visible para no perder el control.
        _consola_visible(False)

    window.ready()
    window.run()


if __name__ == "__main__":
    main()