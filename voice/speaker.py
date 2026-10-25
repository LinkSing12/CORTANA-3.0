import os
import re
import sys
import subprocess
import tempfile
import threading
import unicodedata

try:
    import winsound
except ImportError:  # pragma: no cover - no Windows audio backend here
    winsound = None

try:
    import pyttsx3
except ImportError:  # pragma: no cover - optional dependency on non-Windows hosts
    pyttsx3 = None


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


class Speaker:
    """
    Habla con Piper TTS (voz neuronal local, mucho más fluida que las
    voces clásicas de Windows) y, si Piper no está listo todavía
    (falta el paquete o el modelo de voz), usa pyttsx3 como antes —
    para que Eco nunca se quede muda mientras terminas de
    configurar la voz nueva.

    CÓMO ACTIVAR LA VOZ DE PIPER (una sola vez):

    1. pip install piper-tts

    2. Descarga estos DOS archivos (mismo nombre, junto al modelo)
       desde https://huggingface.co/rhasspy/piper-voices/tree/main/es
       Recomendado, en español de España, calidad media:
         es/es_ES/davefx/medium/es_ES-davefx-medium.onnx
         es/es_ES/davefx/medium/es_ES-davefx-medium.onnx.json
       (también hay voces es_MX si prefieres acento latinoamericano)

    3. Guarda los dos archivos en: data/piper_voice/
       (junto a tu carpeta data/ de siempre — créala si no existe)

    Si en algún momento quieres cambiar de voz, solo reemplaza esos
    dos archivos por otro par con el mismo nombre entre sí, y ajusta
    PIPER_MODEL abajo.
    """

    PIPER_MODEL = os.path.join("data", "piper_voice", "es_ES-davefx-medium.onnx")

    def __init__(self):
        self.rate = 170
        self.volume = 1.0
        self._piper_ready = self._check_piper()

        # Opcional: si hay una ventana con carita de robot conectada
        # (ver set_window / interface/window.py), se le avisa justo
        # antes y justo después de hablar, para que la boca se mueva
        # sincronizada con el audio real — no con una estimación.
        self._window = None
        self._quitados = {}

        if not self._piper_ready:
            safe_print(
                "Info: Piper TTS no está listo todavía (falta el paquete o "
                "el modelo en data/piper_voice/) - usando la voz clásica "
                "de Windows mientras tanto. Ver voice/speaker.py para "
                "activarlo."
            )

    def _check_piper(self):
        if not os.path.isfile(self.PIPER_MODEL):
            return False
        if not os.path.isfile(self.PIPER_MODEL + ".json"):
            return False
        try:
            import piper  # noqa: F401
            return True
        except ImportError:
            return False

    def set_window(self, window):
        """
        Conecta la ventana con la carita de robot (ver
        interface/window.py). Opcional: si nunca se llama, Eco
        habla exactamente igual, solo sin mover ninguna boca.
        """
        self._window = window

    def _start_talking(self):
        if self._window:
            try:
                self._window.start_talking()
            except Exception:
                pass

    def _stop_talking(self):
        if self._window:
            try:
                self._window.stop_talking()
            except Exception:
                pass

    # Los recordatorios hablan desde su propio hilo: el candado evita
    # que dos frases suenen encima (pyttsx3 no aguanta dos a la vez).
    _speak_lock = threading.Lock()

    def speak(self, text):
        with self._speak_lock:
            self._speak(text)

    def _speak(self, text):

        safe_print(f"Eco: {text}")
        self._quitados = {}

        # La consola (arriba) muestra el texto TAL CUAL — esto es solo
        # para lo que la voz va a decir. Sin esto, la voz leía cosas
        # como ".exe" ("punto e equis e"), guiones bajos ("rayita
        # abajo") y el "~" de rutas cortas de Windows ("tilde uno"),
        # que nadie quiere escuchar en voz alta.
        text = self._sanitize_for_speech(text)

        if self._quitados:
            detalle = ", ".join(
                f"{c!r} (U+{ord(c):04X} {nombre})"
                for c, nombre in self._quitados.items()
            )
            safe_print(f"VOZ: se quitaron estos símbolos del texto hablado: {detalle}")

        try:
            if self._piper_ready and self._speak_with_piper(text):
                return

            if not self._speak_with_pyttsx3(text):
                safe_print("Info: no hay backend de voz disponible para reproducir el texto.")
        finally:
            self._stop_talking()

    # Símbolos que la voz "lee" en voz alta y que no aportan nada al oírlos
    # (copyright, marcas, viñetas, acentos sueltos, asteriscos de negrita...).
    _SIMBOLOS_A_QUITAR = set(
        "©®™℠℗§¶†‡•‣◦▪▫■□◆◇★☆✓✔✗✘→←↑↓➜➤►◄¦|\\^`´¨˜¯¸ˆ*#<>{}[]=~_"
    )

    _URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
    _CITA = re.compile(r"\[\s*\d+\s*\]")  # marcas de cita tipo [1], [23]
    _EXTENSIONES = re.compile(r"\.(?:exe|lnk|bat|cmd|com)\b", re.IGNORECASE)

    def _sanitize_for_speech(self, text):
        """
        Limpia el texto SOLO para lo que se va a hablar (la consola
        sigue mostrando el original). Sin esto, la voz lee en voz alta
        cosas como "copyright" (©), "tilde" (marcas de acento sueltas o
        "~"), "asterisco" (negritas de Ollama), emojis, direcciones web,
        "rayita abajo", ".exe", etc.

        Lo que se quita queda registrado en self._quitados (con nombre y
        código Unicode) para poder diagnosticar si algo raro se sigue
        oyendo.
        """

        quitados = {}
        text = str(text or "")

        # Tildes "descompuestas": muchos textos de la web guardan la "ñ"
        # como una "n" + una marca de tilde SUELTA. La voz lee esa marca
        # ("tilde"). Normalizar a la forma compuesta (ñ, á, é...) lo arregla.
        text = unicodedata.normalize("NFC", text)

        # Direcciones web: leerlas letra por letra es insoportable.
        text = self._URL.sub("el enlace de la pantalla", text)

        # Marcas de cita de Wikipedia: [1], [23]
        text = self._CITA.sub("", text)

        # Viñetas al inicio de línea ("- algo", "• algo").
        text = re.sub(r"(?m)^\s*[-–—•*]\s+", "", text)

        text = text.replace("&", " y ")

        # Extensiones de archivo: que no diga "punto e equis e".
        text = self._EXTENSIONES.sub("", text)

        # Puntos suspensivos: un solo punto.
        text = re.sub(r"\.{2,}|…", ".", text)

        limpio = []
        for caracter in text:
            if caracter.isspace():
                limpio.append(" ")
                continue

            categoria = unicodedata.category(caracter)

            quitar = (
                caracter in self._SIMBOLOS_A_QUITAR
                # marcas combinables sueltas (tildes/acentos sin letra),
                # caracteres invisibles de formato y de control
                or categoria in ("Mn", "Mc", "Me", "Cf", "Cc", "Cs", "Co")
                # emojis y símbolos varios (pero se conserva el "°" de
                # "25 °C"); las monedas y el "%" se dejan, la voz los
                # dice bien ("dólares", "por ciento")
                or (categoria in ("So", "Sk") and caracter != "°")
            )

            if quitar:
                quitados[caracter] = unicodedata.name(caracter, "sin nombre")
                limpio.append(" ")
            else:
                limpio.append(caracter)

        text = "".join(limpio)
        text = re.sub(r"\s+([,.;:!?])", r"\1", text)   # "Wikipedia ," -> "Wikipedia,"
        text = re.sub(r"\s+", " ", text).strip()

        self._quitados = quitados
        return text

    # =========================================================
    # PIPER TTS (voz local neuronal)
    # =========================================================

    def _speak_with_piper(self, text):
        wav_path = None
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".wav", delete=False
            ) as tmp:
                wav_path = tmp.name

            if not self._run_piper(text, wav_path):
                return False

            if not os.path.isfile(wav_path) or os.path.getsize(wav_path) == 0:
                return False

            # Recién AQUÍ arranca el sonido de verdad — generar el
            # audio con Piper (arriba) toma su tiempo, y si la boca
            # empezaba a moverse antes de esto, se adelantaba al
            # sonido en vez de ir junto con él.
            if winsound is None:
                safe_print("Info: winsound no está disponible en este sistema; se omite la reproducción de audio con Piper.")
                return False

            self._start_talking()
            winsound.PlaySound(wav_path, winsound.SND_FILENAME)
            return True

        except Exception as error:
            safe_print("ERROR HABLANDO CON PIPER:", error)
            return False

        finally:
            if wav_path:
                try:
                    os.remove(wav_path)
                except Exception:
                    pass

    def _run_piper(self, text, wav_path):
        """
        Intenta primero el comando "piper" (el que queda instalado en
        el PATH tras "pip install piper-tts"); si no se encuentra
        (común cuando el entorno virtual no está en el PATH), cae a
        invocar el módulo directamente con el mismo Python que está
        corriendo Eco.
        """
        commands = [
            ["piper", "--model", self.PIPER_MODEL, "--output_file", wav_path],
            [
                sys.executable, "-m", "piper",
                "--model", self.PIPER_MODEL, "--output_file", wav_path,
            ],
        ]

        last_error = None

        for command in commands:
            try:
                result = subprocess.run(
                    command,
                    input=text,
                    capture_output=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=30,
                )
                if result.returncode == 0:
                    return True
                last_error = result.stderr
            except FileNotFoundError:
                continue
            except Exception as error:
                last_error = str(error)

        safe_print("ERROR PIPER:", last_error)
        return False

    # =========================================================
    # RESPALDO: voz clásica de Windows (pyttsx3)
    # =========================================================

    def _speak_with_pyttsx3(self, text):
        if pyttsx3 is None:
            return False

        try:
            engine = pyttsx3.init()

            engine.setProperty("rate", self.rate)
            engine.setProperty("volume", self.volume)

            engine.say(text)
            # pyttsx3.init() y setProperty() de arriba también toman
            # un poco de tiempo — recién acá empieza a sonar de verdad.
            self._start_talking()
            engine.runAndWait()

            engine.stop()
            return True
        except Exception as error:
            safe_print("ERROR HABLANDO CON PYTTSX3:", error)
            return False