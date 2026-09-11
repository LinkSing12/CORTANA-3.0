import os
import re
import time
import subprocess
import urllib.parse
import requests

from core.web_search import WebSearch


class Router:
    def __init__(self, windows, media):
        self.windows = windows
        self.media = media
        self.chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        self.chrome_user_data = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
        self.chrome_profile = "Default"
        self.web_search = WebSearch()

    def execute(self, result, original_command=""):
        if not isinstance(result, dict):
            return "No entendí la orden."
        intent = str(result.get("intent", "UNKNOWN")).upper().strip()
        target = str(result.get("target", "")).strip()
        params = result.get("parameters", {}) or {}
        try:
            confidence = float(result.get("confidence", 0))
        except Exception:
            confidence = 0.0

        command = str(original_command or "").strip().lower()
        direct = self.detect_direct_command(command)
        if direct:
            intent = direct
            target = "pc"
            confidence = 1.0

        print(f"\nROUTER: {intent}\nTARGET: {target}\nCONFIDENCE: {confidence}")
        if confidence < 0.50 and intent not in {"UNINSTALL_PROGRAM", "DELETE_FOLDER"}:
            return "No estoy suficientemente segura de lo que quieres."

        if intent == "OPEN_PROGRAM": return self.windows.open_program(target)
        if intent == "INSTALL_PROGRAM": return self.windows.install_program(target)
        if intent == "CLOSE_PROGRAM": return self.windows.close_program(target)
        if intent == "UNINSTALL_PROGRAM":
            confirmed = bool(params.get("confirmed", False)) or bool(re.search(r"\b(confirmo|confirmado|si|sí|hazlo|adelante)\b", command))
            return self.windows.uninstall_program(target, confirmed=confirmed)
        if intent in {"LIST_PROGRAMS", "LIST_RUNNING_PROGRAMS"}:
            return self._list_running()
        if intent == "CHECK_PROGRAM": return self._check_program(target)
        if intent == "PROGRAM_INFO": return self._program_info(target)
        if intent == "REFRESH_PROGRAMS": return self.windows.refresh_programs()
        if intent == "OPEN_FILE": return self.windows.open_file(target)
        if intent == "OPEN_FOLDER": return self._open_folder(target)
        if intent == "CREATE_FOLDER": return self.windows.create_folder(target)
        if intent == "DELETE_FOLDER":
            confirmed = bool(params.get("confirmed", False)) or bool(re.search(r"\b(confirmo|confirmado|si|sí|hazlo|adelante)\b", command))
            return self.windows.delete_folder(target, confirmed=confirmed)
        if intent == "OPEN_URL": return self.windows.open_url(target)
        if intent in {"SEARCH_WEB", "SEARCH_GOOGLE", "WEB_SEARCH"}: return self.answer_web_search(target)
        if intent in {"SEARCH_YOUTUBE", "PLAY_YOUTUBE", "PLAY_MEDIA"}: return self.search_youtube(target)
        if intent in {"VOLUME_MUTE", "MUTE"}: return self.media.volume_mute()
        if intent in {"VOLUME_UNMUTE", "UNMUTE"}: return self._unmute()
        if intent == "VOLUME_UP": return self.media.volume_up()
        if intent == "VOLUME_DOWN": return self.media.volume_down()
        if intent in {"MEDIA_PLAY", "RESUME_MEDIA"}: return self.media.play()
        if intent in {"MEDIA_PAUSE", "PAUSE_MEDIA", "MEDIA_STOP", "STOP_MEDIA"}: return self.media.pause()
        if intent == "MEDIA_NEXT": return self.media.next()
        if intent == "MEDIA_PREVIOUS": return self.media.previous()
        if intent == "SHUTDOWN_PC": return self.windows.shutdown_pc()
        if intent == "RESTART_PC": return self.windows.restart_pc()
        if intent == "SLEEP_PC": return self.windows.sleep_pc()
        if intent == "LOCK_PC": return self.windows.lock_pc()
        if intent == "LOGOUT_PC": return self.windows.logout_pc()
        if intent == "CANCEL_SHUTDOWN": return self.windows.cancel_shutdown()
        if intent == "SYSTEM_INFO": return self.windows.system_info()
        if intent == "CPU_INFO": return self.windows.cpu_info()
        if intent == "MEMORY_INFO": return self.windows.memory_info()
        if intent == "DISK_INFO": return self.windows.disk_info()
        if intent == "BATTERY_INFO": return self.windows.battery_info()
        return "Todavía no sé hacer eso."

    def detect_direct_command(self, command):
        c = re.sub(r"[¿?¡!.,]+", "", str(command or "").lower()).strip()
        if re.search(r"\b(apaga|apagar)\b.*\b(pc|computadora|ordenador|equipo|windows)\b", c): return "SHUTDOWN_PC"
        if re.search(r"\b(reinicia|reiniciar|reboot)\b", c) and re.search(r"\b(pc|computadora|ordenador|equipo|windows)\b", c): return "RESTART_PC"
        if re.search(r"\b(suspende|suspender|hiberna|hibernar)\b", c): return "SLEEP_PC"
        if re.search(r"\b(bloquea|bloquear)\b.*\b(pc|pantalla|sesion|sesión)\b", c): return "LOCK_PC"
        if re.search(r"\b(cierra|cerrar)\b.*\b(sesion|sesión)\b", c): return "LOGOUT_PC"
        if re.search(r"\b(cancela|cancelar)\b.*\b(apagado|reinicio|shutdown)\b", c): return "CANCEL_SHUTDOWN"
        return None

    def _list_running(self):
        try:
            from core.process_manager import obtener_programas_en_ejecucion
            items = obtener_programas_en_ejecucion() or []
            return "PROGRAMAS EN EJECUCIÓN:\n" + "\n".join(f"- {x}" for x in items[:60]) if items else "No encontré programas ejecutándose."
        except Exception as error:
            print("ERROR LISTANDO:", error)
            return "No pude obtener los programas en ejecución."

    def _check_program(self, target):
        try:
            from core.process_manager import buscar_proceso
            found = buscar_proceso(target) or []
            if not found: return f"No. {target} no está ejecutándose."
            return f"Sí. {found[0]['name']} está ejecutándose. PID {found[0]['pid']}."
        except Exception:
            return f"No pude comprobar {target}."

    def _program_info(self, target):
        try:
            from core.process_manager import informacion_proceso
            info = informacion_proceso(target)
            if not info: return f"No encontré {target} ejecutándose."
            return (f"Programa: {info.get('name', target)}\nPID: {info.get('pid', '')}\n"
                    f"Instancias: {info.get('instances', 1)}\nCPU: {info.get('cpu', 0)}%\n"
                    f"Memoria: {info.get('memory', 0)} MB\nRuta: {info.get('path', 'No disponible')}\n"
                    f"Estado: {info.get('status', 'Desconocido')}")
        except Exception:
            return f"No pude obtener información de {target}."

    def _open_folder(self, target):
        path = os.path.expandvars(os.path.expanduser(str(target).strip()))
        if not os.path.isdir(path): return f"No encontré la carpeta {path}."
        try:
            os.startfile(path)
            return f"Abriendo {path}."
        except Exception: return f"No pude abrir {path}."

    def _start_chrome(self, url):
        if not os.path.isfile(self.chrome_path): return False
        args = [self.chrome_path]
        if os.path.isdir(self.chrome_user_data):
            args += [f"--user-data-dir={self.chrome_user_data}", f"--profile-directory={self.chrome_profile}"]
        args.append(url)
        try:
            subprocess.Popen(args, close_fds=True)
            return True
        except Exception as error:
            print("ERROR CHROME:", error)
            return False

    def search_google(self, query):
        query = str(query).strip()
        if not query: return "¿Qué quieres que busque en Google?"
        url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)
        return "Buscando en Google." if self._start_chrome(url) else self.windows.open_url(url)

    # =====================================================
    # BÚSQUEDA REAL EN INTERNET (DuckDuckGo vía ddgs)
    # =====================================================
    def answer_web_search(self, query):
        query = str(query).strip()
        if not query:
            return "¿Qué quieres que busque en internet?"

        try:
            results = self.web_search.search(query)
        except Exception as error:
            print("ERROR BUSCANDO EN INTERNET:", error)
            results = []

        if not results:
            # Respaldo: si no hay resultados, al menos abre la búsqueda en Chrome.
            return self.search_google(query)

        best = results[0]
        title = str(best.get("title", "")).strip()
        body = str(best.get("body", "")).strip()

        answer = body if body else title
        if not answer:
            return self.search_google(query)

        # Recortar para que la respuesta hablada no sea eterna.
        if len(answer) > 400:
            answer = answer[:400].rsplit(" ", 1)[0].rstrip(",.;: ") + "..."

        if title and title.lower() not in answer.lower():
            return f"Según {title}: {answer}"
        return answer

    def get_first_youtube_video(self, query):
        try:
            encoded = urllib.parse.quote_plus(query)
            search_url = "https://www.youtube.com/results?search_query=" + encoded
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"
                )
            }
            t_req = time.time()
            response = requests.get(search_url, headers=headers, timeout=6)
            print(f"⏱ PETICIÓN HTTP A YOUTUBE: {time.time() - t_req:.2f}s")
            if response.status_code != 200:
                return None
            matches = re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', response.text)
            for video_id in matches:
                return "https://www.youtube.com/watch?v=" + video_id + "&autoplay=1"
            return None
        except Exception as error:
            print("ERROR BUSCANDO VIDEO YOUTUBE:", error)
            return None

    def search_youtube(self, query):
        query = str(query).strip()
        if not query: return "¿Qué quieres que busque en YouTube?"

        print("YOUTUBE:", query)
        t_total = time.time()
        video_url = self.get_first_youtube_video(query)
        print(f"⏱ search_youtube() TOTAL: {time.time() - t_total:.2f}s")

        if video_url:
            print("VIDEO ENCONTRADO:", video_url)
            if self._start_chrome(video_url):
                return f"Reproduciendo {query} en YouTube."
            return self.windows.open_url(video_url)

        # Respaldo: si no se encontró un video, abrir solo los resultados.
        search_url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query)
        return "Buscando en YouTube." if self._start_chrome(search_url) else self.windows.open_url(search_url)

    def _unmute(self):
        try:
            import ctypes
            ctypes.windll.user32.keybd_event(0xAD, 0, 0, 0)
            ctypes.windll.user32.keybd_event(0xAD, 0, 2, 0)
            return "Sonido activado."
        except Exception:
            return "No pude activar el sonido."