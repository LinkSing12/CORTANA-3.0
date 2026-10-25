import os
import re
import time
import threading
import subprocess

from voice.listener import Listener
from voice.speaker import Speaker

from memory.memory import Memory
from memory.learning import Learning

from windows.controller import WindowsController
from windows.media import MediaController
from windows.winamp import WinampController
from windows.wifi import WifiController
from windows.bluetooth import BluetoothController

from core.brain import Brain
from core.router import Router
from core.learning_brain import LearningBrain
from core.conversation import Conversation
from core.updater import Updater
from core.context_resolver import ContextCommandResolver
from core.skill_learner import SkillLearner
from core.whatsapp_client import WhatsAppClient


class Eco:

    def __init__(self):

        self.name = "Eco"

        self.listener = Listener()
        self.speaker = Speaker()

        self.memory = Memory()
        self.learning = Learning()

        self.learning_brain = LearningBrain(
            self.learning
        )

        self.conversation = Conversation()

        self.windows = WindowsController()
        self.media = MediaController()
        self.wifi = WifiController()
        self.bluetooth = BluetoothController()

        # AJUSTA esta carpeta a donde tengas tu música real si no
        # está en la carpeta "Música" por defecto de Windows.
        self.winamp = WinampController()

        self.updater = Updater()

        # Guarda la acción destructiva que está esperando confirmación
        # (flujo de dos turnos: "desinstala X" / "borra la carpeta X"
        # -> Eco pregunta -> usuario dice "sí" -> se ejecuta).
        # Formato: {"type": "uninstall" | "delete_folder", "target": ...}
        self.pending_confirmation = None

        self.context_resolver = ContextCommandResolver()

        # =====================================================
        # PALABRA DE ACTIVACIÓN POR VOZ ("eco")
        #
        # Eco siempre está escuchando, pero en modo PASIVO
        # ignora todo lo que no empiece con "eco". Al decir "eco",
        # se activa por VOICE_ACTIVE_WINDOW_SECONDS: durante ese
        # tiempo puede darle órdenes seguidas sin repetir "eco".
        # Si pasa ese tiempo sin una orden nueva, vuelve a pasivo.
        #
        # Esto SOLO aplica al canal de voz — escribir en la consola
        # o en la ventana gráfica sigue funcionando siempre directo,
        # sin necesitar "eco".
        # =====================================================
        # Variantes fonéticas: el reconocimiento de voz en español a
        # veces transcribe "eco" como "ecko", "esco", "eko", etc.
        # _strip_wake_word() las acepta todas por igual.
        self.WAKE_WORD_VARIANTS = (
            "eco", "ecko", "esco", "eko", "ecco",
            "hecko", "ehco", "equo", "heco",
        )
        self.VOICE_ACTIVE_WINDOW_SECONDS = 30
        self.voice_active = False
        self.voice_last_activity = 0.0

        self.brain = Brain()

        # Genera y (con confirmación explícita del usuario en un turno
        # aparte) guarda habilidades nuevas cuando un comando no coincide
        # con nada conocido. Ver core/skill_learner.py para el flujo de
        # seguridad de dos pasos (prepare_skill + confirm_and_save).
        self.skill_learner = SkillLearner(self.brain)

        # El navegador de WhatsApp Web NO se abre aquí — solo la
        # primera vez que se envíe, lea o borre un mensaje (ver
        # WhatsAppClient._ensure_driver), para no ralentizar el
        # arranque normal de Eco.
        self.whatsapp = WhatsAppClient()

        self.router = Router(
            self.windows,
            self.media,
            brain=self.brain
        )

        # Interfaz gráfica (window.py). Es opcional: si nadie
        # llama a set_interface(), Eco sigue funcionando
        # 100% por consola/voz igual que antes.
        self.window = None

    # =========================================================
    # CONECTAR INTERFAZ GRAFICA (window.py)
    # =========================================================

    def set_interface(self, window):

        self.window = window

        # Conecta la voz con la carita de robot (si la ventana la
        # tiene) para que la boca se mueva sincronizada con el audio
        # real. Si window no tiene set_window (una interfaz distinta,
        # o ninguna), simplemente no pasa nada.
        if hasattr(self.speaker, "set_window"):
            self.speaker.set_window(window)

    # =========================================================
    # ACTUALIZAR INTERFAZ GRAFICA (si existe)
    # =========================================================

    def _update_window(
        self,
        listened=None,
        analysis=None,
        intent=None,
        target=None,
        response=None,
        status=None
    ):

        if not self.window:
            return

        try:

            if listened is not None:
                self.window.set_listened(listened)

            if analysis is not None:
                self.window.set_analysis(analysis)

            if intent is not None:
                self.window.set_intent(intent)

            if target is not None:
                self.window.set_target(target if target else "—")

            if response is not None:
                self.window.set_response(response)

            if status is not None:
                self.window.set_status(status)

        except Exception as error:

            print(
                "ERROR ACTUALIZANDO VENTANA:",
                error
            )

    # =========================================================
    # INICIAR ECO
    # =========================================================

    def start(self):

        print()
        print("=" * 55)
        print("                 ECO 4.0")
        print("                 IA LOCAL")
        print("=" * 55)
        print()

        print("MODO TEXTO + VOZ ACTIVADO")
        print(
            "Escribe tu orden y presiona Enter, "
            "o dila en voz alta."
        )

        print("Escribe o di 'salir' para cerrar.")
        print()

        if self.brain.is_available():
            print("✅ OLLAMA: conectado y listo.")
        else:
            print("=" * 55)
            print("⚠️  OLLAMA NO ESTÁ CORRIENDO.")
            print(
                "   Los comandos que necesiten interpretar lenguaje "
                "libre (preguntas, búsquedas, órdenes no reconocidas)"
            )
            print(
                "   van a fallar hasta que abras Ollama. Los comandos "
                "directos (abrir/cerrar programas, volumen, sistema)"
            )
            print("   seguirán funcionando normal.")
            print("   Para arrancarlo: abre la app Ollama, o corre 'ollama serve'.")
            print("=" * 55)
        print()

        try:
            if self.updater.should_check_now():
                update_info = self.updater.check_for_update()
                if update_info and update_info.get("available"):
                    print("=" * 55)
                    print(
                        f"🔄 ACTUALIZACIÓN DISPONIBLE: "
                        f"{update_info['current_version']} -> "
                        f"{update_info['latest_version']}"
                    )
                    print("   Di 'busca actualizaciones' para instalarla.")
                    print("=" * 55)
                    print()
            else:
                print("(Chequeo de actualizaciones en enfriamiento, se omite por ahora.)")
        except Exception as error:
            print("ERROR CHEQUEANDO ACTUALIZACIONES AL ARRANCAR:", error)

        try:
            self.speaker.speak(
                "Sistema iniciado."
            )
        except Exception as error:
            print(
                "ERROR VOZ:",
                error
            )

        voice_thread = threading.Thread(
            target=self._voice_loop,
            daemon=True
        )

        voice_thread.start()

        while True:

            try:
                text = input("> ").strip()

            except (KeyboardInterrupt, EOFError):

                print()
                print("ECO CERRADA.")
                break

            if not text:
                continue

            if self.is_exit_command(
                text.lower()
            ):

                print(
                    "ECO: Hasta luego."
                )

                break

            self.respond(text)

    # =========================================================
    # ESCUCHAR VOZ
    # =========================================================

    def _voice_loop(self):

        while True:

            try:

                text = self.listener.listen()

            except Exception as error:

                print(
                    "ERROR ESCUCHANDO:",
                    error
                )

                continue

            if not text:
                continue

            text = text.strip()

            if not text:
                continue

            print()
            print(
                "ESCUCHADO:",
                text
            )

            # -------------------------------------------------
            # ¿Se venció la ventana de 30s sin recibir órdenes?
            # Se revisa ANTES de intentar usar lo que se acaba de
            # escuchar, porque si ya pasó el tiempo, esto que se
            # acaba de oír necesita "eco" de nuevo para contar.
            # -------------------------------------------------

            if self.voice_active and (
                time.time() - self.voice_last_activity
                > self.VOICE_ACTIVE_WINDOW_SECONDS
            ):

                self.voice_active = False

                print(
                    "(Eco volvió a modo pasivo: "
                    "pasaron 30s sin órdenes. Di 'eco' para reactivarla.)"
                )

                self._update_window(
                    status="● PASIVA (di 'eco')"
                )

                if self.window:
                    try:
                        self.window.hide()
                    except Exception:
                        pass

            command = None

            if self.voice_active:

                # Ya está activa: todo lo que diga cuenta como
                # orden directa, sin necesitar repetir "eco".
                command = text

            else:

                remainder = self._strip_wake_word(text)

                if remainder is not None:

                    self.voice_active = True

                    if self.window:
                        try:
                            self.window.show()
                        except Exception:
                            pass

                    self._update_window(
                        status="● ACTIVA (escuchando)"
                    )

                    if remainder:

                        command = remainder

                    else:

                        # Dijo solo "eco", sin orden todavía:
                        # confirma que está escuchando y espera
                        # la siguiente frase, sin procesar nada aún.
                        try:
                            self.speaker.speak("Dime.")
                        except Exception:
                            pass

                else:

                    # Modo pasivo y no dijo "eco": se ignora todo.
                    continue

            if command is None:
                continue

            self.voice_last_activity = time.time()

            if self.is_exit_command(
                command.lower()
            ):

                try:
                    self.speaker.speak(
                        "Hasta luego."
                    )
                except Exception:
                    pass

                print()
                print(
                    "ECO CERRADA (por voz)."
                )

                os._exit(0)

            self.respond(command)

            # Renueva la ventana de 30s tras procesar la orden.
            self.voice_last_activity = time.time()

    # =========================================================
    # PALABRA DE ACTIVACIÓN
    # =========================================================

    def _strip_wake_word(self, text):
        """
        Si el texto empieza con alguna variante de la palabra de
        activación ("eco", "ecko", "esco", etc. — ver
        WAKE_WORD_VARIANTS), devuelve lo que queda después (puede ser
        cadena vacía si solo dijo la palabra de activación). Si NO
        empieza con ninguna variante, devuelve None.
        """

        alternativas = "|".join(
            re.escape(variante) for variante in self.WAKE_WORD_VARIANTS
        )

        match = re.match(
            rf"^\s*(?:{alternativas})\b[\s,.:!¡]*",
            text,
            re.IGNORECASE
        )

        if not match:
            return None

        return text[match.end():].strip()

    # =========================================================
    # DETECTAR PETICIÓN EXPLÍCITA DE APRENDER UNA HABILIDAD NUEVA
    # (generar código), a diferencia de aprender un ALIAS de un
    # intent ya existente (eso lo maneja LearningBrain más arriba).
    # =========================================================

    LEARN_SKILL_TRIGGERS = (
        "aprende a ", "aprende como ", "aprende cómo ",
        "enséñame a ", "enseñame a ",
        "puedes aprender a ", "quiero que aprendas a ",
    )

    def _extract_skill_description(self, text):
        """
        Si el texto empieza con una frase explícita para pedir una
        habilidad nueva, devuelve la descripción (sin la frase
        disparadora). Si no, devuelve None — así un UNKNOWN cualquiera
        (por ejemplo, ruido mal transcrito por voz) NO dispara la
        generación de código.
        """

        stripped = text.strip()
        lowered = stripped.lower()

        for trigger in self.LEARN_SKILL_TRIGGERS:
            if lowered.startswith(trigger):
                description = stripped[len(trigger):].strip()
                return description or None

        return None

    # =========================================================
    # COMANDOS PARA CERRAR ECO
    # =========================================================

    def is_exit_command(self, text):

        commands = [
            "salir",
            "terminar",
            "termina",
            "apagar asistente",
            "apaga el asistente"
        ]

        # "cerrar eco" / "apaga eco", incluyendo las variantes fonéticas
        # con las que el micrófono suele transcribir el nombre (ver
        # WAKE_WORD_VARIANTS).
        for nombre in self.WAKE_WORD_VARIANTS:
            commands.append(f"cerrar {nombre}")
            commands.append(f"apaga {nombre}")

        return text in commands

    # =========================================================
    # COMANDOS LOCALES
    # =========================================================

    # =========================================================
    # WINAMP: DETECCIÓN DE COMANDOS
    # =========================================================

    # El reconocimiento de voz confunde seguido "winamp" con "windows"
    # (suenan parecido). Aceptar "windows" aquí es seguro PORQUE solo
    # se usa dentro de la frase "reproduce/pon/toca X en ___" — nadie
    # dice eso de verdad refiriéndose al sistema operativo, así que no
    # choca con comandos reales sobre Windows en el resto del proyecto.
    WINAMP_MENTION = (
        r"(?:winamp|windows|wiiamp|wynamp|guinamp|uinamp|vinamp|winan)"
    )

    def _extract_winamp_target(self, command):
        """
        Revisa si el comando pide reproducir algo en Winamp, ya sea
        en forma compuesta ("abre winamp y reproduce X") o directa
        ("reproduce X en winamp"). Si coincide, devuelve una tupla
        ("number", "5") o ("name", "bad bunny"). Si no, devuelve None.
        """

        FILLER = (
            r"(?:por favor\s+|porfavor\s+|puedes\s+|podrias\s+|"
            r"podrías\s+|quiero que\s+)?"
        )

        VERB = r"(?:reproduce|reproducir|pon|poner|toca|tocar|play)"

        patterns = [
            # "abre winamp y reproduce X" / "abre winamp reproduce X"
            rf"^{FILLER}abre\s+{self.WINAMP_MENTION}\s+(?:y\s+)?{VERB}\s+(.+)$",
            # "reproduce X en winamp"
            rf"^{FILLER}{VERB}\s+(.+?)\s+en\s+{self.WINAMP_MENTION}$",
        ]

        for pattern in patterns:

            match = re.match(pattern, command)

            if not match:
                continue

            raw_target = match.group(1).strip()

            if not raw_target:
                return None

            return self._parse_winamp_number_or_name(raw_target)

        return None

    def _parse_winamp_number_or_name(self, text):
        """
        Si el texto es, en el fondo, solo un NÚMERO acompañado de
        relleno ("el", "la", "canción", "música", "pista", "tema",
        "número" — en CUALQUIER orden), se interpreta como pedido de
        reproducir esa posición en Winamp. Antes solo reconocía
        "canción número X"; con solo decir "música número X" en vez de
        "canción número X" ya no coincidía, y la frase completa se
        trataba como nombre de canción a buscar en YouTube.
        """

        text = text.strip()

        cleaned = re.sub(
            r"\b(?:el|la|canci[oó]n|m[uú]sica|pista|tema|n[uú]mero)\b",
            " ",
            text,
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        if re.fullmatch(r"\d+", cleaned):
            return ("number", cleaned)

        return ("name", text)

    # =========================================================
    # CARPETAS: EXTRAER NOMBRE Y UBICACIÓN SIN IMPORTAR EL ORDEN
    # =========================================================

    FOLDER_LOCATION_WORDS = (
        r"escritorio|documentos|descargas|imagenes|imágenes|"
        r"musica|música|videos|vídeos"
    )

    def _parse_folder_command(self, command, verbs):
        """
        Extrae (nombre, ubicación) de una orden de carpeta, sin
        importar en qué parte de la frase venga la ubicación:

            "crea una carpeta llamada tareas en el escritorio"
            "crea una carpeta en el escritorio llamada tareas"
            "crea una carpeta en documentos que se llame tareas"

        Todas deben dar name="tareas", location="escritorio"/"documentos".
        Devuelve (None, None) si el verbo/objeto ("carpeta") no calza.
        """

        verb_pattern = "|".join(verbs)

        # 1) Separar la ubicación de donde sea que esté en la frase.
        location_search = re.search(
            rf"\ben\s+(?:el\s+|la\s+)?({self.FOLDER_LOCATION_WORDS})\b",
            command
        )

        location = location_search.group(1) if location_search else None

        remainder = command
        if location_search:
            remainder = (
                command[:location_search.start()]
                + " "
                + command[location_search.end():]
            )

        remainder = re.sub(r"\s+", " ", remainder).strip()

        # 2) Con la ubicación ya fuera, extraer el nombre de lo que queda.
        name_match = re.match(
            rf"^(?:{verb_pattern})\s+(?:la\s+|una\s+)?carpeta\s*"
            r"(?:llamada\s+|que\s+se\s+llame\s+)?(.*)$",
            remainder
        )

        if not name_match:
            return None, None

        name = name_match.group(1).strip()

        return (name or None), location

    def _control_playback(self, action):
        """
        Controla play/pausa/stop/siguiente/anterior.

        Prefiere hablarle DIRECTO a Winamp (por su API propia) si
        está abierto, porque las teclas multimedia globales de
        Windows no siempre le llegan de forma confiable según su
        configuración. Si Winamp no está abierto, usa esas teclas
        globales normales (funcionan con Spotify, el navegador,
        Windows Media Player, VLC, etc.)
        """

        if self.winamp.is_running():

            try:

                if action == "play":
                    ok = self.winamp.resume()
                    label = "Reproduciendo"
                elif action == "pause":
                    ok = self.winamp.pause()
                    label = "Pausado"
                elif action == "stop":
                    ok = self.winamp.stop()
                    label = "Detenido"
                elif action == "next":
                    ok = self.winamp.next_track()
                    label = "Siguiente canción"
                elif action == "previous":
                    ok = self.winamp.previous_track()
                    label = "Canción anterior"
                else:
                    ok = False
                    label = ""

                if ok:
                    return f"{label} en Winamp."

            except Exception as error:

                print(
                    "ERROR CONTROLANDO WINAMP:",
                    error
                )

            # Si Winamp está abierto pero la comunicación falló,
            # se sigue de largo al respaldo de teclas globales.

        if action == "play":
            return self.media.play()
        if action == "pause":
            return self.media.pause()
        if action == "stop":
            return self.media.pause()
        if action == "next":
            return self.media.next()
        if action == "previous":
            return self.media.previous()

        return "No pude controlar la reproducción."

    # =========================================================
    # COMANDOS LOCALES
    # =========================================================

    def handle_local_command(self, command):

        # Se guarda tal cual, ANTES de pasar a minúsculas, porque las
        # contraseñas de Wi-Fi son sensibles a mayúsculas/minúsculas
        # (ver el bloque de confirmación "wifi_password" más abajo).
        original_command = str(command).strip()

        command = command.lower().strip()

        # =====================================================
        # CONFIRMACIÓN DE DESINSTALACIÓN PENDIENTE
        # Si Eco ya preguntó "¿quieres desinstalar X?", esta
        # respuesta corta confirma (o cancela) esa acción específica.
        # Solo aplica si hay algo realmente pendiente, para no
        # interceptar un "sí" normal en otro contexto.
        # =====================================================

        if self.pending_confirmation:

            # Caso especial: no es un sí/no, es "dime la contraseña".
            # Cualquier cosa que diga el usuario (que no sea cancelar)
            # se toma TAL CUAL como la contraseña — por eso se revisa
            # antes que el resto, y por eso se usa original_command
            # (con mayúsculas/minúsculas reales) en vez de command.
            if self.pending_confirmation["type"] == "wifi_password":

                pending = self.pending_confirmation

                cancel_words = {
                    "no", "cancela", "cancelar", "mejor no", "olvidalo",
                    "olvídalo", "detente", "para"
                }

                if command in cancel_words:
                    self.pending_confirmation = None
                    response = "Está bien, no me conecto."
                else:
                    self.pending_confirmation = None
                    try:
                        response = self.wifi.connect(
                            pending["ssid"], password=original_command
                        )
                    except Exception as error:
                        print("ERROR CONECTANDO WIFI:", error)
                        response = f"No pude conectarme a {pending['ssid']}."

                print("ECO:", response)

                self._update_window(
                    intent="CONNECT_WIFI",
                    target=pending.get("ssid", ""),
                    response=response,
                    status="● ECO LISTA"
                )

                try:
                    self.speaker.speak(response)
                except Exception:
                    pass

                return True

            confirm_words = {
                "si", "sí", "confirmo", "confirmado", "hazlo",
                "adelante", "dale", "sisi", "si si"
            }

            cancel_words = {
                "no", "cancela", "cancelar", "mejor no", "olvidalo",
                "olvídalo", "detente", "para"
            }

            if command in confirm_words:

                pending = self.pending_confirmation
                self.pending_confirmation = None

                print()
                print(
                    "LOCAL: CONFIRMAR ACCIÓN ->",
                    pending
                )

                try:
                    if pending["type"] == "uninstall":
                        response = self.windows.uninstall_program(
                            pending["target"], confirmed=True
                        )
                        response_intent = "UNINSTALL_PROGRAM"
                    elif pending["type"] == "delete_folder":
                        response = self.windows.delete_folder(
                            pending["target"],
                            location=pending.get("location"),
                            confirmed=True
                        )
                        response_intent = "DELETE_FOLDER"
                    elif pending["type"] == "learn_offer":
                        # Paso 1 de 2: el usuario aceptó que Eco
                        # INTENTE generar código para esto. Todavía no
                        # se guarda ni se ejecuta nada — solo se prepara
                        # y se pide una segunda confirmación explícita
                        # (ver SkillLearner.prepare_skill).
                        prepared, summary = self.skill_learner.prepare_skill(
                            pending["description"]
                        )
                        if prepared:
                            self.pending_confirmation = {
                                "type": "learn_confirm",
                                "prepared": prepared,
                            }
                            response = (
                                summary
                                + " ¿Guardo esta habilidad y la ejecuto ahora?"
                            )
                        else:
                            response = (
                                summary
                                or "No pude generar una forma de hacer eso."
                            )
                        response_intent = "LEARN_SKILL_PREPARED"
                    elif pending["type"] == "learn_confirm":
                        # Paso 2 de 2: recién aquí se guarda el código en
                        # disco y se ejecuta, nunca antes de este punto.
                        response = self.skill_learner.confirm_and_save(
                            pending["prepared"]
                        )
                        response_intent = "LEARN_SKILL_SAVED"
                    else:
                        response = "No supe qué confirmar."
                        response_intent = "UNKNOWN"
                except Exception as error:
                    print("ERROR CONFIRMANDO ACCIÓN:", error)
                    response = "No pude completar la acción."
                    response_intent = "UNKNOWN"

                print("ECO:", response)

                self._update_window(
                    intent=response_intent,
                    target=pending.get("target", ""),
                    response=response,
                    status="● ECO LISTA"
                )

                try:
                    self.speaker.speak(response)
                except Exception:
                    pass

                return True

            if command in cancel_words:

                self.pending_confirmation = None

                response = "Está bien, no hago nada."

                print("ECO:", response)

                try:
                    self.speaker.speak(response)
                except Exception:
                    pass

                return True

        # =====================================================
        # EJECUTAR APLICACIÓN DEL ESCRITORIO
        # Ejemplo: "ejecuta Steam del escritorio". Esto busca
        # directamente accesos .lnk y archivos .exe del Escritorio,
        # sin necesitar que la aplicación ya esté en el catálogo.
        # =====================================================

        desktop_app_match = re.match(
            r"^(?:abre|abrir|ejecuta|ejecutar|inicia|iniciar)\s+(.+?)\s+"
            r"(?:del|desde\s+el|en\s+el)\s+escritorio$",
            command
        )

        if desktop_app_match:
            target = desktop_app_match.group(1).strip()
            if target:
                print("LOCAL: EJECUTAR DESDE ESCRITORIO ->", target)
                try:
                    response = self.windows.open_desktop_application(target)
                except Exception as error:
                    print("ERROR EJECUTANDO DESDE ESCRITORIO:", error)
                    response = f"No pude ejecutar {target} desde el Escritorio."

                print("ECO:", response)
                self._update_window(
                    intent="OPEN_DESKTOP_APPLICATION",
                    target=target,
                    response=response,
                    status="● ECO LISTA"
                )
                try:
                    self.speaker.speak(response)
                except Exception:
                    pass
                return True

        # =====================================================
        # PIN Y CONTRASEÑA DE WINDOWS
        # Windows no permite cambiar credenciales sin que la
        # persona se autentique, por eso Eco abre la pantalla
        # oficial donde el usuario completa el cambio.
        # =====================================================

        sign_in_match = re.search(
            r"\b(?:cambia|cambiar|modifica|modificar|configura|configurar|"
            r"abre)\b.*\b(?:pin|contrase[nñ]a|password)\b",
            command
        )

        if sign_in_match:
            print("LOCAL: OPCIONES DE INICIO DE SESIÓN")
            try:
                response = self.windows.open_sign_in_options()
            except Exception as error:
                print("ERROR ABRIENDO OPCIONES DE INICIO:", error)
                response = "No pude abrir las opciones de inicio de sesión de Windows."

            print("ECO:", response)
            self._update_window(
                intent="OPEN_SIGN_IN_OPTIONS",
                target="PIN de Windows",
                response=response,
                status="● ECO LISTA"
            )
            try:
                self.speaker.speak(response)
            except Exception:
                pass
            return True

        # =====================================================
        # INSTALAR PROGRAMA (vía winget)
        # =====================================================

        install_match = re.match(
            r"^(?:instala|instalar|descarga\s+e\s+instala)"
            r"\s+(?:el\s+programa\s+|la\s+aplicaci[oó]n\s+)?(.+)$",
            command
        )

        if install_match:

            name = install_match.group(1).strip()

            if name:

                print()
                print(
                    "LOCAL: INSTALAR ->",
                    name
                )

                try:
                    self.speaker.speak(
                        f"Instalando {name}, esto puede tardar unos minutos."
                    )
                except Exception:
                    pass

                try:
                    response = self.windows.install_program(name)
                except Exception as error:
                    print("ERROR INSTALANDO:", error)
                    response = f"No pude instalar {name}."

                print("ECO:", response)

                self._update_window(
                    intent="INSTALL_PROGRAM",
                    target=name,
                    response=response,
                    status="● ECO LISTA"
                )

                try:
                    self.speaker.speak(response)
                except Exception:
                    pass

                return True

        # =====================================================
        # DESINSTALAR PROGRAMA
        # =====================================================

        uninstall_match = re.match(
            r"^(?:desinstala|desinstalar|elimina|eliminar)"
            r"\s+(?:el\s+programa\s+|la\s+aplicaci[oó]n\s+)?"
            r"(?!(?:la\s+)?carpeta\b)(.+)$",
            command
        )

        if uninstall_match:

            target = uninstall_match.group(1).strip()

            if target:

                print()
                print(
                    "LOCAL: DESINSTALAR ->",
                    target
                )

                try:
                    response = self.windows.uninstall_program(
                        target, confirmed=False
                    )
                except Exception as error:
                    print("ERROR DESINSTALANDO:", error)
                    response = "No pude buscar ese programa."

                if response.startswith("CONFIRMATION_REQUIRED:"):

                    self.pending_confirmation = {
                        "type": "uninstall",
                        "target": target
                    }
                    spoken = response.replace(
                        "CONFIRMATION_REQUIRED:", ""
                    ).strip()

                    print("ECO:", spoken)

                    self._update_window(
                        intent="UNINSTALL_PROGRAM",
                        target=target,
                        response=spoken,
                        status="● ESPERANDO CONFIRMACIÓN"
                    )

                    try:
                        self.speaker.speak(spoken)
                    except Exception:
                        pass

                else:

                    print("ECO:", response)

                    try:
                        self.speaker.speak(response)
                    except Exception:
                        pass

                return True

        # =====================================================
        # CREAR CARPETA
        # =====================================================

        folder_name, folder_location = self._parse_folder_command(
            command, ("crea", "crear", "haz", "hazme")
        )

        if folder_name is not None:

            if not folder_name:

                response = "¿Cómo quieres que se llame la carpeta?"

                print("ECO:", response)

                try:
                    self.speaker.speak(response)
                except Exception:
                    pass

                return True

            print()
            print(
                "LOCAL: CREAR CARPETA ->",
                folder_name,
                "EN",
                folder_location or "escritorio"
            )

            try:
                response = self.windows.create_folder(folder_name, folder_location)
            except Exception as error:
                print("ERROR CREANDO CARPETA:", error)
                response = "No pude crear la carpeta."

            print("ECO:", response)

            self._update_window(
                intent="CREATE_FOLDER",
                target=folder_name,
                response=response,
                status="● ECO LISTA"
            )

            try:
                self.speaker.speak(response)
            except Exception:
                pass

            return True

        # =====================================================
        # BORRAR CARPETA (a la papelera de reciclaje)
        # =====================================================

        delete_name, delete_location = self._parse_folder_command(
            command, ("borra", "borrar", "elimina", "eliminar")
        )

        if delete_name is not None:

            name = delete_name
            location = delete_location

            if name:

                print()
                print(
                    "LOCAL: BORRAR CARPETA ->",
                    name,
                    "EN",
                    location or "(buscar en todas)"
                )

                try:
                    response = self.windows.delete_folder(
                        name, location=location, confirmed=False
                    )
                except Exception as error:
                    print("ERROR BORRANDO CARPETA:", error)
                    response = "No pude buscar esa carpeta."

                if response.startswith("CONFIRMATION_REQUIRED:"):

                    self.pending_confirmation = {
                        "type": "delete_folder",
                        "target": name,
                        "location": location
                    }
                    spoken = response.replace(
                        "CONFIRMATION_REQUIRED:", ""
                    ).strip()

                    print("ECO:", spoken)

                    self._update_window(
                        intent="DELETE_FOLDER",
                        target=name,
                        response=spoken,
                        status="● ESPERANDO CONFIRMACIÓN"
                    )

                    try:
                        self.speaker.speak(spoken)
                    except Exception:
                        pass

                else:

                    print("ECO:", response)

                    try:
                        self.speaker.speak(response)
                    except Exception:
                        pass

                return True

        # =====================================================
        # WINAMP — nombre o número de canción
        # Se revisa ANTES de dividir por conectores, porque
        # "abre winamp y reproduce X" debe tratarse como una sola
        # orden (abrir + reproducir EN Winamp), no como "abre
        # winamp" + "reproduce X" por separado (eso mandaría X a
        # buscarse en YouTube en vez de en Winamp).
        # =====================================================

        winamp_target = self._extract_winamp_target(command)

        if winamp_target is not None:

            kind, value = winamp_target

            print()
            print(
                "LOCAL: WINAMP ->",
                kind,
                value
            )

            try:

                if kind == "number":
                    response = self.winamp.play_by_number(value)
                else:
                    response = self.winamp.play_by_name(value)

                if response:

                    print(
                        "ECO:",
                        response
                    )

                    self._update_window(
                        intent="PLAY_MEDIA",
                        target=str(value),
                        response=response,
                        status="● ECO LISTA"
                    )

                    try:
                        self.speaker.speak(response)
                    except Exception:
                        pass

            except Exception as error:

                print(
                    "ERROR WINAMP:",
                    error
                )

            return True

        # =====================================================
        # SISTEMAS PERSONALIZADOS (páginas configuradas por el
        # usuario en windows/controller.py: self.custom_systems)
        #
        # Va ANTES de "ÓRDENES COMPUESTAS" (justo abajo) a propósito:
        # ese bloque parte la frase por "y", así que "abre sistema 1
        # y 2" se partiría en "abre sistema 1" y "2" sueltos. Aquí se
        # extraen TODOS los números de una vez, sin importar cómo
        # estén conectados.
        # =====================================================

        system_match = re.search(
            r"\babre\s+(?:el\s+|los\s+)?sistemas?\s+(.+)$",
            command
        )

        if system_match:

            raw = system_match.group(1)
            raw = raw.replace("uno", "1").replace("dos", "2")
            numbers = list(dict.fromkeys(re.findall(r"[12]", raw)))

            print()
            print("LOCAL: ABRIR SISTEMA(S) ->", numbers)

            if not numbers:
                response = "¿Cuál sistema, el 1 o el 2?"
            else:
                try:
                    response = self.windows.open_system(numbers)
                except Exception as error:
                    print("ERROR ABRIENDO SISTEMA:", error)
                    response = "No pude abrir el sistema."

            print("ECO:", response)

            self._update_window(
                intent="OPEN_SYSTEM",
                target=", ".join(numbers),
                response=response,
                status="● ECO LISTA"
            )

            try:
                self.speaker.speak(response)
            except Exception:
                pass

            return True

        # =====================================================
        # ÓRDENES COMPUESTAS
        # "abre winamp y reproduce bad bunny" -> se procesa cada
        # parte por separado. Si AMBAS partes se resuelven de
        # forma local, ninguna toca a Ollama.
        # =====================================================

        connector_match = re.split(
            r"\s+(?:y luego|y despu[eé]s|despu[eé]s|luego|y)\s+",
            command
        )

        if len(connector_match) > 1:

            any_handled = False

            for part in connector_match:

                part = part.strip()

                if not part:
                    continue

                if self.handle_local_command(part):
                    any_handled = True

            if any_handled:
                return True

        # =====================================================
        # APAGAR PC
        # =====================================================

        shutdown_commands = [
            "apaga la pc",
            "apaga el pc",
            "apaga mi pc",
            "apaga mi computadora",
            "apaga la computadora",
            "apaga el ordenador",
            "apaga mi ordenador",
            "apagar la pc",
            "apagar el pc",
            "apagar mi pc",
            "apagar la computadora",
            "apagar el ordenador",
            "apagar computadora",
            "apagar ordenador",
            "apaga el equipo",
            "apagar el equipo",
            "apaga mi equipo",
            "apagar mi equipo",
            "shutdown pc",
            "shutdown"
        ]

        if command in shutdown_commands:

            print()
            print("LOCAL: APAGAR PC")

            try:
                self.speaker.speak(
                    "Apagando la computadora."
                )
            except Exception:
                pass

            try:

                subprocess.Popen(
                    [
                        "shutdown",
                        "/s",
                        "/t",
                        "3"
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL
                )

                print(
                    "ECO: Apagando la computadora "
                    "en 3 segundos."
                )

            except Exception as error:

                print(
                    "ERROR APAGANDO PC:",
                    error
                )

            return True

        # =====================================================
        # REINICIAR PC
        # =====================================================

        restart_commands = [
            "reinicia la pc",
            "reinicia el pc",
            "reinicia mi pc",
            "reinicia la computadora",
            "reinicia mi computadora",
            "reinicia el ordenador",
            "reinicia mi ordenador",
            "reiniciar la pc",
            "reiniciar el pc",
            "reiniciar mi pc",
            "reiniciar la computadora",
            "reiniciar el ordenador",
            "reinicia el equipo",
            "reiniciar el equipo",
            "reinicia mi equipo",
            "reiniciar mi equipo",
            "restart pc"
        ]

        if command in restart_commands:

            print()
            print("LOCAL: REINICIAR PC")

            try:
                self.speaker.speak(
                    "Reiniciando la computadora."
                )
            except Exception:
                pass

            try:

                subprocess.Popen(
                    [
                        "shutdown",
                        "/r",
                        "/t",
                        "3"
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL
                )

                print(
                    "ECO: Reiniciando la computadora "
                    "en 3 segundos."
                )

            except Exception as error:

                print(
                    "ERROR REINICIANDO PC:",
                    error
                )

            return True

        # =====================================================
        # CANCELAR APAGADO
        # =====================================================

        cancel_shutdown_commands = [
            "cancela el apagado",
            "cancelar el apagado",
            "cancela apagado",
            "cancelar apagado",
            "cancela el reinicio",
            "cancelar el reinicio",
            "cancela reinicio",
            "cancelar reinicio",
            "cancela el shutdown",
            "cancelar shutdown"
        ]

        if command in cancel_shutdown_commands:

            print()
            print(
                "LOCAL: CANCELAR APAGADO"
            )

            try:

                subprocess.Popen(
                    [
                        "shutdown",
                        "/a"
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL
                )

                print(
                    "ECO: Apagado cancelado."
                )

                try:
                    self.speaker.speak(
                        "Apagado cancelado."
                    )
                except Exception:
                    pass

            except Exception as error:

                print(
                    "ERROR CANCELANDO APAGADO:",
                    error
                )

            return True

        # =====================================================
        # CERRAR SESIÓN
        # Debe revisarse ANTES del patrón genérico "cierra X" (más
        # abajo, en CERRAR PROGRAMAS): sin este bloque, "cierra
        # sesión" caía ahí y Eco intentaba cerrar un PROCESO
        # llamado "sesión" (que nunca existe) en vez de cerrar la
        # sesión de Windows — por eso el comando nunca funcionaba.
        # =====================================================

        if re.search(r"\b(cierra|cerrar)\b.*\bsesi[oó]n\b", command):

            print()
            print("LOCAL: CERRAR SESIÓN")

            try:
                response = self.windows.logout_pc()
            except Exception as error:
                print("ERROR CERRANDO SESIÓN:", error)
                response = "No pude cerrar la sesión."

            print("ECO:", response)

            try:
                self.speaker.speak(response)
            except Exception:
                pass

            return True

        # =====================================================
        # ACTUALIZACIONES
        # =====================================================

        update_commands = [
            "busca actualizaciones",
            "buscar actualizaciones",
            "hay actualizaciones",
            "revisa actualizaciones",
            "actualízate",
            "actualizate"
        ]

        # "actualiza eco" / "actualizar eco" (+ variantes fonéticas del nombre)
        for nombre in self.WAKE_WORD_VARIANTS:
            update_commands.append(f"actualiza {nombre}")
            update_commands.append(f"actualizar {nombre}")

        if command in update_commands:

            print()
            print("LOCAL: BUSCAR ACTUALIZACIONES")

            try:

                self.speaker.speak(
                    "Buscando actualizaciones, dame un momento."
                )
            except Exception:
                pass

            try:

                response = self.updater.check_download_and_apply()

                print(
                    "ECO:",
                    response
                )

                self._update_window(
                    intent="UPDATE",
                    target="",
                    response=response,
                    status="● ECO LISTA"
                )

                try:
                    self.speaker.speak(
                        response
                    )
                except Exception:
                    pass

            except Exception as error:

                print(
                    "ERROR BUSCANDO ACTUALIZACIONES:",
                    error
                )

            return True

        # =====================================================
        # WHATSAPP (envía / lee / borra, vía core/whatsapp_client.py)
        #
        # La primera vez que se use cualquiera de estos tres, se abre
        # un navegador para que escanees el código QR con tu teléfono
        # — puede tardar. Ver whatsapp_client.py para las advertencias
        # de términos de servicio y fragilidad de la interfaz.
        #
        # Estos patrones se probaron contra decenas de formas de decir
        # lo mismo (orden de "un mensaje"/"por whatsapp"/"a NOMBRE"
        # intercambiado, con y sin "whatsapp" explícito, con distintos
        # verbos y separadores) antes de dejarlos aquí — no son un
        # primer intento a ciegas.
        # =====================================================

        WHATSAPP_MENTION = r"(?:whatsapp|wasap|guasap|wsp)"

        # "un [mensaje] [de/por] whatsapp": cada pieza es opcional por
        # separado, y este mismo bloque se usa TANTO antes de "a
        # NOMBRE" como después, porque la gente lo dice de las dos
        # formas ("mándale un mensaje a Juan por whatsapp..." Y
        # "mándale a Juan un mensaje por whatsapp...").
        WHATSAPP_CONNECTOR = (
            rf"(?:un\s+)?(?:mensaje\s+)?(?:(?:de|por)\s+)?"
            rf"(?:{WHATSAPP_MENTION}\s*)?"
        )

        # \b al final de cada palabra para que "diciendo" no matchee
        # como prefijo de "diciéndole" y se coma parte del mensaje.
        WHATSAPP_SEPARATOR = (
            r"(?:diciendo\b|dici[eé]ndole\b|que\s+diga\b|"
            r"con\s+el\s+mensaje\b|que\b|[:\-])\s*"
        )

        send_whatsapp_match = re.search(
            rf"^(?:por\s+{WHATSAPP_MENTION}\s+)?"
            r"(?:env[ií]a(?:le)?|manda(?:le)?|escr[ií]be(?:le)?|"
            r"d[ií]le|dic[ée]le|(?:un\s+)?mensaje)\s+"
            rf"{WHATSAPP_CONNECTOR}a\s+(.+?)\s+"
            rf"{WHATSAPP_CONNECTOR}{WHATSAPP_SEPARATOR}(.+)$",
            command
        )

        if send_whatsapp_match:

            contact = send_whatsapp_match.group(1).strip()
            message = send_whatsapp_match.group(2).strip()

            print()
            print("LOCAL: ENVIAR WHATSAPP ->", contact, "|", message)

            try:
                response = self.whatsapp.send_message(contact, message)
            except Exception as error:
                print("ERROR WHATSAPP (ENVIAR):", error)
                response = f"No pude enviar el WhatsApp a {contact}."

            print("ECO:", response)

            self._update_window(
                intent="SEND_WHATSAPP",
                target=contact,
                response=response,
                status="● ECO LISTA"
            )

            try:
                self.speaker.speak(response)
            except Exception:
                pass

            return True

        read_whatsapp_match = (
            re.search(
                rf"^(?:l[eé]e(?:me)?|revisa(?:me)?)\s+"
                rf"(?:los\s+|el\s+)?(?:[uú]ltimos\s+)?"
                rf"(?:mensajes|{WHATSAPP_MENTION})\s+de\s+"
                rf"(.+?)(?:\s+(?:en|por)\s+{WHATSAPP_MENTION})?$",
                command
            )
            or re.search(
                rf"^(?:por\s+{WHATSAPP_MENTION}\s+)?(?:dime\s+)?"
                r"qu[eé]\s+me\s+(?:escribi[oó]|mand[oó]|envi[oó]|dijo)\s+"
                rf"(.+?)(?:\s+por\s+{WHATSAPP_MENTION})?$",
                command
            )
        )

        if read_whatsapp_match:

            contact = read_whatsapp_match.group(1).strip()

            print()
            print("LOCAL: LEER WHATSAPP ->", contact)

            try:
                messages = self.whatsapp.read_last_messages(contact)
            except Exception as error:
                print("ERROR WHATSAPP (LEER):", error)
                messages = [f"No pude leer los mensajes de {contact}."]

            response = (
                f"Esto es lo último con {contact} por WhatsApp: "
                + " / ".join(messages)
            )

            print("ECO:", response)

            self._update_window(
                intent="READ_WHATSAPP",
                target=contact,
                response=response,
                status="● ECO LISTA"
            )

            try:
                self.speaker.speak(response)
            except Exception:
                pass

            return True

        delete_whatsapp_match = re.search(
            rf"^borra(?:me)?\s+(?:el|mi)\s+[uú]ltimo\s+"
            rf"(?:mensaje|{WHATSAPP_MENTION})\s+"
            rf"(?:de\s+{WHATSAPP_MENTION}\s+)?"
            r"(?:que\s+le\s+(?:envi[eé]|mand[eé])\s+a\s+|a\s+)"
            rf"(.+?)(?:\s+por\s+{WHATSAPP_MENTION})?$",
            command
        )

        if delete_whatsapp_match:

            contact = delete_whatsapp_match.group(1).strip()
            # Por defecto se borra SOLO PARA TI (reversible únicamente
            # en tu equipo). Solo se borra "para todos" si lo pides
            # explícitamente — es lo que de verdad borra el mensaje del
            # otro lado, y WhatsApp además le muestra un aviso a la
            # otra persona de que borraste algo.
            for_everyone = bool(
                re.search(r"para\s+todos|a\s+todos", command)
            )

            print()
            print(
                "LOCAL: BORRAR WHATSAPP ->", contact,
                "| para_todos =", for_everyone
            )

            try:
                response = self.whatsapp.delete_last_sent_message(
                    contact, for_everyone=for_everyone
                )
            except Exception as error:
                print("ERROR WHATSAPP (BORRAR):", error)
                response = f"No pude borrar el mensaje de {contact}."

            print("ECO:", response)

            self._update_window(
                intent="DELETE_WHATSAPP",
                target=contact,
                response=response,
                status="● ECO LISTA"
            )

            try:
                self.speaker.speak(response)
            except Exception:
                pass

            return True

        # =====================================================
        # WIFI (vía windows/wifi.py — netsh, sin dependencias nuevas)
        # =====================================================

        if re.search(
            r"\b(lista|listame|muestrame|dime|que)\b.*"
            r"\b(wifis?|redes?(?:\s+de\s+wifi)?)\b.*"
            r"(?:disponibles?|cerca|hay)?$",
            command
        ):

            print()
            print("LOCAL: LISTAR WIFI")

            try:
                response = self.wifi.list_networks_text()
            except Exception as error:
                print("ERROR LISTANDO WIFI:", error)
                response = "No pude listar las redes Wi-Fi."

            print("ECO:", response)

            self._update_window(
                intent="LIST_WIFI",
                response=response,
                status="● ECO LISTA"
            )

            try:
                self.speaker.speak(response)
            except Exception:
                pass

            return True

        connect_wifi_match = re.search(
            r"\bconecta(?:te)?\b\s+(?:al?\s+)?(?:la\s+red\s+|el\s+wifi\s+|"
            r"la\s+wifi\s+)?(.+?)\s*(?:\(?\s*wifi\s*\)?)?$",
            command
        )

        if connect_wifi_match and "wifi" in command:

            ssid = connect_wifi_match.group(1).strip()
            # Por si quedó "wifi" pegado al nombre porque venía antes
            # del nombre de la red en vez de después.
            ssid = re.sub(r"\bwifi\b", "", ssid).strip()

            print()
            print("LOCAL: CONECTAR WIFI ->", ssid)

            if not ssid:
                response = "¿A qué red Wi-Fi quieres que me conecte?"
            elif self.wifi.is_network_secured(ssid):
                self.pending_confirmation = {
                    "type": "wifi_password",
                    "ssid": ssid,
                }
                response = (
                    f"La red {ssid} tiene seguridad. ¿Cuál es la "
                    "contraseña?"
                )
            else:
                try:
                    response = self.wifi.connect(ssid)
                except Exception as error:
                    print("ERROR CONECTANDO WIFI:", error)
                    response = f"No pude conectarme a {ssid}."

            print("ECO:", response)

            self._update_window(
                intent="CONNECT_WIFI",
                target=ssid,
                response=response,
                status="● ECO LISTA"
            )

            try:
                self.speaker.speak(response)
            except Exception:
                pass

            return True

        # =====================================================
        # BLUETOOTH (vía windows/bluetooth.py — dispositivos YA
        # EMPAREJADOS solamente; ver el aviso al inicio de ese
        # archivo sobre por qué no empareja dispositivos nuevos)
        # =====================================================

        if re.search(
            r"\b(lista|listame|muestrame|dime|que)\b.*"
            r"\b(dispositivos?\s+)?bluetooth\b",
            command
        ):

            print()
            print("LOCAL: LISTAR BLUETOOTH")

            try:
                response = self.bluetooth.list_devices_text()
            except Exception as error:
                print("ERROR LISTANDO BLUETOOTH:", error)
                response = "No pude listar los dispositivos Bluetooth."

            print("ECO:", response)

            self._update_window(
                intent="LIST_BLUETOOTH",
                response=response,
                status="● ECO LISTA"
            )

            try:
                self.speaker.speak(response)
            except Exception:
                pass

            return True

        connect_bluetooth_match = re.search(
            r"\bconecta(?:te)?\b\s+(?:al?\s+)?(?:el\s+bluetooth\s+|"
            r"por\s+bluetooth\s+a\s+)?(.+?)\s*(?:\(?\s*bluetooth\s*\)?)?$",
            command
        )

        if connect_bluetooth_match and "bluetooth" in command:

            device_name = connect_bluetooth_match.group(1).strip()
            device_name = re.sub(
                r"\bbluetooth\b", "", device_name
            ).strip()

            print()
            print("LOCAL: CONECTAR BLUETOOTH ->", device_name)

            try:
                response = self.bluetooth.connect(device_name)
            except Exception as error:
                print("ERROR CONECTANDO BLUETOOTH:", error)
                response = f"No pude conectarme a {device_name}."

            print("ECO:", response)

            self._update_window(
                intent="CONNECT_BLUETOOTH",
                target=device_name,
                response=response,
                status="● ECO LISTA"
            )

            try:
                self.speaker.speak(response)
            except Exception:
                pass

            return True

        # =====================================================
        # SISTEMAS (URLs fijas configuradas por el usuario)
        # "abre sistema 1", "abre sistema 2", "abre sistema 1 y 2",
        # "abre sistema 1 y dos", "abre ambos sistemas"
        # =====================================================

        SISTEMA_URLS = {
            "1": "https://dldservicio.smartolt.com/auth/login",
            "2": "https://dldservicio.net/admin/login",
        }

        sistema_match = re.search(
            r"\b(?:abre|abrir)\b.*\bsistemas?\b\s*(.*)$", command
        )

        if sistema_match:

            resto = sistema_match.group(1)
            resto = re.sub(r"\buno\b", "1", resto)
            resto = re.sub(r"\bdos\b", "2", resto)

            numeros = sorted(set(re.findall(r"\b[12]\b", resto)))

            if not numeros and re.search(
                r"\b(ambos|los\s+dos|todos)\b", resto
            ):
                numeros = ["1", "2"]

            if numeros:

                print()
                print("LOCAL: ABRIR SISTEMA(S) ->", numeros)

                respuestas = [
                    self.windows.open_url(SISTEMA_URLS[n]) for n in numeros
                ]
                response = " ".join(respuestas)

                print("ECO:", response)

                self._update_window(
                    intent="OPEN_SISTEMA",
                    target=",".join(numeros),
                    response=response,
                    status="● ECO LISTA"
                )

                try:
                    self.speaker.speak(response)
                except Exception:
                    pass

                return True

        # =====================================================
        # SILENCIO
        # =====================================================

        mute_commands = [
            "silencio",
            "silenciar",
            "silencia",
            "mute",
            "pon silencio",
            "pon el silencio",
            "silencia la pc",
            "silencia el pc",
            "silencia la computadora",
            "silencia el ordenador"
        ]

        if command in mute_commands:

            print()
            print("LOCAL: SILENCIO")

            try:

                response = self.media.volume_mute()

                print(
                    "ECO:",
                    response
                )

                try:
                    self.speaker.speak(
                        response
                    )
                except Exception:
                    pass

            except Exception as error:

                print(
                    "ERROR AUDIO:",
                    error
                )

            return True

        # =====================================================
        # QUITAR SILENCIO
        # =====================================================

        unmute_commands = [
            "quita el silencio",
            "quitar el silencio",
            "quita silencio",
            "quitar silencio",
            "desactiva el silencio",
            "desactivar el silencio",
            "activa el sonido",
            "activar el sonido",
            "enciende el sonido",
            "enciende el audio",
            "quita el mute",
            "quitar el mute",
            "quita mute",
            "quitar mute",
            "desmutea",
            "desmutear",
            "desmute",
            "desactivar mute"
        ]

        if command in unmute_commands:

            print()
            print(
                "LOCAL: QUITAR SILENCIO"
            )

            try:

                response = self.media.volume_unmute()

                print(
                    "ECO:",
                    response
                )

                try:
                    self.speaker.speak(
                        response
                    )
                except Exception:
                    pass

            except Exception as error:

                print(
                    "ERROR AUDIO:",
                    error
                )

            return True

        # =====================================================
        # VOLUMEN ARRIBA
        # =====================================================

        volume_up_commands = [
            "sube el volumen",
            "subir el volumen",
            "aumenta el volumen",
            "aumentar el volumen",
            "más volumen",
            "mas volumen",
            "sube volumen",
            "subir volumen",
            "volumen arriba"
        ]

        if command in volume_up_commands:

            print()
            print(
                "LOCAL: VOLUMEN ARRIBA"
            )

            try:

                response = self.media.volume_up()

                print(
                    "ECO:",
                    response
                )

                try:
                    self.speaker.speak(
                        response
                    )
                except Exception:
                    pass

            except Exception as error:

                print(
                    "ERROR VOLUMEN:",
                    error
                )

            return True

        # =====================================================
        # VOLUMEN EXACTO
        # =====================================================

        volume_exact_match = re.match(
            r"^(?:baja|bajar|disminuye|disminuir|"
            r"sube|subir|aumenta|aumentar|pon|poner)"
            r"(?:\s+el)?\s+volumen\s+(?:a|en)\s+(\d{1,3})$",
            command
        )

        if volume_exact_match:

            percentage = int(
                volume_exact_match.group(1)
            )

            print()
            print(
                "LOCAL: VOLUMEN EXACTO ->",
                percentage
            )

            try:

                response = self.media.volume_set(
                    percentage
                )

                print(
                    "ECO:",
                    response
                )

                try:
                    self.speaker.speak(
                        response
                    )
                except Exception:
                    pass

            except Exception as error:

                print(
                    "ERROR VOLUMEN:",
                    error
                )

            return True

        # =====================================================
        # VOLUMEN ABAJO
        # =====================================================

        volume_down_commands = [
            "baja el volumen",
            "bajar el volumen",
            "disminuye el volumen",
            "disminuir el volumen",
            "menos volumen",
            "baja volumen",
            "bajar volumen",
            "volumen abajo"
        ]

        if command in volume_down_commands:

            print()
            print(
                "LOCAL: VOLUMEN ABAJO"
            )

            try:

                response = self.media.volume_down()

                print(
                    "ECO:",
                    response
                )

                try:
                    self.speaker.speak(
                        response
                    )
                except Exception:
                    pass

            except Exception as error:

                print(
                    "ERROR VOLUMEN:",
                    error
                )

            return True

        # =====================================================
        # PLAY
        # =====================================================

        play_commands = [
            "play",
            "reproduce",
            "reproducir",
            "reanuda",
            "reanudar",
            "continúa",
            "continua",
            "continúa la música",
            "continua la musica",
            "sigue"
        ]

        if command in play_commands:

            print()
            print("LOCAL: PLAY")

            try:

                response = self._control_playback("play")

                print(
                    "ECO:",
                    response
                )

                try:
                    self.speaker.speak(
                        response
                    )
                except Exception:
                    pass

            except Exception as error:

                print(
                    "ERROR PLAY:",
                    error
                )

            return True

        # =====================================================
        # PAUSA
        # =====================================================

        pause_commands = [
            "pausa",
            "pausar",
            "pausa la música",
            "pausa la musica",
            "pausa el video",
            "pausar el video",
            "ponlo en pausa"
        ]

        if command in pause_commands:

            print()
            print("LOCAL: PAUSA")

            try:

                response = self._control_playback("pause")

                print(
                    "ECO:",
                    response
                )

                try:
                    self.speaker.speak(
                        response
                    )
                except Exception:
                    pass

            except Exception as error:

                print(
                    "ERROR PAUSA:",
                    error
                )

            return True

        # =====================================================
        # SIGUIENTE
        # =====================================================

        next_commands = [
            "siguiente",
            "siguiente canción",
            "siguiente cancion",
            "siguiente video",
            "pasa a la siguiente"
        ]

        if command in next_commands:

            print()
            print("LOCAL: SIGUIENTE")

            try:

                response = self._control_playback("next")

                print(
                    "ECO:",
                    response
                )

                try:
                    self.speaker.speak(
                        response
                    )
                except Exception:
                    pass

            except Exception as error:

                print(
                    "ERROR SIGUIENTE:",
                    error
                )

            return True

        # =====================================================
        # ANTERIOR
        # =====================================================

        previous_commands = [
            "anterior",
            "canción anterior",
            "cancion anterior",
            "video anterior",
            "vuelve a la anterior"
        ]

        if command in previous_commands:

            print()
            print("LOCAL: ANTERIOR")

            try:

                response = self._control_playback("previous")

                print(
                    "ECO:",
                    response
                )

                try:
                    self.speaker.speak(
                        response
                    )
                except Exception:
                    pass

            except Exception as error:

                print(
                    "ERROR ANTERIOR:",
                    error
                )

            return True

        # =====================================================
        # STOP
        # =====================================================

        stop_commands = [
            "detener",
            "detén",
            "deten",
            "detener música",
            "detener musica",
            "detén la música",
            "deten la musica",
            "para la música",
            "para la musica",
            "para el video"
        ]

        if command in stop_commands:

            print()
            print("LOCAL: STOP")

            try:

                response = self._control_playback("stop")

                print(
                    "ECO:",
                    response
                )

                try:
                    self.speaker.speak(
                        response
                    )
                except Exception:
                    pass

            except Exception as error:

                print(
                    "ERROR STOP:",
                    error
                )

            return True

        # =====================================================
        # NORMALIZAR
        # =====================================================

        normalized = re.sub(
            r"[.,!¡?¿]+$",
            "",
            command
        ).strip()

        normalized = re.sub(
            r"\s+",
            " ",
            normalized
        )

        # =====================================================
        # YOUTUBE
        # =====================================================

        youtube_patterns = [

            r"^(?:busca|buscar|reproduce|reproducir|pon|poner|"
            r"toca|tocar|play)\s+(.+?)\s+en\s+youtube$",

            r"^(?:busca|buscar|reproduce|reproducir|pon|poner)\s+"
            r"(.+?)\s+(?:video|canción|cancion)\s+en\s+youtube$",

            r"^youtube\s+(.+)$"
        ]

        for pattern in youtube_patterns:

            match = re.match(
                pattern,
                normalized
            )

            if not match:
                continue

            query = match.group(1).strip()

            if not query:
                return True

            print()
            print(
                "LOCAL: YOUTUBE ->",
                query
            )

            try:

                response = self.router.search_youtube(
                    query
                )

                if response:

                    print(
                        "ECO:",
                        response
                    )

                    try:
                        self.speaker.speak(
                            response
                        )
                    except Exception:
                        pass

            except Exception as error:

                print(
                    "ERROR YOUTUBE:",
                    error
                )

            return True

        # =====================================================
        # GOOGLE
        # =====================================================

        google_patterns = [

            r"^(?:busca|buscar|búscame|buscame)\s+"
            r"(.+?)\s+en\s+google$",

            r"^google\s+(.+)$"
        ]

        for pattern in google_patterns:

            match = re.match(
                pattern,
                normalized
            )

            if not match:
                continue

            query = match.group(1).strip()

            if not query:
                return True

            print()
            print(
                "LOCAL: GOOGLE ->",
                query
            )

            try:

                response = self.router.search_google(
                    query
                )

                if response:

                    print(
                        "ECO:",
                        response
                    )

                    try:
                        self.speaker.speak(
                            response
                        )
                    except Exception:
                        pass

            except Exception as error:

                print(
                    "ERROR GOOGLE:",
                    error
                )

            return True

        # =====================================================
        # REPRODUCIR ALGO (sin decir "en youtube")
        # Atajo local para no pasar por el cerebro (Ollama) en el
        # comando más común de todos: "reproduce X", "pon X",
        # "toca X". Esto es lo que más se demoraba antes, porque
        # cada canción distinta era una frase nueva que el modelo
        # tenía que interpretar desde cero.
        # =====================================================

        play_query_match = re.match(
            r"^(?:por favor|porfavor|puedes|podrias|podrías|quiero que)?\s*"
            r"(?:reproduce|reproducir|pon|poner|toca|tocar|play)\s+(.+)$",
            normalized
        )

        if play_query_match:

            query = play_query_match.group(1).strip()

            if query:

                # Si lo que pide es un número o "canción número X",
                # es control de reproducción local (Winamp), NO una
                # búsqueda en YouTube — nadie busca "canción número
                # 5" en YouTube. Esto aplica aunque no diga "winamp".
                parsed_target = self._parse_winamp_number_or_name(query)

                if parsed_target and parsed_target[0] == "number":

                    print()
                    print(
                        "LOCAL: REPRODUCIR (número, asumiendo Winamp) ->",
                        parsed_target[1]
                    )

                    try:

                        response = self.winamp.play_by_number(
                            parsed_target[1]
                        )

                        if response:

                            print(
                                "ECO:",
                                response
                            )

                            self._update_window(
                                intent="PLAY_MEDIA",
                                target=parsed_target[1],
                                response=response,
                                status="● ECO LISTA"
                            )

                            try:
                                self.speaker.speak(
                                    response
                                )
                            except Exception:
                                pass

                    except Exception as error:

                        print(
                            "ERROR WINAMP:",
                            error
                        )

                    return True

                print()
                print(
                    "LOCAL: REPRODUCIR ->",
                    query
                )

                try:

                    response = self.router.search_youtube(
                        query
                    )

                    if response:

                        print(
                            "ECO:",
                            response
                        )

                        self._update_window(
                            intent="PLAY_MEDIA",
                            target=query,
                            response=response,
                            status="● ECO LISTA"
                        )

                        try:
                            self.speaker.speak(
                                response
                            )
                        except Exception:
                            pass

                except Exception as error:

                    print(
                        "ERROR REPRODUCIENDO:",
                        error
                    )

                return True

        # =====================================================
        # ABRIR PROGRAMAS
        # =====================================================

        FILLER_PREFIX = r"^(?:por favor|porfavor|puedes|podrias|podrías|quiero que|me puedes|me podrias|me podrías)?\s*"

        open_patterns = [
            FILLER_PREFIX + r"abre\s+(.+)$",
            FILLER_PREFIX + r"abrir\s+(.+)$",
            FILLER_PREFIX + r"ábreme\s+(.+)$",
            FILLER_PREFIX + r"abreme\s+(.+)$"
        ]

        for pattern in open_patterns:

            match = re.match(
                pattern,
                normalized
            )

            if not match:
                continue

            target = match.group(1).strip()

            if not target:
                return True

            print()
            print(
                "LOCAL: ABRIR ->",
                target
            )

            try:

                response = self.windows.open_program(
                    target
                )

                if response:

                    print(
                        "ECO:",
                        response
                    )

                    try:
                        self.speaker.speak(
                            response
                        )
                    except Exception:
                        pass

            except Exception as error:

                print(
                    "ERROR ABRIR:",
                    error
                )

            return True

        # =====================================================
        # CERRAR PROGRAMAS
        # =====================================================

        close_patterns = [
            FILLER_PREFIX + r"cierra\s+(.+)$",
            FILLER_PREFIX + r"cerrar\s+(.+)$"
        ]

        for pattern in close_patterns:

            match = re.match(
                pattern,
                normalized
            )

            if not match:
                continue

            target = match.group(1).strip()

            if not target:
                return True

            print()
            print(
                "LOCAL: CERRAR ->",
                target
            )

            try:

                response = self.windows.close_program(
                    target
                )

                if response:

                    print(
                        "ECO:",
                        response
                    )

                    try:
                        self.speaker.speak(
                            response
                        )
                    except Exception:
                        pass

            except Exception as error:

                print(
                    "ERROR CERRAR:",
                    error
                )

            return True

        return False

    # =========================================================
    # RESPONDER
    # =========================================================

    def respond(self, text):

        text = text.strip()

        if not text:
            return

        t0 = time.time()

        print()
        print(
            "ANALIZANDO:",
            text
        )

        self._update_window(
            listened=text,
            analysis=text,
            status="● PROCESANDO"
        )

        command = text.lower().strip()

        # =====================================================
        # COMANDOS LOCALES
        # =====================================================

        t_local_start = time.time()

        if self.handle_local_command(command):
            print(f"⏱ COMANDO LOCAL: {time.time() - t_local_start:.2f}s | TOTAL: {time.time() - t0:.2f}s")
            return

        print(f"⏱ (no era comando local, tardó {time.time() - t_local_start:.2f}s en descartarlo)")

        # Respuestas que Eco ya investigó antes. Se revisan antes
        # de llamar a Ollama o a internet, pero solo para preguntas:
        # una orden como "abre Chrome" nunca debe reutilizar una
        # respuesta factual guardada por coincidencia casual.
        is_question = "?" in text or command.startswith((
            "que ", "qué ", "quien ", "quién ", "como ", "cómo ",
            "cuando ", "cuándo ", "donde ", "dónde ", "cual ", "cuál ",
            "por que ", "por qué ", "para que ", "para qué "
        ))
        if is_question:
            try:
                remembered = self.learning_brain.remember_knowledge(text)
            except Exception as error:
                print("ERROR LEYENDO CONOCIMIENTO APRENDIDO:", error)
                remembered = None

            if remembered:
                response = remembered["answer"]
                print("ECO (APRENDIDO):", response)
                self._update_window(
                    intent="CONOCIMIENTO_APRENDIDO",
                    target="",
                    response=response,
                    status="● ECO LISTA"
                )
                try:
                    self.speaker.speak(response)
                except Exception:
                    pass
                return

        # =====================================================
        # CONVERSACIÓN
        # =====================================================

        try:

            conversation_response = (
                self.conversation.respond(text)
            )

        except Exception as error:

            print(
                "ERROR CONVERSACION:",
                error
            )

            conversation_response = None

        if conversation_response:

            print()
            print(
                "ECO:",
                conversation_response
            )

            self._update_window(
                intent="CONVERSACIÓN",
                target="",
                response=conversation_response,
                status="● ECO LISTA"
            )

            try:

                self.speaker.speak(
                    conversation_response
                )

            except Exception as error:

                print(
                    "ERROR VOZ:",
                    error
                )

            return

        # =====================================================
        # APRENDIZAJE
        # =====================================================

        try:

            if self.learning_brain.is_learning_request(
                text
            ):

                self._handle_learning(text)
                return

        except Exception as error:

            print(
                "ERROR APRENDIZAJE:",
                error
            )

        # =====================================================
        # MEMORIA APRENDIDA
        # =====================================================

        # -----------------------------------------------------
        # ATAJO: ordenes directas de sistema (apagar, reiniciar,
        # suspender, bloquear, cerrar sesion, cancelar apagado)
        # aunque la frase no sea exacta ("apaga la pc porfavor").
        # Router.detect_direct_command() ya sabia reconocer esto
        # por regex, pero antes se revisaba DESPUES de llamar a
        # Ollama, asi que no ahorraba nada de tiempo. Ahora se
        # revisa aqui, antes de tocar el cerebro para nada.
        # -----------------------------------------------------

        # -----------------------------------------------------
        # COMANDOS CONTEXTUALES ("hazlo de nuevo", "otra vez",
        # "repite eso", "vuelve a hacerlo"). Se revisan ANTES que
        # todo lo demás: reutilizan la última intención ya validada
        # (last_intent/last_target) sin generar ni ejecutar código
        # nuevo, y sin tocar a Ollama para nada.
        # -----------------------------------------------------

        context_reuse_result = None

        try:
            if self.context_resolver.is_context_command(text):

                resolver_context = {
                    "last_intent": self.memory.get_context("last_intent", ""),
                    "last_target": self.memory.get_context("last_target", ""),
                    "last_command": self.memory.get_context("last_command", ""),
                }

                context_reuse_result = self.context_resolver.resolve(
                    text, resolver_context
                )

        except Exception as error:
            print("ERROR RESOLVIENDO CONTEXTO:", error)
            context_reuse_result = None

        if context_reuse_result:

            print()
            print(
                "LOCAL: REUTILIZANDO CONTEXTO ->",
                context_reuse_result
            )

        direct_system_intent = self.router.detect_direct_command(text)

        learned = None

        if context_reuse_result:

            result = context_reuse_result

        elif direct_system_intent:

            print()
            print(
                "LOCAL: ORDEN DIRECTA DE SISTEMA ->",
                direct_system_intent
            )

            result = {
                "intent": direct_system_intent,
                "target": "pc",
                "confidence": 1.0
            }

        else:

            try:

                learned = self.learning_brain.remember(
                    text
                )

            except Exception as error:

                print(
                    "ERROR BUSCANDO APRENDIZAJE:",
                    error
                )

                learned = None

        if context_reuse_result or direct_system_intent:

            pass

        elif learned:

            result = {
                "intent": learned.get(
                    "intent",
                    "UNKNOWN"
                ),
                "target": learned.get(
                    "target",
                    ""
                ),
                "confidence": learned.get(
                    "confidence",
                    1.0
                )
            }

        else:

            # Últimos intercambios reales (pregunta + respuesta), para
            # que el cerebro pueda resolver preguntas de seguimiento
            # ("¿y cuándo murió?" después de "¿quién fue X?") sin que
            # el usuario tenga que repetir el tema cada vez.
            try:
                recent_turns = self.memory.get_history(amount=4)
            except Exception as error:
                print("ERROR LEYENDO HISTORIAL:", error)
                recent_turns = []

            history_lines = []
            for turn in recent_turns:
                user_line = str(turn.get("user", "")).strip()
                assistant_line = str(turn.get("assistant", "")).strip()
                if user_line or assistant_line:
                    history_lines.append(f"Usuario: {user_line}")
                    history_lines.append(f"Eco: {assistant_line}")

            recent_history_text = (
                "\n".join(history_lines) if history_lines else "(sin historial reciente)"
            )

            context = {
                "last_target":
                    self.memory.get_context(
                        "last_target",
                        ""
                    ),

                "last_intent":
                    self.memory.get_context(
                        "last_intent",
                        ""
                    ),

                "last_command":
                    self.memory.get_context(
                        "last_command",
                        ""
                    ),

                "recent_history":
                    recent_history_text
            }

            print()
            print(
                "CONTEXTO:",
                context
            )

            try:

                t_brain = time.time()

                result = self.brain.think(
                    text,
                    context
                )

                print(f"⏱ CEREBRO (Ollama): {time.time() - t_brain:.2f}s")

            except Exception as error:

                print(
                    "ERROR BRAIN:",
                    error
                )

                result = {
                    "intent": "UNKNOWN",
                    "target": "",
                    "confidence": 0.0
                }

        if not isinstance(result, dict):

            result = {
                "intent": "UNKNOWN",
                "target": "",
                "confidence": 0.0
            }

        intent = str(
            result.get(
                "intent",
                "UNKNOWN"
            )
        ).upper().strip()

        target = str(
            result.get(
                "target",
                ""
            )
        ).strip()

        try:

            confidence = float(
                result.get(
                    "confidence",
                    0
                )
            )

        except Exception:

            confidence = 0.0

        print()
        print(
            "INTENCION:",
            intent
        )

        print(
            "OBJETIVO:",
            target
        )

        print(
            "CONFIANZA:",
            confidence
        )

        self._update_window(
            intent=intent,
            target=target
        )

        # =====================================================
        # SEGURIDAD
        # =====================================================

        if (
            intent == "UNKNOWN"
            or confidence < 0.45
        ):

            # Si el intent es UNKNOWN (no "una acción conocida pero con
            # poca confianza"), y el usuario lo pidió de forma EXPLÍCITA
            # ("aprende a...", "enséñame a..."), se ofrece generar código
            # nuevo en vez de simplemente rendirse. Ofrecerlo ante
            # CUALQUIER comando no reconocido sería molesto: un error de
            # transcripción de voz también da UNKNOWN. Todavía no se
            # genera ni ejecuta nada: solo queda pendiente, igual que
            # "desinstala X" o "borra la carpeta X". Ver
            # handle_local_command() para los dos pasos de confirmación.
            skill_description = (
                self._extract_skill_description(text)
                if intent == "UNKNOWN" else None
            )

            if skill_description:

                response = (
                    "¿Quieres que intente aprenderlo generando código "
                    "automáticamente? Puede tardar un momento."
                )

                self.pending_confirmation = {
                    "type": "learn_offer",
                    "description": skill_description,
                }

            else:

                response = (
                    "No estoy suficientemente "
                    "segura de lo que quieres."
                )

            print()
            print(
                "ECO:",
                response
            )

            self._update_window(
                response=response,
                status="● ECO LISTA"
            )

            try:

                self.speaker.speak(
                    response
                )

            except Exception:
                pass

            return

        # =====================================================
        # ROUTER
        # =====================================================

        print()
        print(
            "ROUTER:",
            intent
        )

        print(
            "TARGET:",
            target
        )

        try:

            # NOTA: se pasa "text" (el comando original) para que
            # Router.detect_direct_command() pueda reconocer órdenes
            # directas de sistema (apagar, reiniciar, suspender,
            # bloquear, cerrar sesión, cancelar apagado) sin depender
            # de que el cerebro las haya clasificado bien.
            t_router = time.time()

            response = self.router.execute(
                result,
                text
            )

            # Las respuestas factuales se convierten en conocimiento
            # local para no depender siempre de Ollama ni de internet.
            if intent == "WEB_SEARCH" and response:
                try:
                    self.learning_brain.teach_knowledge(text, response)
                    print("CONOCIMIENTO APRENDIDO:", text)
                except Exception as error:
                    print("ERROR GUARDANDO CONOCIMIENTO:", error)

            print(f"⏱ ROUTER: {time.time() - t_router:.2f}s | TOTAL: {time.time() - t0:.2f}s")

            if response:

                print()
                print(
                    "ECO:",
                    response
                )

                self._update_window(
                    response=response,
                    status="● ECO LISTA"
                )

                try:

                    self.speaker.speak(
                        response
                    )

                except Exception:
                    pass

        except Exception as error:

            print()
            print(
                "ERROR ROUTER:",
                error
            )

            return

        # =====================================================
        # MEMORIA
        # =====================================================

        try:

            self.memory.set_context(
                "last_target",
                target
            )

            self.memory.set_context(
                "last_intent",
                intent
            )

            self.memory.set_context(
                "last_command",
                text
            )

            # Guarda el intercambio real (lo que preguntaste + lo que
            # respondió Eco) para que futuras preguntas de
            # seguimiento puedan usarlo como contexto.
            self.memory.save(
                text,
                response or ""
            )

        except Exception as error:

            print(
                "ERROR MEMORIA:",
                error
            )

    # =========================================================
    # APRENDIZAJE
    # =========================================================

    def _handle_learning(self, text):

        print()
        print(
            "MODO APRENDIZAJE"
        )

        try:

            parsed = (
                self.learning_brain
                .parse_learning_request(text)
            )

        except Exception as error:

            print(
                "ERROR ANALIZANDO APRENDIZAJE:",
                error
            )

            return

        if not parsed:
            return

        phrase = parsed.get(
            "phrase",
            ""
        )

        action = parsed.get(
            "action",
            ""
        )

        if not phrase or not action:
            return

        print(
            "FRASE:",
            phrase
        )

        print(
            "ACCION:",
            action
        )

        try:

            result = self.brain.think(
                action
            )

        except Exception as error:

            print(
                "ERROR INTERPRETANDO ACCION:",
                error
            )

            return

        if not isinstance(result, dict):
            return

        intent = result.get(
            "intent",
            "UNKNOWN"
        )

        target = result.get(
            "target",
            ""
        )

        confidence = result.get(
            "confidence",
            0
        )

        if intent == "UNKNOWN":
            return

        if confidence < 0.60:
            return

        try:

            success = self.learning_brain.teach(
                phrase=phrase,
                intent=intent,
                target=target,
                confidence=confidence
            )

        except Exception as error:

            print(
                "ERROR GUARDANDO APRENDIZAJE:",
                error
            )

            return

        if success:

            print()
            print(
                "APRENDIZAJE GUARDADO"
            )

            try:

                self.speaker.speak(
                    "Entendido. He aprendido esa orden."
                )

            except Exception:
                pass
