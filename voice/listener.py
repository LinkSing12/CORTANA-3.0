import speech_recognition as sr
import re
import time


class Listener:

    # =========================================================
    # CORRECCIONES FONÉTICAS
    #
    # Google Speech (en español) no conoce nombres propios poco
    # comunes como "Winamp" y "alucina" la palabra que más se le
    # parece por sonido. Confirmado en pruebas reales:
    #   "en winamp" -> se transcribió como "en queens"
    #
    # Cada entrada es (patrón regex, reemplazo). Se aplican sobre
    # la frase completa reconocida, ANTES de que Cortana intente
    # interpretarla. Están limitadas al contexto "en X" para no
    # arruinar frases legítimas (ej. "toca queen" para el grupo
    # de rock sigue funcionando normal; solo se corrige cuando
    # aparece como "en queens/kings/etc").
    #
    # Si notas otra palabra que Google confunde seguido, agrega
    # una línea aquí con el mismo formato.
    # =========================================================
    PHONETIC_CORRECTIONS = [
        (r"\ben\s+queens?\b", "en winamp"),
        (r"\ben\s+kings?\b", "en winamp"),
        (r"\ben\s+wi\s*namp\b", "en winamp"),
        (r"\bwi\s*namp\b", "winamp"),
    ]

    def __init__(self):

        self.recognizer = sr.Recognizer()

        # =====================================================
        # AJUSTES DEL RECONOCIMIENTO
        # =====================================================

        self.recognizer.energy_threshold = 300

        # IMPORTANTE: dynamic_energy_threshold en True hace que el
        # umbral se siga recalculando DURANTE toda la sesión, no solo
        # al inicio. Si Cortana habla por las bocinas y el micrófono
        # capta ese sonido, o hay ruido variable (ventilador, etc.),
        # el umbral puede saltar de forma errática (visto en pruebas
        # reales: 150 -> 83 -> 2333 -> 5554 entre intentos), causando
        # tanto cortes prematuros como que se quede "escuchando" de
        # más. Por eso se calibra UNA VEZ al inicio y luego se
        # CONGELA (ver más abajo, tras adjust_for_ambient_noise).
        self.recognizer.dynamic_energy_threshold = True

        self.recognizer.dynamic_energy_adjustment_damping = 0.15

        self.recognizer.dynamic_energy_ratio = 1.5

        # pause_threshold: segundos de silencio para considerar
        # que terminaste de hablar. 0.8 es un punto medio: ni corta
        # demasiado rápido en pausas naturales al hablar, ni se queda
        # esperando mucho tiempo tras terminar.
        self.recognizer.pause_threshold = 1.0

        self.recognizer.phrase_threshold = 0.3

        self.recognizer.non_speaking_duration = 0.5

        # Piso mínimo del umbral de energía. Si la calibración
        # automática da un valor absurdamente bajo (ej. 83, como se
        # vio en pruebas reales), CUALQUIER ruido de fondo se
        # interpreta como "sigues hablando" y nunca detecta silencio.
        self.MIN_ENERGY_THRESHOLD = 250

        # =====================================================
        # MICRÓFONO
        # =====================================================

        self.microphone = sr.Microphone()

        # =====================================================
        # EVITAR REPETICIONES
        # =====================================================

        self.last_text = ""

        self.last_time = 0

        # =====================================================
        # CALIBRACIÓN
        # =====================================================

        print()
        print("🎙️ CALIBRANDO MICRÓFONO...")

        try:

            with self.microphone as source:

                # 2 segundos en vez de 1: calibración más estable
                # frente a ruido de fondo (ventilador, eco, etc.)
                self.recognizer.adjust_for_ambient_noise(
                    source,
                    duration=2
                )

            if self.recognizer.energy_threshold < self.MIN_ENERGY_THRESHOLD:

                print(
                    f"⚠️ Calibró un umbral muy bajo "
                    f"({self.recognizer.energy_threshold:.0f}). "
                    f"Se ajusta al mínimo seguro: {self.MIN_ENERGY_THRESHOLD}."
                )

                self.recognizer.energy_threshold = self.MIN_ENERGY_THRESHOLD

            # CONGELAR el umbral: ya no se recalcula solo durante la
            # sesión. Esto es lo que elimina el comportamiento errático.
            self.recognizer.dynamic_energy_threshold = False

            print(
                f"✅ MICRÓFONO LISTO (umbral de energía fijo: "
                f"{self.recognizer.energy_threshold:.0f})"
            )

        except Exception as error:

            print(
                "⚠️ No se pudo calibrar el micrófono:",
                error
            )

    # =========================================================
    # APLICAR CORRECCIONES FONÉTICAS
    # =========================================================

    def _apply_phonetic_corrections(self, text):

        if not text:
            return text

        corrected = text

        for pattern, replacement in self.PHONETIC_CORRECTIONS:

            corrected = re.sub(
                pattern,
                replacement,
                corrected,
                flags=re.IGNORECASE
            )

        if corrected != text:

            print(
                f"🔧 CORRECCIÓN FONÉTICA: '{text}' -> '{corrected}'"
            )

        return corrected

    # =========================================================
    # ESCUCHAR
    # =========================================================

    def listen(self):

        try:

            print()
            print("🎙️ ESCUCHANDO...")

            t_listen = time.time()

            with self.microphone as source:

                audio = self.recognizer.listen(
                    source,
                    timeout=None,
                    phrase_time_limit=15
                )

            elapsed = time.time() - t_listen

            print(
                f"🧠 PROCESANDO... (grabó {elapsed:.1f}s, "
                f"umbral actual: {self.recognizer.energy_threshold:.0f})"
            )

            if elapsed >= 14.5:
                print(
                    "⚠️ Se grabó hasta el tope de 15s. Esto casi "
                    "siempre significa que el umbral de energía está "
                    "mal calibrado para el ruido de tu ambiente "
                    "(no detecta el silencio al terminar de hablar)."
                )

            # =================================================
            # RECONOCIMIENTO
            # =================================================

            try:

                text = self.recognizer.recognize_google(
                    audio,
                    language="es-DO"
                )

            except sr.UnknownValueError:

                print(
                    "❌ No entendí lo que dijiste."
                )

                return ""

            except sr.RequestError as error:

                print(
                    "❌ Error del reconocimiento:",
                    error
                )

                return ""

            text = self._apply_phonetic_corrections(text)

            text = text.strip()

            if not text:

                return ""

            # =================================================
            # EVITAR REPETICIÓN
            # =================================================

            now = time.time()

            if (
                text.lower() == self.last_text.lower()
                and
                now - self.last_time < 2
            ):

                print(
                    "⚠️ Ignorando repetición."
                )

                return ""

            self.last_text = text

            self.last_time = now

            print()
            print(
                "🎤 RECONOCIDO:",
                text
            )

            return text

        except sr.WaitTimeoutError:

            return ""

        except KeyboardInterrupt:

            raise

        except Exception as error:

            print()
            print(
                "❌ Error del micrófono:",
                error
            )

            return ""
