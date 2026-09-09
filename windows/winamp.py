import ctypes
import ctypes.wintypes
import os
import time
import subprocess


# =============================================================
# API DE CONTROL DE WINAMP (IPC por mensajes de Windows)
#
# Winamp expone una ventana oculta de clase "Winamp v1.x" que
# entiende mensajes WM_USER / WM_COMMAND / WM_COPYDATA para
# controlarlo desde otros programas. Esta API es pública y
# estable desde hace más de 20 años (Winamp 2.x en adelante).
#
# Referencias de los códigos usados:
#   IPC_PLAYFILE         = 100  (via WM_COPYDATA: abre y reproduce un archivo)
#   IPC_SETPLAYLISTPOS   = 121  (via WM_USER: salta a una posición de la lista)
#   IPC_GETLISTLENGTH    = 124  (via WM_USER: cuántas canciones hay en la lista)
#   WINAMP_BUTTON2_PLAY  = 40045 (via WM_COMMAND: simula el botón Play)
# =============================================================

WM_COMMAND = 0x0111
WM_USER = 0x0400
WM_COPYDATA = 0x004A

IPC_PLAYFILE = 100
IPC_SETPLAYLISTPOS = 121
IPC_GETLISTLENGTH = 124

WINAMP_BUTTON2_PREV = 40044
WINAMP_BUTTON2_PLAY = 40045
WINAMP_BUTTON2_PAUSE = 40046
WINAMP_BUTTON2_STOP = 40047
WINAMP_BUTTON2_NEXT = 40048


class COPYDATASTRUCT(ctypes.Structure):
    _fields_ = [
        ("dwData", ctypes.wintypes.WPARAM),
        ("cbData", ctypes.wintypes.DWORD),
        ("lpData", ctypes.c_void_p),
    ]


