import os
import re
import json
import time
import subprocess
import webbrowser
import difflib

try:
    import psutil
except ImportError:
    psutil = None

try:
    import winreg
except ImportError:
    winreg = None


class WindowsController:
    """Controlador general de Windows para CORTANA 4.0.

    Permite abrir/cerrar aplicaciones y juegos, resolver alias de voz y,
    cuando un juego usa un cliente, esperar y pulsar Jugar/Play/Launch/Start.
    """

    def __init__(self):
        self.cache_dir = "data"
        self.cache_file = os.path.join(self.cache_dir, "installed_programs.json")
        os.makedirs(self.cache_dir, exist_ok=True)

        self.programs = {}
        self.games = {}
        self.apps = {}

        # Evita que un "abre X" fallido dispare un reescaneo
        # completo del registro y las carpetas de accesos directos
        # cada vez (eso era lo que hacía lentos los "abrir X" que
        # no coincidían con nada). Solo se vuelve a escanear solo
        # si ya pasó este tiempo desde el último escaneo, o si el
        # usuario pide explícitamente "actualiza los programas".
        self._last_scan_time = 0
        self._rescan_cooldown_seconds = 300

        self.aliases = {
            "lol": "league of legends",
            "l o l": "league of legends",
            "lo l": "league of legends",
            "el o el": "league of legends",
            "ele o ele": "league of legends",
            "ele o el": "league of legends",
            "l o el": "league of legends",
            "league": "league of legends",
            "league of legend": "league of legends",
            "league of legends": "league of legends",
            "lig of legen": "league of legends",
            "ligue of legends": "league of legends",
            "age of legend": "league of legends",
            "age of legends": "league of legends",
            "riot": "riot client",
            "riot client": "riot client",
            "chrome": "google chrome",
            "google chrome": "google chrome",
            "battlenet": "battle.net",
            "battle net": "battle.net",
            "bloc": "bloc de notas",
            "blog": "bloc de notas",
            "notepad": "bloc de notas",
            "calculator": "calculadora",
        }

        # Juego -> cliente que debe abrirse antes de buscar el botón Jugar.
        self.game_clients = {
            "league of legends": "riot client",
            "valorant": "riot client",
            "valorant game": "riot client",
            "overwatch": "battle.net",
            "diablo": "battle.net",
            "diablo iv": "battle.net",
            "world of warcraft": "battle.net",
        }

        self.client_processes = {
            "riot client": [
                "RiotClientServices.exe",
                "RiotClientUx.exe",
                "RiotClientUxRender.exe",
            ],
            "battle.net": ["Battle.net.exe", "Agent.exe"],
            "steam": ["steam.exe"],
            "epic games launcher": ["EpicGamesLauncher.exe"],
            "ea app": ["EADesktop.exe", "EALauncher.exe"],
            "ubisoft connect": ["upc.exe", "UbisoftConnect.exe"],
        }

        self.scan_programs()

    # ------------------------------------------------------------------
    # Normalización
    # ------------------------------------------------------------------
    def normalize_text(self, text):
        if not text:
            return ""
        text = str(text).lower().strip()
        table = str.maketrans("áéíóúüñ", "aeiouun")
        text = text.translate(table)
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def normalize_process_name(self, name):
        return re.sub(r"[^a-z0-9]", "", self.normalize_text(name))

    def clean_target(self, target):
        target = self.normalize_text(target)
        prefixes = (
            "por favor ", "porfavor ", "me puedes ", "puedes ",
            "quiero ", "quisiera ", "abre ", "abrir ",
            "ejecuta ", "ejecutar ", "inicia ", "iniciar ",
        )
        for prefix in prefixes:
            if target.startswith(prefix):
                target = target[len(prefix):].strip()
                break
        for article in ("el ", "la ", "los ", "las ", "un ", "una "):
            if target.startswith(article):
                target = target[len(article):].strip()
                break
        return self.aliases.get(target, target)

    # ------------------------------------------------------------------
    # Programas instalados
    # ------------------------------------------------------------------
    def is_game(self, name):
        name = self.normalize_text(name)
        keywords = (
            "league of legends", "valorant", "roblox", "minecraft",
            "fortnite", "steam", "epic games", "battle net", "riot client",
            "halo", "tekken", "dragon ball", "sparking", "forza", "gta",
            "grand theft auto", "call of duty", "warzone", "apex legends",
            "overwatch", "counter strike", "cs2", "elden ring", "dark souls",
            "fall guys", "among us", "rocket league", "pubg", "destiny",
            "cyberpunk", "red dead", "assassins creed", "resident evil",
            "need for speed", "terraria", "ubisoft connect",
        )
        return any(k in name for k in keywords)

    def scan_programs(self):
        found = {}
        paths = [
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs"),
        ]

        for base in paths:
            if not os.path.isdir(base):
                continue
            for root, _, files in os.walk(base):
                for filename in files:
                    if not filename.lower().endswith(".lnk"):
                        continue
                    name = os.path.splitext(filename)[0]
                    key = self.normalize_text(name)
                    if key:
                        found[key] = {
                            "name": name,
                            "path": os.path.join(root, filename),
                            "type": "game" if self.is_game(name) else "app",
                        }

        if winreg:
            locations = [
                (winreg.HKEY_LOCAL_MACHINE,
                 r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_LOCAL_MACHINE,
                 r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_CURRENT_USER,
                 r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            ]
            for hive, path in locations:
                try:
                    with winreg.OpenKey(hive, path) as key:
                        for i in range(winreg.QueryInfoKey(key)[0]):
                            try:
                                subname = winreg.EnumKey(key, i)
                                with winreg.OpenKey(key, subname) as sub:
                                    name = winreg.QueryValueEx(sub, "DisplayName")[0]
                                    if not name:
                                        continue
                                    clean = self.normalize_text(name)
                                    if clean in found:
                                        continue
                                    def value(field):
                                        try:
                                            return winreg.QueryValueEx(sub, field)[0] or ""
                                        except Exception:
                                            return ""
                                    found[clean] = {
                                        "name": name,
                                        "path": value("InstallLocation"),
                                        "display_icon": value("DisplayIcon"),
                                        "uninstall": value("UninstallString"),
                                        "type": "game" if self.is_game(name) else "app",
                                    }
                            except Exception:
                                continue
                except Exception:
                    continue

        self.programs = found
        self.games = {k: v for k, v in found.items() if v["type"] == "game"}
        self.apps = {k: v for k, v in found.items() if v["type"] != "game"}
        self._save_cache()
        self._last_scan_time = time.time()
        print(f"PROGRAMAS DETECTADOS: {len(self.programs)}")

    def _save_cache(self):
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump({"programs": self.programs}, f, indent=2, ensure_ascii=False)
        except Exception as error:
            print("ERROR GUARDANDO CACHE:", error)

    def refresh_programs(self):
        self.scan_programs()
        return f"Lista actualizada. Encontré {len(self.programs)} programas."

    def _looks_like_uninstaller(self, key, info):
        name = str(info.get("name", "") or key).lower()
        key_lower = key.lower()
        markers = ("desinstalar", "uninstall", "unins0", "quitar ")
        return any(m in name or m in key_lower for m in markers)

    def find_program(self, target, exclude_uninstallers=False):
        target = self.clean_target(target)
        if not target:
            return None

        candidates = self.programs

        if exclude_uninstallers:
            filtered = {
                key: info
                for key, info in self.programs.items()
                if not self._looks_like_uninstaller(key, info)
            }
            # Si filtrar dejó la lista vacía (ej. el único resultado
            # posible era un desinstalador), se usa la lista completa
            # como respaldo en vez de no encontrar nada.
            if filtered:
                candidates = filtered

        if target in candidates:
            return candidates[target]

        # De las coincidencias por substring, se prefiere la CLAVE
        # MÁS CORTA (la más específica/exacta), no la primera que
        # aparezca al recorrer el diccionario. Esto evita que "abre
        # sekiro" agarre "desinstalar sekiro shadows die twice" solo
        # porque salió primero en el escaneo.
        best_key = None
        for key in candidates:
            if target in key or key in target:
                if best_key is None or len(key) < len(best_key):
                    best_key = key

        if best_key:
            return candidates[best_key]

        matches = difflib.get_close_matches(
            target, list(candidates.keys()), n=1, cutoff=0.45
        )
        return candidates[matches[0]] if matches else None

    # ------------------------------------------------------------------
    # Procesos
    # ------------------------------------------------------------------
    def process_running(self, names):
        if not psutil:
            return False
        wanted = {self.normalize_process_name(n) for n in names}
        try:
            for p in psutil.process_iter(["name"]):
                name = p.info.get("name")
                if name and self.normalize_process_name(name) in wanted:
                    return True
        except Exception:
            pass
        return False

    # ------------------------------------------------------------------
    # Riot y clientes
    # ------------------------------------------------------------------
    def find_riot_client(self):
        candidates = [
            os.path.expandvars(r"%ProgramFiles%\Riot Games\Riot Client\RiotClientServices.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Riot Games\Riot Client\RiotClientServices.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Riot Games\Riot Client\RiotClientServices.exe"),
        ]
        for path in candidates:
            if os.path.isfile(path):
                return path

        info = self.find_program("riot client")
        if info:
            for value in (info.get("display_icon"), info.get("path")):
                if value:
                    match = re.search(r'([A-Za-z]:\\[^" ]+\.exe)', str(value), re.I)
                    if match and os.path.isfile(match.group(1)):
                        return match.group(1)
        return None

    def open_riot_client(self):
        processes = self.client_processes["riot client"]
        if self.process_running(processes):
            return True
        exe = self.find_riot_client()
        if not exe:
            return False
        try:
            subprocess.Popen([exe], cwd=os.path.dirname(exe), close_fds=True)
            return True
        except Exception as error:
            print("ERROR ABRIENDO RIOT:", error)
            return False

    def click_play_button(self, timeout=45):
        """Detecta Jugar/Play mediante UI Automation y, si hace falta, OCR."""
        targets = {"jugar", "play", "launch", "start", "iniciar"}
        end = time.time() + timeout

        while time.time() < end:
            if self._click_uia(targets):
                return True
            if self._click_ocr(targets):
                return True
            time.sleep(1)
        return False

    def _click_uia(self, targets):
        try:
            from pywinauto import Desktop
        except ImportError:
            return False
        try:
            desktop = Desktop(backend="uia")
            for window in desktop.windows(visible_only=True):
                try:
                    controls = window.descendants(control_type="Button")
                except Exception:
                    continue
                for control in controls:
                    try:
                        text = self.normalize_text(control.window_text())
                        if not text:
                            text = self.normalize_text(control.element_info.name)
                        if text in targets or any(t in text for t in targets):
                            print("BOTON DETECTADO:", text)
                            control.click_input()
                            return True
                    except Exception:
                        continue
        except Exception as error:
            print("UIA:", error)
        return False

    def _click_ocr(self, targets):
        try:
            import pyautogui
            import pytesseract
        except ImportError:
            return False
        try:
            image = pyautogui.screenshot()
            data = pytesseract.image_to_data(
                image, output_type=pytesseract.Output.DICT, config="--psm 11"
            )
            for i, raw in enumerate(data.get("text", [])):
                word = self.normalize_text(raw)
                if not word:
                    continue
                if word in targets or any(t in word for t in targets):
                    x = int(data["left"][i])
                    y = int(data["top"][i])
                    w = int(data["width"][i])
                    h = int(data["height"][i])
                    pyautogui.click(x + w // 2, y + h // 2)
                    print("BOTON OCR DETECTADO:", raw)
                    return True
        except Exception as error:
            print("OCR:", error)
        return False

    def launch_game_via_client(self, game):
        game = self.clean_target(game)
        client = self.game_clients.get(game)
        if not client:
            return None

        print(f"JUEGO: {game} | CLIENTE: {client}")
        if client == "riot client":
            if not self.open_riot_client():
                return "No pude abrir Riot Client."
            time.sleep(3)
            if self.click_play_button(45):
                return f"He pulsado Jugar para iniciar {game}."
            return "Abrí el cliente, pero no pude detectar el botón Jugar."

        return f"Abrí el cliente {client}, pero todavía no tengo un flujo automático para su botón Jugar."

    # ------------------------------------------------------------------
    # Abrir / cerrar
    # ------------------------------------------------------------------
    def _basic_program(self, target):
        programs = {
            "bloc de notas": r"C:\Windows\System32\notepad.exe",
            "notepad": r"C:\Windows\System32\notepad.exe",
            "calculadora": r"C:\Windows\System32\calc.exe",
            "paint": r"C:\Windows\System32\mspaint.exe",
            "cmd": r"C:\Windows\System32\cmd.exe",
            "powershell": r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            "explorador": r"C:\Windows\explorer.exe",
        }
        path = programs.get(target)
        if not path:
            return None
        try:
            subprocess.Popen([path], close_fds=True)
            return f"Abriendo {target}."
        except Exception:
            return f"No pude abrir {target}."

    def open_program(self, target):
        target = self.clean_target(target)
        if not target:
            return "Necesito saber qué quieres abrir."

        urls = {
            "youtube": "https://www.youtube.com",
            "google": "https://www.google.com",
            "gmail": "https://mail.google.com",
            "facebook": "https://www.facebook.com",
            "instagram": "https://www.instagram.com",
        }
        if target in urls:
            return self.open_url(urls[target])

        basic = self._basic_program(target)
        if basic:
            return basic

        game_result = self.launch_game_via_client(target)
        if game_result is not None:
            return game_result

        info = self.find_program(target, exclude_uninstallers=True)
        if not info:
            if time.time() - self._last_scan_time > self._rescan_cooldown_seconds:
                self.scan_programs()
                info = self.find_program(target, exclude_uninstallers=True)
        if not info:
            return (
                f"No encontré el programa {target}. "
                "Si lo acabas de instalar, di: actualiza la lista de programas."
            )

        path = str(info.get("path", "") or "").strip().strip('"')
        if path.lower().endswith(".lnk") and os.path.isfile(path):
            try:
                os.startfile(path)
                return f"Abriendo {info['name']}."
            except Exception as error:
                print("ERROR LNK:", error)

        if os.path.isfile(path) and path.lower().endswith(".exe"):
            try:
                subprocess.Popen([path], cwd=os.path.dirname(path), close_fds=True)
                return f"Abriendo {info['name']}."
            except Exception:
                pass

        if os.path.isdir(path):
            for root, _, files in os.walk(path):
                for filename in files:
                    if filename.lower().endswith(".exe"):
                        exe = os.path.join(root, filename)
                        try:
                            subprocess.Popen([exe], cwd=root, close_fds=True)
                            return f"Abriendo {info['name']}."
                        except Exception:
                            continue
                break

        try:
            subprocess.Popen(["cmd", "/c", "start", "", info["name"]], close_fds=True)
            return f"Abriendo {info['name']}."
        except Exception:
            return f"Encontré {info['name']}, pero no pude abrirlo."

    def close_program(self, target):
        target = self.clean_target(target)
        aliases = {
            "chrome": ["chrome.exe"],
            "google chrome": ["chrome.exe"],
            "edge": ["msedge.exe"],
            "firefox": ["firefox.exe"],
            "discord": ["Discord.exe"],
            "steam": ["steam.exe"],
            "riot client": self.client_processes["riot client"],
            "league of legends": [
                "LeagueClient.exe", "LeagueClientUx.exe", "LeagueClientUxRender.exe",
            ],
        }
        names = aliases.get(target, [target if target.endswith(".exe") else target + ".exe"])
        if not psutil:
            return "psutil no está instalado."

        wanted = {self.normalize_process_name(n) for n in names}
        closed = []
        try:
            for process in psutil.process_iter(["name"]):
                name = process.info.get("name")
                if name and self.normalize_process_name(name) in wanted:
                    try:
                        process.terminate()
                        closed.append(name)
                    except Exception:
                        pass
        except Exception:
            pass

        if closed:
            return "Cerré " + ", ".join(dict.fromkeys(closed)) + "."
        return f"No encontré {target} ejecutándose."

    # ------------------------------------------------------------------
    # DESINSTALAR PROGRAMAS
    # ------------------------------------------------------------------
    def uninstall_program(self, target, confirmed=False):
        target = self.clean_target(target)
        if not target:
            return "Necesito saber qué programa quieres desinstalar."

        info = self.find_program(target)
        if not info:
            self.scan_programs()
            info = self.find_program(target)
        if not info:
            return f"No encontré el programa {target} instalado."

        name = str(info.get("name", target)).strip()
        uninstall = str(info.get("uninstall", "") or "").strip()
        if not uninstall:
            return f"Encontré {name}, pero Windows no proporcionó un desinstalador registrado."

        if not confirmed:
            return f"CONFIRMATION_REQUIRED: ¿Quieres desinstalar {name}?"

        try:
            # Ejecuta el comando registrado por el propio instalador.
            # Se mantiene como cadena porque puede contener argumentos.
            subprocess.Popen(uninstall, shell=True, close_fds=True)
            self.programs.pop(self.normalize_text(name), None)
            self._save_cache()
            return f"Inicié la desinstalación de {name}."
        except Exception as error:
            print("ERROR DESINSTALANDO:", error)
            return f"No pude iniciar la desinstalación de {name}."

    # ------------------------------------------------------------------
    # CONTROL DEL SISTEMA
    # ------------------------------------------------------------------
    def sleep_pc(self):
        try:
            subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], close_fds=True)
            return "Suspendiendo la PC."
        except Exception as error:
            print("ERROR SUSPENDIENDO:", error)
            return "No pude suspender la PC."

    def lock_pc(self):
        try:
            subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"], close_fds=True)
            return "Bloqueando la PC."
        except Exception as error:
            print("ERROR BLOQUEANDO:", error)
            return "No pude bloquear la PC."

    def logout_pc(self):
        try:
            subprocess.Popen(["shutdown", "/l"], close_fds=True)
            return "Cerrando la sesión."
        except Exception as error:
            print("ERROR CERRANDO SESIÓN:", error)
            return "No pude cerrar la sesión."

    def cancel_shutdown(self):
        try:
            subprocess.run(["shutdown", "/a"], check=True, capture_output=True, text=True)
            return "Cancelé el apagado o reinicio programado."
        except Exception:
            return "No había un apagado o reinicio pendiente, o no pude cancelarlo."

    def system_info(self):
        if not psutil:
            return "psutil no está instalado."
        try:
            vm = psutil.virtual_memory()
            disk = psutil.disk_usage(os.path.abspath(os.sep))
            return (
                f"CPU: {psutil.cpu_percent(interval=0.5)}%\n"
                f"Memoria: {vm.percent}% ({vm.used / 1024**3:.1f} GB usados de {vm.total / 1024**3:.1f} GB)\n"
                f"Disco: {disk.percent}% ({disk.used / 1024**3:.1f} GB usados de {disk.total / 1024**3:.1f} GB)"
            )
        except Exception as error:
            print("ERROR INFORMACIÓN SISTEMA:", error)
            return "No pude obtener la información del sistema."

    def cpu_info(self):
        if not psutil:
            return "psutil no está instalado."
        try:
            return f"Uso de CPU: {psutil.cpu_percent(interval=0.5)}%. Núcleos: {psutil.cpu_count(logical=False) or psutil.cpu_count()} físicos / {psutil.cpu_count()} lógicos."
        except Exception:
            return "No pude obtener la información de CPU."

    def memory_info(self):
        if not psutil:
            return "psutil no está instalado."
        try:
            m = psutil.virtual_memory()
            return f"Memoria RAM: {m.percent}% usada. {m.used / 1024**3:.1f} GB de {m.total / 1024**3:.1f} GB."
        except Exception:
            return "No pude obtener la información de memoria."

    def disk_info(self):
        if not psutil:
            return "psutil no está instalado."
        try:
            d = psutil.disk_usage(os.path.abspath(os.sep))
            return f"Disco principal: {d.percent}% usado. {d.free / 1024**3:.1f} GB libres de {d.total / 1024**3:.1f} GB."
        except Exception:
            return "No pude obtener la información del disco."

    def battery_info(self):
        if not psutil:
            return "psutil no está instalado."
        try:
            b = psutil.sensors_battery()
            if not b:
                return "No detecté una batería en este equipo."
            estado = "conectada a corriente" if b.power_plugged else "usando batería"
            return f"Batería: {b.percent:.0f}%, {estado}."
        except Exception:
            return "No pude obtener la información de batería."

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    def open_url(self, target):
        target = str(target).strip()
        if not target.startswith(("http://", "https://")):
            target = "https://" + target
        try:
            webbrowser.open(target)
            return f"Abriendo {target}."
        except Exception:
            return "No pude abrir esa página."

    def open_file(self, target):
        target = os.path.expandvars(os.path.expanduser(str(target).strip()))
        if not os.path.isfile(target):
            return f"No encontré el archivo {target}."
        try:
            os.startfile(target)
            return f"Abriendo {target}."
        except Exception:
            return f"No pude abrir {target}."

    def get_processes(self):
        if not psutil:
            return []
        result = []
        for process in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                result.append(process.info)
            except Exception:
                continue
        return result

    def shutdown_pc(self):
        try:
            subprocess.run(["shutdown", "/s", "/t", "0"], check=True)
            return "Apagando la PC."
        except Exception:
            return "No pude apagar la PC."

    def restart_pc(self):
        try:
            subprocess.run(["shutdown", "/r", "/t", "0"], check=True)
            return "Reiniciando la PC."
        except Exception:
            return "No pude reiniciar la PC."