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
    """Controlador general de Windows para ECO 4.0.

    Permite abrir/cerrar aplicaciones y juegos, resolver alias de voz y,
    cuando un juego usa un cliente, esperar y pulsar Jugar/Play/Launch/Start.
    """

    def __init__(self):
        self.cache_dir = "data"
        self.cache_file = os.path.join(self.cache_dir, "installed_programs.json")
        self.portable_games_file = os.path.join(self.cache_dir, "portable_games.json")
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

        # "abre sistema 1" / "abre sistema 2" / "abre sistema 1 y 2"
        # -> páginas web propias del usuario, no programas instalados.
        self.custom_systems = {
            "1": "https://dldservicio.smartolt.com/auth/login",
            "2": "https://dldservicio.net/admin/login",
        }

        # =====================================================
        # PROGRAMAS QUE PIDEN CONFIRMACIÓN DE ADMINISTRADOR
        # =====================================================
        # Para cada uno, crea una Tarea Programada de Windows con
        # "ejecutar con privilegios más altos" (ver instrucciones),
        # y agrega aquí: "nombre que le dices a eco": "NombreDeLaTarea"
        #
        # Ejemplo:
        #   schtasks /create /tn "Cortana_AbrirSekiro" /tr "\"C:\...\sekiro.exe\""
        #            /sc once /st 00:00 /sd 01/01/2099 /rl highest /f
        #
        self.elevated_tasks = {
            "sekiro": "Cortana_AbrirSekiro",
            # "otro juego": "Cortana_AbrirOtroJuego",
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

                                    def value(field):
                                        try:
                                            return winreg.QueryValueEx(sub, field)[0] or ""
                                        except Exception:
                                            return ""

                                    if clean in found:
                                        # Ya existe (normalmente detectado como
                                        # acceso directo del menú Inicio, que NO
                                        # trae datos de desinstalación). Se
                                        # completan los campos que falten en
                                        # vez de descartar la información real
                                        # del registro — esto es lo que antes
                                        # rompía "desinstala X" para programas
                                        # como Discord.
                                        existing = found[clean]
                                        if not existing.get("uninstall"):
                                            existing["uninstall"] = value("UninstallString")
                                        if not existing.get("display_icon"):
                                            existing["display_icon"] = value("DisplayIcon")
                                        if not existing.get("path"):
                                            existing["path"] = value("InstallLocation")
                                        continue

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

        # cutoff=0.6 (antes 0.45): con 0.45, "whatsapp" contra
        # "character map" daba 0.476 — una coincidencia PURAMENTE
        # accidental de letras, no un parecido real — y Eco
        # terminaba abriendo el Mapa de caracteres al pedir WhatsApp
        # (que ni siquiera está en el catálogo). 0.6 sigue aceptando
        # errores de tipeo reales (p. ej. "spotifi" -> Spotify, 0.86)
        # pero rechaza coincidencias débiles como esa.
        matches = difflib.get_close_matches(
            target, list(candidates.keys()), n=1, cutoff=0.6
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
        # RiotClientServices.exe es un proceso de FONDO que casi
        # siempre está corriendo (Riot lo deja activo para arrancar
        # más rápido después), incluso SIN ninguna ventana visible.
        # Usar la lista completa aquí hacía que Eco pensara "ya
        # está abierto" y nunca lanzara nada — por eso no aparecía
        # ninguna ventana y el botón Jugar nunca se podía detectar
        # (no había ninguna ventana donde buscarlo).
        # RiotClientUx.exe es el proceso de la ventana real; solo ese
        # cuenta como "ya está abierto".
        if self.process_running(["RiotClientUx.exe"]):
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

    def click_play_button(self, timeout=45, process_names=None):
        """
        Detecta Jugar/Play mediante UI Automation y, si hace falta, OCR.

        Si se da process_names (ej. ["RiotClientServices.exe", ...]),
        la búsqueda se restringe a las ventanas de esos procesos. SIN
        esto, se buscaba en TODAS las ventanas visibles del escritorio
        — y como "launch" es una de las palabras buscadas, en equipos
        con Visual Studio abierto (que tiene un botón "Launch Profile"
        en su barra de herramientas) Eco terminaba haciéndole clic
        a ESO en vez de al botón real del cliente del juego.
        """
        targets = {"jugar", "play", "launch", "start", "iniciar"}
        end = time.time() + timeout
        first_attempt = True

        while time.time() < end:
            if self._click_uia(
                targets, process_names=process_names, debug=first_attempt
            ):
                return True
            if self._click_ocr(
                targets, process_names=process_names, debug=first_attempt
            ):
                return True
            first_attempt = False
            time.sleep(1)
        return False

    def _target_pids(self, process_names):
        if not process_names or not psutil:
            return None
        wanted = {self.normalize_process_name(n) for n in process_names}
        pids = set()
        try:
            for process in psutil.process_iter(["pid", "name"]):
                name = process.info.get("name")
                if name and self.normalize_process_name(name) in wanted:
                    pids.add(process.info["pid"])
        except Exception:
            pass
        return pids

    def _click_uia(self, targets, process_names=None, debug=False):
        try:
            from pywinauto import Desktop
        except ImportError:
            if debug:
                print("UIA DEBUG: pywinauto no está instalado.")
            return False

        allowed_pids = None
        if process_names:
            allowed_pids = self._target_pids(process_names)
            if not allowed_pids:
                # El proceso del cliente todavía no tiene ninguna
                # ventana abierta — nada que buscar todavía.
                if debug:
                    print(
                        "UIA DEBUG: ningún proceso de", process_names,
                        "está corriendo todavía."
                    )
                return False

        matched_windows = 0
        total_buttons = 0
        seen_texts = []

        try:
            desktop = Desktop(backend="uia")
            for window in desktop.windows(visible_only=True):
                try:
                    if allowed_pids is not None:
                        if window.process_id() not in allowed_pids:
                            continue
                    matched_windows += 1
                    controls = window.descendants(control_type="Button")
                except Exception:
                    continue
                for control in controls:
                    try:
                        text = self.normalize_text(control.window_text())
                        if not text:
                            text = self.normalize_text(control.element_info.name)
                        total_buttons += 1
                        if debug and len(seen_texts) < 20:
                            seen_texts.append(text or "(sin texto)")
                        if text in targets or any(t in text for t in targets):
                            print("BOTON DETECTADO:", text)
                            control.click_input()
                            return True
                    except Exception:
                        continue
        except Exception as error:
            print("UIA:", error)

        if debug:
            print(
                f"UIA DEBUG: {matched_windows} ventana(s) del proceso "
                f"encontradas, {total_buttons} botón(es) revisados. "
                f"Textos vistos: {seen_texts}"
            )

        return False

    def _tesseract_available(self):
        """
        pytesseract es solo el envoltorio de Python — necesita el
        motor real de Tesseract-OCR instalado aparte en Windows. Esto
        distingue "no está instalado el motor" de "no encontró el
        botón", para dar un mensaje que de verdad ayude.
        """
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def _click_ocr(self, targets, process_names=None, debug=False):
        try:
            import pyautogui
            import pytesseract
        except ImportError:
            if debug:
                print("OCR DEBUG: pyautogui o pytesseract no están instalados.")
            return False

        region = None
        offset_x, offset_y = 0, 0

        if process_names:
            allowed_pids = self._target_pids(process_names)
            if not allowed_pids:
                return False
            try:
                from pywinauto import Desktop
                desktop = Desktop(backend="uia")
                target_window = None
                for window in desktop.windows(visible_only=True):
                    try:
                        if window.process_id() in allowed_pids:
                            target_window = window
                            break
                    except Exception:
                        continue
                if target_window is None:
                    if debug:
                        print(
                            "OCR DEBUG: no encontré ninguna ventana de ese "
                            "proceso para recortar la captura de pantalla."
                        )
                    return False
                rect = target_window.rectangle()
                offset_x, offset_y = rect.left, rect.top
                region = (rect.left, rect.top, rect.width(), rect.height())
                if debug:
                    print(f"OCR DEBUG: región de captura = {region}")
            except Exception as error:
                print("UIA (región para OCR):", error)
                return False

        try:
            image = (
                pyautogui.screenshot(region=region)
                if region else pyautogui.screenshot()
            )
            data = pytesseract.image_to_data(
                image, output_type=pytesseract.Output.DICT, config="--psm 11"
            )
            read_words = []
            for i, raw in enumerate(data.get("text", [])):
                word = self.normalize_text(raw)
                if not word:
                    continue
                if debug and len(read_words) < 40:
                    read_words.append(word)
                if word in targets or any(t in word for t in targets):
                    x = int(data["left"][i]) + offset_x
                    y = int(data["top"][i]) + offset_y
                    w = int(data["width"][i])
                    h = int(data["height"][i])
                    pyautogui.click(x + w // 2, y + h // 2)
                    print("BOTON OCR DETECTADO:", raw)
                    return True
            if debug:
                print(
                    f"OCR DEBUG: {len(read_words)} palabra(s) leídas en "
                    f"la región: {read_words}"
                )
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
            if self.click_play_button(
                45, process_names=self.client_processes.get(client)
            ):
                return f"He pulsado Jugar para iniciar {game}."

            if not self._tesseract_available():
                return (
                    "Abrí el cliente, pero no pude detectar el botón "
                    "Jugar. Riot Client casi nunca expone sus botones a "
                    "la accesibilidad de Windows, así que Eco "
                    "necesita leer la pantalla con OCR — y Tesseract-OCR "
                    "no está instalado. Instálalo desde "
                    "https://github.com/UB-Mannheim/tesseract/wiki "
                    "(agrégalo al PATH) e inténtalo de nuevo."
                )

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

    # ------------------------------------------------------------------
    # JUEGOS PORTABLES
    # ------------------------------------------------------------------
    def _portable_game_roots(self):
        """Devuelve todas las unidades locales disponibles para buscarlas."""
        roots = []
        for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            drive = f"{letter}:\\"
            if not os.path.isdir(drive):
                continue
            roots.append(drive)

        return list(dict.fromkeys(roots))

    def _read_portable_games(self):
        try:
            with open(self.portable_games_file, "r", encoding="utf-8") as file:
                data = json.load(file)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_portable_game(self, name, path):
        data = self._read_portable_games()
        data[self.normalize_text(name)] = path
        temporary = self.portable_games_file + ".tmp"
        try:
            with open(temporary, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
            os.replace(temporary, self.portable_games_file)
        except OSError as error:
            print("ERROR GUARDANDO JUEGO PORTABLE:", error)

    def _portable_game_score(self, target, path):
        target = self.normalize_text(target)
        compact_target = target.replace(" ", "")
        filename = os.path.splitext(os.path.basename(path))[0]
        parent = os.path.basename(os.path.dirname(path))
        labels = (self.normalize_text(filename), self.normalize_text(parent))
        score = 0.0

        for label in labels:
            compact_label = label.replace(" ", "")
            if label == target or compact_label == compact_target:
                score = max(score, 100.0)
            elif target in label or compact_target in compact_label:
                score = max(score, 85.0)
            else:
                score = max(score, difflib.SequenceMatcher(None, target, label).ratio() * 70)
        return score

    # Profundidad por defecto del escaneo de unidades completas. Antes
    # era ilimitada (max_depth=None): en discos con muchas carpetas
    # (Program Files, backups, etc.) eso podía tardar mucho la primera
    # vez que pedías un juego portable no cacheado todavía. 8 niveles
    # alcanza sin problema instalaciones típicas tipo
    # "E:\Games\Nombre\bin\win64\juego.exe" sin recorrer todo el disco.
    DEFAULT_PORTABLE_SCAN_DEPTH = 8

    def find_portable_game(self, target, max_depth=DEFAULT_PORTABLE_SCAN_DEPTH):
        """Encuentra un ejecutable en cualquier unidad local del equipo."""
        target = self.clean_target(target)
        if not target:
            return None

        cached = self._read_portable_games().get(target)
        if cached and os.path.isfile(cached):
            return cached

        best_path = None
        best_score = 0.0
        roots = self._portable_game_roots()
        if not roots:
            return None

        print("BUSCANDO EJECUTABLE EN TODO EL EQUIPO:", ", ".join(roots))
        for base in roots:
            for current_root, directories, files in os.walk(base, topdown=True):
                relative = os.path.relpath(current_root, base)
                depth = 0 if relative == "." else relative.count(os.sep) + 1
                directories[:] = [
                    item for item in directories
                    if item.lower() not in {
                        "$recycle.bin", "system volume information", "windows",
                        "node_modules", "__pycache__", ".git",
                        "program files", "program files (x86)", "programdata",
                        "appdata", "windows.old", "$windows.~bt", "$windows.~ws",
                    }
                ]
                if max_depth is not None and depth >= max_depth:
                    directories[:] = []

                for filename in files:
                    if not filename.lower().endswith(".exe"):
                        continue
                    path = os.path.join(current_root, filename)
                    score = self._portable_game_score(target, path)
                    if score > best_score:
                        best_path, best_score = path, score

        # Evita abrir un .exe apenas parecido por accidente.
        if best_path and best_score >= 60:
            self._save_portable_game(target, best_path)
            return best_path
        return None

    def open_portable_game(self, target):
        path = self.find_portable_game(target)
        if not path:
            return None
        try:
            subprocess.Popen([path], cwd=os.path.dirname(path), close_fds=True)
            return f"Abriendo: {os.path.splitext(os.path.basename(path))[0]}."
        except Exception as error:
            print("ERROR ABRIENDO JUEGO PORTABLE:", error)
            return f"Encontré {target}, pero no pude abrir su ejecutable."

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
            portable_result = self.open_portable_game(target)
            if portable_result:
                return portable_result
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
    # INSTALAR PROGRAMAS (vía gestores de paquetes oficiales: winget,
    # y si no encuentra el paquete ahí, Chocolatey y luego Scoop)
    #
    # Se usan gestores de paquetes en vez de descargar instaladores de
    # sitios web directamente: los tres verifican el origen de cada
    # paquete y saben instalar en modo silencioso, sin que Eco
    # tenga que adivinar URLs de descarga que pueden cambiar en
    # cualquier momento — y sin el riesgo de correr un .exe bajado de
    # una página sin verificar. Se prueban en orden y solo se pasa al
    # siguiente si el anterior no tiene el paquete (no si lo tiene y
    # falla al instalarlo, para no reintentar innecesariamente).
    # ------------------------------------------------------------------
    def _winget_available(self):
        try:
            result = subprocess.run(
                ["winget", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def _choco_available(self):
        try:
            result = subprocess.run(
                ["choco", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def _scoop_available(self):
        try:
            result = subprocess.run(
                ["scoop", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def _install_with_winget(self, name):
        print(f"INSTALANDO CON WINGET: {name}")
        try:
            result = subprocess.run(
                [
                    "winget", "install",
                    "--name", name,
                    "--accept-package-agreements",
                    "--accept-source-agreements",
                    "--silent",
                    "--disable-interactivity",
                ],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=300
            )

            output = (result.stdout or "") + (result.stderr or "")
            print("SALIDA WINGET:", output)

            if result.returncode == 0:
                return f"Instalé {name} con winget."

            lowered = output.lower()

            if "multiple packages found" in lowered or "varios paquetes" in lowered:
                return (
                    f"Encontré varias aplicaciones parecidas a {name} en "
                    "winget. Sé más específico con el nombre."
                )

            if "no package found" in lowered or "no se encontr" in lowered:
                # None = "no está en este catálogo", para seguir
                # probando con el siguiente gestor de paquetes.
                return None

            return (
                f"Encontré {name} en winget, pero no pude instalarlo. Es "
                "posible que Windows haya pedido tu confirmación en una "
                "ventana aparte — revisa la pantalla."
            )

        except subprocess.TimeoutExpired:
            return (
                f"La instalación de {name} con winget está tardando "
                "demasiado. Revisa si Windows pidió alguna confirmación "
                "en pantalla."
            )
        except Exception as error:
            print("ERROR INSTALANDO CON WINGET:", error)
            return None

    def _install_with_choco(self, name):
        print(f"INSTALANDO CON CHOCOLATEY: {name}")
        try:
            result = subprocess.run(
                ["choco", "install", name, "-y", "--no-progress"],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=300
            )

            output = (result.stdout or "") + (result.stderr or "")
            print("SALIDA CHOCOLATEY:", output)

            if result.returncode == 0:
                return f"Instalé {name} con Chocolatey."

            lowered = output.lower()

            if "unable to find package" in lowered or "0/1" in lowered:
                return None

            return (
                f"Encontré {name} en Chocolatey, pero no pude instalarlo."
            )

        except subprocess.TimeoutExpired:
            return (
                f"La instalación de {name} con Chocolatey está tardando "
                "demasiado."
            )
        except Exception as error:
            print("ERROR INSTALANDO CON CHOCOLATEY:", error)
            return None

    def _install_with_scoop(self, name):
        print(f"INSTALANDO CON SCOOP: {name}")
        try:
            result = subprocess.run(
                ["scoop", "install", name],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=300
            )

            output = (result.stdout or "") + (result.stderr or "")
            print("SALIDA SCOOP:", output)

            if result.returncode == 0:
                return f"Instalé {name} con Scoop."

            lowered = output.lower()

            if "couldn't find" in lowered or "no se encontr" in lowered:
                return None

            return f"Encontré {name} en Scoop, pero no pude instalarlo."

        except subprocess.TimeoutExpired:
            return (
                f"La instalación de {name} con Scoop está tardando "
                "demasiado."
            )
        except Exception as error:
            print("ERROR INSTALANDO CON SCOOP:", error)
            return None

    def install_program(self, name):
        name = str(name).strip().strip('"\'')

        if not name:
            return "¿Qué programa quieres que instale?"

        managers = (
            (self._winget_available, self._install_with_winget),
            (self._choco_available, self._install_with_choco),
            (self._scoop_available, self._install_with_scoop),
        )

        any_available = False

        for is_available, install_with in managers:
            if not is_available():
                continue
            any_available = True
            result = install_with(name)
            if result is not None:
                if result.startswith(f"Instalé {name}"):
                    # Fuerza que el próximo "abre X" reescanee los
                    # programas, para que encuentre lo recién instalado
                    # sin esperar el enfriamiento normal de 5 minutos.
                    self._last_scan_time = 0
                return result

        if not any_available:
            return (
                "No encontré ningún gestor de paquetes instalado. "
                "Instala 'App Installer' desde la Microsoft Store para "
                "tener winget, Chocolatey desde https://chocolatey.org/install, "
                "o Scoop desde https://scoop.sh, e inténtalo de nuevo."
            )

        return (
            f"No encontré {name} en ninguno de los catálogos disponibles "
            "(winget, Chocolatey, Scoop). Revisa el nombre exacto."
        )

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

    def open_system(self, numbers):
        """
        Abre una o más de las páginas de self.custom_systems.
        'numbers' es una lista de claves a abrir (ej. ["1"] o
        ["1", "2"]).
        """
        opened = []
        missing = []

        for number in numbers:
            url = self.custom_systems.get(str(number).strip())
            if url:
                self.open_url(url)
                opened.append(str(number))
            else:
                missing.append(str(number))

        if not opened:
            return f"No tengo configurado el sistema {', '.join(missing)}."

        label = " y ".join(opened)
        response = (
            f"Abriendo el sistema {label}."
            if len(opened) == 1
            else f"Abriendo los sistemas {label}."
        )

        if missing:
            response += f" No tengo configurado el sistema {', '.join(missing)}."

        return response

    def open_sign_in_options(self):
        """Abre la pantalla oficial de Windows para PIN y contraseña."""
        try:
            os.startfile("ms-settings:signinoptions")
            return (
                "Abrí las opciones de inicio de sesión. Selecciona PIN de "
                "Windows Hello y luego Cambiar. Windows te pedirá confirmar "
                "tu identidad."
            )
        except Exception as error:
            print("ERROR ABRIENDO OPCIONES DE INICIO DE SESIÓN:", error)
            return "No pude abrir las opciones de inicio de sesión de Windows."

    def open_file(self, target):
        target = os.path.expandvars(os.path.expanduser(str(target).strip()))
        if not os.path.isfile(target):
            return f"No encontré el archivo {target}."
        try:
            os.startfile(target)
            return f"Abriendo {target}."
        except Exception:
            return f"No pude abrir {target}."

    def open_desktop_application(self, target):
        """Abre un acceso directo o ejecutable ubicado en el Escritorio.

        No depende del catálogo de programas de Windows: revisa el
        Escritorio real del usuario, incluso si OneDrive lo redirigió.
        """
        requested = self.normalize_text(target)
        if not requested:
            return "¿Qué aplicación del Escritorio quieres ejecutar?"

        desktop = self._resolve_shell_folder(
            self.FOLDER_LOCATIONS["escritorio"][0],
            self.FOLDER_LOCATIONS["escritorio"][1]
        )
        if not os.path.isdir(desktop):
            return "No encontré el Escritorio de este usuario."

        candidates = []
        for item in os.listdir(desktop):
            path = os.path.join(desktop, item)
            if not os.path.isfile(path):
                continue
            extension = os.path.splitext(item)[1].lower()
            if extension not in {".lnk", ".exe"}:
                continue
            display_name = os.path.splitext(item)[0]
            normalized_name = self.normalize_text(display_name)
            if normalized_name == requested:
                candidates.insert(0, (display_name, path))
            elif requested in normalized_name:
                candidates.append((display_name, path))

        if not candidates:
            return f"No encontré {target} como acceso directo o ejecutable en el Escritorio."

        display_name, path = candidates[0]
        try:
            os.startfile(path)
            return f"Ejecutando {display_name} desde el Escritorio."
        except Exception as error:
            print("ERROR ABRIENDO APLICACIÓN DEL ESCRITORIO:", error)
            return f"No pude ejecutar {display_name} desde el Escritorio."

    # ------------------------------------------------------------------
    # CREAR CARPETA
    # ------------------------------------------------------------------

    # Nombres de valor dentro de esta clave del registro, que apuntan
    # a la ubicación REAL de cada carpeta — importante porque con
    # OneDrive activado (muy común hoy en día), "Escritorio",
    # "Documentos", etc. suelen estar REDIRIGIDOS dentro de
    # OneDrive (ej. C:\Users\tú\OneDrive\Desktop) en vez de la ruta
    # clásica C:\Users\tú\Desktop. Si se asume la ruta clásica sin
    # verificar, la carpeta se crea en un lugar que ya nadie mira.
    SHELL_FOLDERS_KEY = (
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
    )

    FOLDER_LOCATIONS = {
        # nombre hablado: (nombre de valor en el registro, ruta de respaldo)
        "escritorio": ("Desktop", r"%USERPROFILE%\Desktop"),
        "documentos": ("Personal", r"%USERPROFILE%\Documents"),
        "descargas": ("{374DE290-123F-4565-9164-39C4925E467B}", r"%USERPROFILE%\Downloads"),
        "imagenes": ("My Pictures", r"%USERPROFILE%\Pictures"),
        "imágenes": ("My Pictures", r"%USERPROFILE%\Pictures"),
        "musica": ("My Music", r"%USERPROFILE%\Music"),
        "música": ("My Music", r"%USERPROFILE%\Music"),
        "videos": ("My Video", r"%USERPROFILE%\Videos"),
        "vídeos": ("My Video", r"%USERPROFILE%\Videos"),
    }

    def _resolve_shell_folder(self, registry_value_name, fallback_path):
        if winreg:
            try:
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER, self.SHELL_FOLDERS_KEY
                ) as key:
                    value, _ = winreg.QueryValueEx(key, registry_value_name)
                    resolved = os.path.expandvars(value)
                    if resolved and os.path.isdir(resolved):
                        return resolved
            except Exception as error:
                print("ERROR LEYENDO CARPETA DEL REGISTRO:", error)

        return os.path.expandvars(fallback_path)

    def _find_named_folder(self, name, location=None):
        """
        Resuelve la ruta de una carpeta por nombre. Si se da una
        ubicación, busca solo ahí. Si no, busca primero en el
        escritorio (por defecto) y si no está, revisa las demás
        ubicaciones conocidas, para no fallar solo porque no
        recuerdas dónde la creaste.

        Devuelve (path, location_key) o (None, None) si no la
        encuentra en ningún lado.
        """

        if location:
            location_key = str(location).strip().lower()
            registry_name, fallback_path = self.FOLDER_LOCATIONS.get(
                location_key, self.FOLDER_LOCATIONS["escritorio"]
            )
            base = self._resolve_shell_folder(registry_name, fallback_path)
            path = os.path.join(base, name)
            return (path, location_key) if os.path.isdir(path) else (None, None)

        # Sin ubicación explícita: escritorio primero (comportamiento
        # por defecto de create_folder), luego las demás.
        ordered_keys = ["escritorio"] + [
            k for k in self.FOLDER_LOCATIONS if k != "escritorio"
        ]

        for location_key in ordered_keys:
            registry_name, fallback_path = self.FOLDER_LOCATIONS[location_key]
            base = self._resolve_shell_folder(registry_name, fallback_path)
            path = os.path.join(base, name)
            if os.path.isdir(path):
                return path, location_key

        return None, None

    def create_folder(self, name, location=None):
        name = str(name).strip().strip('"\'')

        if not name:
            return "Necesito un nombre para la carpeta."

        location_key = str(location or "escritorio").strip().lower()
        registry_name, fallback_path = self.FOLDER_LOCATIONS.get(
            location_key, self.FOLDER_LOCATIONS["escritorio"]
        )

        base = self._resolve_shell_folder(registry_name, fallback_path)
        path = os.path.join(base, name)

        if os.path.isdir(path):
            try:
                os.startfile(path)
            except Exception:
                pass
            return f"Ya existe una carpeta llamada {name} ahí. La abrí para que la veas."

        try:
            os.makedirs(path, exist_ok=False)
        except Exception as error:
            print("ERROR CREANDO CARPETA:", error)
            return f"No pude crear la carpeta {name}."

        label = location_key if location_key in self.FOLDER_LOCATIONS else "escritorio"

        # Se abre automáticamente para que quede clarísimo dónde
        # quedó, sin depender de que el usuario adivine la ruta.
        try:
            os.startfile(path)
        except Exception as error:
            print("ERROR ABRIENDO CARPETA CREADA:", error)

        return f"Creé la carpeta {name} en {label} y la abrí."

    # ------------------------------------------------------------------
    # BORRAR CARPETA (a la papelera de reciclaje, NUNCA borrado
    # permanente directo — un error de reconocimiento de voz no debe
    # poder destruir algo sin posibilidad de recuperarlo)
    # ------------------------------------------------------------------
    def delete_folder(self, name, location=None, confirmed=False):
        name = str(name).strip().strip('"\'')

        if not name:
            return "Necesito el nombre de la carpeta que quieres borrar."

        path, found_location = self._find_named_folder(name, location)

        if not path:
            where = f" en {location}" if location else ""
            return f"No encontré una carpeta llamada {name}{where}."

        if not confirmed:
            return (
                f"CONFIRMATION_REQUIRED: ¿Quieres enviar la carpeta "
                f"{name} (en {found_location}) a la papelera de reciclaje?"
            )

        try:
            from send2trash import send2trash
        except ImportError:
            return (
                "Necesito el paquete Send2Trash para borrar de forma segura. "
                "Instálalo con: pip install Send2Trash"
            )

        try:
            send2trash(path)
            return f"Envié la carpeta {name} a la papelera de reciclaje."
        except Exception as error:
            print("ERROR BORRANDO CARPETA:", error)
            return f"No pude borrar la carpeta {name}."

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