class WinampController:

    def __init__(self, music_folders=None):

        # Carpetas donde Cortana busca el archivo cuando le pides
        # una canción por nombre. Ajusta esto a donde tengas tu
        # música real si no está en la carpeta por defecto.
        self.music_folders = music_folders or [
            os.path.expandvars(r"%USERPROFILE%\Music"),
        ]

        self.audio_extensions = (
            ".mp3", ".wav", ".flac", ".ogg", ".m4a", ".wma"
        )

    # ------------------------------------------------------------------
    # VENTANA DE WINAMP
    # ------------------------------------------------------------------
    def find_window(self):
        try:
            return ctypes.windll.user32.FindWindowW("Winamp v1.x", None)
        except Exception as error:
            print("ERROR BUSCANDO VENTANA DE WINAMP:", error)
            return 0

    def is_running(self):
        return self.find_window() != 0

    def _find_winamp_exe(self):
        candidates = [
            os.path.expandvars(r"%ProgramFiles(x86)%\Winamp\winamp.exe"),
            os.path.expandvars(r"%ProgramFiles%\Winamp\winamp.exe"),
        ]
        for path in candidates:
            if os.path.isfile(path):
                return path
        return None

    def ensure_open(self, winamp_path=None, wait_seconds=10):
        if self.is_running():
            return True

        path = winamp_path or self._find_winamp_exe()
        if not path:
            print("ERROR: no encontré winamp.exe en las rutas usuales.")
            return False

        try:
            subprocess.Popen([path], close_fds=True)
        except Exception as error:
            print("ERROR ABRIENDO WINAMP:", error)
            return False

        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            if self.is_running():
                return True
            time.sleep(0.3)

        return self.is_running()

    # ------------------------------------------------------------------
    # REPRODUCIR UN ARCHIVO DIRECTO (por ruta)
    # ------------------------------------------------------------------
    def play_file(self, path):
        hwnd = self.find_window()
        if not hwnd:
            return False

        try:
            # Winamp espera la ruta como cadena ANSI (codepage del
            # sistema), no UTF-16, para este mensaje en particular.
            encoded = str(path).encode("mbcs", errors="replace")
        except LookupError:
            encoded = str(path).encode("latin-1", errors="replace")

        buffer = ctypes.create_string_buffer(encoded)

        cds = COPYDATASTRUCT()
        cds.dwData = IPC_PLAYFILE
        cds.cbData = len(encoded) + 1
        cds.lpData = ctypes.cast(buffer, ctypes.c_void_p)

        try:
            ctypes.windll.user32.SendMessageW(
                hwnd, WM_COPYDATA, 0, ctypes.byref(cds)
            )
            return True
        except Exception as error:
            print("ERROR ENVIANDO ARCHIVO A WINAMP:", error)
            return False

    # ------------------------------------------------------------------
    # REPRODUCIR POR POSICIÓN EN LA LISTA (número de canción)
    # ------------------------------------------------------------------
    def get_playlist_length(self):
        hwnd = self.find_window()
        if not hwnd:
            return 0
        try:
            return ctypes.windll.user32.SendMessageW(
                hwnd, WM_USER, 0, IPC_GETLISTLENGTH
            )
        except Exception as error:
            print("ERROR OBTENIENDO LARGO DE LISTA:", error)
            return 0

    def play_position(self, index):
        hwnd = self.find_window()
        if not hwnd:
            return False
        try:
            ctypes.windll.user32.SendMessageW(
                hwnd, WM_USER, index, IPC_SETPLAYLISTPOS
            )
            ctypes.windll.user32.SendMessageW(
                hwnd, WM_COMMAND, WINAMP_BUTTON2_PLAY, 0
            )
            return True
        except Exception as error:
            print("ERROR SALTANDO A POSICIÓN:", error)
            return False

    # ------------------------------------------------------------------
    # CONTROLES DE REPRODUCCIÓN (botones remotos de Winamp)
    # Se usan directamente contra Winamp cuando está abierto, en vez
    # de depender de las teclas multimedia globales de Windows, que
    # no siempre llegan de forma confiable a Winamp según su versión
    # y configuración.
    # ------------------------------------------------------------------
    def _send_button(self, button_id):
        hwnd = self.find_window()
        if not hwnd:
            return False
        try:
            ctypes.windll.user32.SendMessageW(
                hwnd, WM_COMMAND, button_id, 0
            )
            return True
        except Exception as error:
            print("ERROR ENVIANDO BOTÓN A WINAMP:", error)
            return False

    def resume(self):
        return self._send_button(WINAMP_BUTTON2_PLAY)

    def pause(self):
        return self._send_button(WINAMP_BUTTON2_PAUSE)

    def stop(self):
        return self._send_button(WINAMP_BUTTON2_STOP)

    def next_track(self):
        return self._send_button(WINAMP_BUTTON2_NEXT)

    def previous_track(self):
        return self._send_button(WINAMP_BUTTON2_PREV)

    # ------------------------------------------------------------------
    # BUSCAR UNA CANCIÓN POR NOMBRE EN LAS CARPETAS CONFIGURADAS
    # ------------------------------------------------------------------
    def find_song_file(self, name):
        name_normalized = str(name).strip().lower()
        if not name_normalized:
            return None

        for folder in self.music_folders:
            if not os.path.isdir(folder):
                continue
            for root, _, files in os.walk(folder):
                for filename in files:
                    if not filename.lower().endswith(self.audio_extensions):
                        continue
                    base = os.path.splitext(filename)[0].lower()
                    if name_normalized in base:
                        return os.path.join(root, filename)
        return None

    # ------------------------------------------------------------------
    # ÓRDENES DE ALTO NIVEL (lo que usa Cortana)
    # ------------------------------------------------------------------
    def play_by_name(self, name, winamp_path=None):
        if not self.ensure_open(winamp_path):
            return "No pude abrir Winamp."

        song_path = self.find_song_file(name)
        if not song_path:
            return (
                f"No encontré ninguna canción parecida a '{name}' "
                "en tu carpeta de música."
            )

        if self.play_file(song_path):
            return f"Reproduciendo {os.path.basename(song_path)} en Winamp."

        return "Encontré la canción, pero no pude comunicarme con Winamp."

    def play_by_number(self, number, winamp_path=None):
        if not self.ensure_open(winamp_path):
            return "No pude abrir Winamp."

        try:
            number = int(number)
        except (TypeError, ValueError):
            return "Necesito un número de canción válido."

        length = self.get_playlist_length()

        if length and not (1 <= number <= length):
            return (
                f"Tu lista de reproducción en Winamp solo tiene "
                f"{length} canciones."
            )

        index = number - 1  # el usuario cuenta desde 1

        if self.play_position(index):
            return f"Reproduciendo la canción número {number} en Winamp."

        return "No pude comunicarme con Winamp."
