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

from core.brain import Brain
from core.router import Router
from core.learning_brain import LearningBrain
from core.conversation import Conversation
from core.updater import Updater


class Cortana:

    def __init__(self):

        self.name = "Cortana"

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

        # AJUSTA esta carpeta a donde tengas tu música real si no
        # está en la carpeta "Música" por defecto de Windows.
        self.winamp = WinampController()

        self.updater = Updater()

        # Guarda la acción destructiva que está esperando confirmación
        # (flujo de dos turnos: "desinstala X" / "borra la carpeta X"
        # -> Cortana pregunta -> usuario dice "sí" -> se ejecuta).
        # Formato: {"type": "uninstall" | "delete_folder", "target": ...}
        self.pending_confirmation = None

        self.brain = Brain()

        self.router = Router(
            self.windows,
            self.media
        )

        # Interfaz gráfica (window.py). Es opcional: si nadie
        # llama a set_interface(), Cortana sigue funcionando
        # 100% por consola/voz igual que antes.
        self.window = None

    # =========================================================
    # CONECTAR INTERFAZ GRAFICA (window.py)
    # =========================================================

    def set_interface(self, window):

        self.window = window

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
    # INICIAR CORTANA
    # =========================================================

    def start(self):

        print()
        print("=" * 55)
        print("                 CORTANA 4.0")
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
                print("CORTANA CERRADA.")
                break

            if not text:
                continue

            if self.is_exit_command(
                text.lower()
            ):

                print(
                    "CORTANA: Hasta luego."
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

            command = self.remove_wake_word(
                text
            )

            if not command:
                continue

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
                    "CORTANA CERRADA (por voz)."
                )

                os._exit(0)

            self.respond(command)

    # =========================================================
    # PALABRA DE ACTIVACIÓN
    # =========================================================

    def remove_wake_word(self, text):

        text = text.strip()
        lower = text.lower()

        wake_words = [
            "cortana",
            "cortana.",
            "cortana,",
            "cortana:"
        ]

        for word in wake_words:

            if lower.startswith(word):

                text = text[
                    len(word):
                ].strip()

                break

        return text

    # =========================================================
    # COMANDOS PARA CERRAR CORTANA
    # =========================================================

    def is_exit_command(self, text):

        commands = [
            "salir",
            "cerrar cortana",
            "apaga cortana",
            "terminar",
            "termina",
            "apagar asistente",
            "apaga el asistente"
        ]

        return text in commands

    # =========================================================
    # COMANDOS LOCALES
    # =========================================================

    # =========================================================
    # WINAMP: DETECCIÓN DE COMANDOS
    # =========================================================

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
            rf"^{FILLER}abre\s+winamp\s+(?:y\s+)?{VERB}\s+(.+)$",
            # "reproduce X en winamp"
            rf"^{FILLER}{VERB}\s+(.+?)\s+en\s+winamp$",
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

        text = text.strip()

        number_match = re.match(
            r"^(?:el\s+|la\s+)?(?:canci[oó]n\s+)?(?:n[uú]mero\s+)?(\d+)$",
            text
        )

        if number_match:
            return ("number", number_match.group(1))

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

        command = command.lower().strip()

        # =====================================================
        # CONFIRMACIÓN DE DESINSTALACIÓN PENDIENTE
        # Si Cortana ya preguntó "¿quieres desinstalar X?", esta
        # respuesta corta confirma (o cancela) esa acción específica.
        # Solo aplica si hay algo realmente pendiente, para no
        # interceptar un "sí" normal en otro contexto.
        # =====================================================

        if self.pending_confirmation:

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
                    else:
                        response = "No supe qué confirmar."
                        response_intent = "UNKNOWN"
                except Exception as error:
                    print("ERROR CONFIRMANDO ACCIÓN:", error)
                    response = "No pude completar la acción."
                    response_intent = "UNKNOWN"

                print("CORTANA:", response)

                self._update_window(
                    intent=response_intent,
                    target=pending.get("target", ""),
                    response=response,
                    status="● CORTANA LISTA"
                )

                try:
                    self.speaker.speak(response)
                except Exception:
                    pass

                return True

            if command in cancel_words:

                self.pending_confirmation = None

                response = "Está bien, no hago nada."

                print("CORTANA:", response)

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

                print("CORTANA:", response)

                self._update_window(
                    intent="INSTALL_PROGRAM",
                    target=name,
                    response=response,
                    status="● CORTANA LISTA"
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

                    print("CORTANA:", spoken)

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

                    print("CORTANA:", response)

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

                print("CORTANA:", response)

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

            print("CORTANA:", response)

            self._update_window(
                intent="CREATE_FOLDER",
                target=folder_name,
                response=response,
                status="● CORTANA LISTA"
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

                    print("CORTANA:", spoken)

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

                    print("CORTANA:", response)

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
                        "CORTANA:",
                        response
                    )

                    self._update_window(
                        intent="PLAY_MEDIA",
                        target=str(value),
                        response=response,
                        status="● CORTANA LISTA"
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
                    "CORTANA: Apagando la computadora "
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
                    "CORTANA: Reiniciando la computadora "
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
                    "CORTANA: Apagado cancelado."
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
        # ACTUALIZACIONES
        # =====================================================

        update_commands = [
            "busca actualizaciones",
            "buscar actualizaciones",
            "hay actualizaciones",
            "revisa actualizaciones",
            "actualiza cortana",
            "actualizar cortana",
            "actualízate",
            "actualizate"
        ]

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
                    "CORTANA:",
                    response
                )

                self._update_window(
                    intent="UPDATE",
                    target="",
                    response=response,
                    status="● CORTANA LISTA"
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
                    "CORTANA:",
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
                    "CORTANA:",
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
                    "CORTANA:",
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
                    "CORTANA:",
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
                    "CORTANA:",
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
                    "CORTANA:",
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
                    "CORTANA:",
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
                    "CORTANA:",
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
                    "CORTANA:",
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
                    "CORTANA:",
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
                        "CORTANA:",
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
                        "CORTANA:",
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
                                "CORTANA:",
                                response
                            )

                            self._update_window(
                                intent="PLAY_MEDIA",
                                target=parsed_target[1],
                                response=response,
                                status="● CORTANA LISTA"
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
                            "CORTANA:",
                            response
                        )

                        self._update_window(
                            intent="PLAY_MEDIA",
                            target=query,
                            response=response,
                            status="● CORTANA LISTA"
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
                        "CORTANA:",
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
                        "CORTANA:",
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
                "CORTANA:",
                conversation_response
            )

            self._update_window(
                intent="CONVERSACIÓN",
                target="",
                response=conversation_response,
                status="● CORTANA LISTA"
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

        direct_system_intent = self.router.detect_direct_command(text)

        learned = None

        if direct_system_intent:

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

        if direct_system_intent:

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
                    history_lines.append(f"Cortana: {assistant_line}")

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

            response = (
                "No estoy suficientemente "
                "segura de lo que quieres."
            )

            print()
            print(
                "CORTANA:",
                response
            )

            self._update_window(
                response=response,
                status="● CORTANA LISTA"
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

            print(f"⏱ ROUTER: {time.time() - t_router:.2f}s | TOTAL: {time.time() - t0:.2f}s")

            if response:

                print()
                print(
                    "CORTANA:",
                    response
                )

                self._update_window(
                    response=response,
                    status="● CORTANA LISTA"
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
            # respondió Cortana) para que futuras preguntas de
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