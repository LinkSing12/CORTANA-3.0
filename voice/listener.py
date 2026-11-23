import speech_recognition as sr
import re
import time

# Anulación de ruido propia (más allá del umbral de energía del
# micrófono). Es opcional: si estas dos librerías no están instaladas,
# Eco sigue funcionando exactamente igual que antes, solo sin
# este paso extra de limpieza de audio.
try:
    import numpy as np
    import noisereduce as nr
except ImportError:
    np = None
    nr = None

# Resta del micrófono la música que suena en la PC. También opcional:
# sin numpy/soundcard, Eco usa el micrófono normal.
try:
    from voice.echo_canceller import EchoCanceller, EchoCancelledMicrophone
except ImportError:
    EchoCanceller = None


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
    # la frase completa reconocida, ANTES de que Eco intente
    # interpretarla. Están limitadas al contexto "en X" para no
    # arruinar frases legítimas (ej. "toca queen" para el grupo
    # de rock sigue funcionando normal; solo se corrige cuando
    # aparece como "en queens/kings/etc").
    #
    # Si notas otra palabra que Google confunde seguido, agrega
    # una línea aquí con el mismo formato.
    #
    # "windows" por "winamp" es otro caso confirmado (fonéticamente
    # se parecen: "win-" al principio). Se corrige SOLO en los dos
    # contextos donde "windows" no tiene sentido como orden real
    # (nadie dice "reproduce X en Windows" ni "abre Windows" como
    # comando de voz), para no arruinar otras frases legítimas.
    # =========================================================
    PHONETIC_CORRECTIONS = [
        (r"\ben\s+queens?\b", "en winamp"),
        (r"\ben\s+kings?\b", "en winamp"),
        (r"\ben\s+wi\s*namp\b", "en winamp"),
        (r"\bwi\s*namp\b", "winamp"),
        (
            r"\b(reproduce|reproducir|pon|poner|toca|tocar|play)"
            r"\s+(.+?)\s+en\s+windows\b",
            r"\1 \2 en winamp",
        ),
        (r"\b(abre|abrir|[aá]breme)\s+windows\b", r"\1 winamp"),
    ]

    def __init__(self):

        self.recognizer = sr.Recognizer()

        # =====================================================
        # AJUSTES DEL RECONOCIMIENTO
        # =====================================================

        self.recognizer.energy_threshold = 300

        # El umbral se recalcula con el ruido mientras Eco espera. Antes
        # saltaba de forma errática (150 -> 5554); ahora se limita entre
        # MIN_ENERGY_THRESHOLD y MAX_ENERGY_THRESHOLD antes de cada escucha.
        self.recognizer.dynamic_energy_threshold = True

        self.recognizer.dynamic_energy_adjustment_damping = 0.15

        self.recognizer.dynamic_energy_ratio = 1.5

        # Las órdenes cortas ("pausa", "siguiente") se cierran tras
        # 0.35 s de silencio, para que se ejecuten casi de inmediato.
        self.recognizer.pause_threshold = 0.35

        self.recognizer.phrase_threshold = 0.2

        self.recognizer.non_speaking_duration = 0.3

        # Piso mínimo del umbral de energía. Si la calibración
        # automática da un valor absurdamente bajo (ej. 83, como se
        # vio en pruebas reales), CUALQUIER ruido de fondo se
        # interpreta como "sigues hablando" y nunca detecta silencio.
        self.MIN_ENERGY_THRESHOLD = 80

        # Tope del umbral. Antes era 180 y fijo, pero con música sonando
        # el micrófono de la cámara recibe ~800 aun después de restar la
        # música: con un umbral menor que el ruido, Eco creía que nunca
        # dejabas de hablar, grababa 15 s de canción y el "eco" se perdía.
        # Ahora el umbral sigue al ruido (ver listen) y este tope solo
        # evita que se dispare a valores absurdos.
        self.MAX_ENERGY_THRESHOLD = 2500

        # La reducción espectral se aplicaba después de grabar cada frase.
        # Para órdenes cortas añade demora y puede adelgazar demasiado la
        # voz de una cámara. La cancelación de eco sigue activa; esta capa
        # pesada queda apagada hasta que se necesite específicamente.
        self.noise_reduction_enabled = False

        # =====================================================
        # MICRÓFONO
        # =====================================================

        self.echo_canceller = EchoCanceller() if EchoCanceller else None
        self._use_echo_canceller = bool(
            self.echo_canceller and self.echo_canceller.start()
        )
        self.microphone = None
        self._microphone_device_index = None
        self._microphone_device_name = None

        # El dispositivo predeterminado puede cambiar mientras Eco está
        # abierto (por ejemplo, de la cámara a los audífonos Razer). Se
        # consulta antes de cada escucha y se recrea el stream si Windows
        # eligió otro, en vez de quedar amarrada al que había al iniciar.
        self._refresh_microphone(force=True)

        # =====================================================
        # EVITAR REPETICIONES
        # =====================================================

        self.last_text = ""

        self.last_time = 0

        # Momento en que empezó la última frase. El bucle de voz lo
        # usa para saber si llegó dentro de la ventana de 30s.
        self.last_phrase_started = None

        # =====================================================
        # CALIBRACIÓN
        # =====================================================

        self._calibrate_microphone()

    def _get_windows_default_microphone(self):
        """Devuelve el índice y nombre del dispositivo predeterminado."""
        audio = None
        try:
            audio = sr.Microphone.get_pyaudio().PyAudio()
            info = audio.get_default_input_device_info()
            return info["index"], str(info.get("name", "Desconocido"))
        except Exception as error:
            print("⚠️ No pude consultar el micrófono de Windows:", error)
            return None, None
        finally:
            if audio is not None:
                audio.terminate()

    def _refresh_microphone(self, force=False):
        """Reconecta Eco al dispositivo que Windows marque como entrada."""
        device_index, device_name = self._get_windows_default_microphone()

        if not force and device_index == self._microphone_device_index:
            return False

        try:
            if self._use_echo_canceller:
                microphone = EchoCancelledMicrophone(
                    self.echo_canceller,
                    device_index=device_index,
                )
            else:
                microphone = sr.Microphone(device_index=device_index)
        except Exception as error:
            print("⚠️ No pude abrir el micrófono seleccionado:", error)
            return False

        self.microphone = microphone
        self._microphone_device_index = device_index
        self._microphone_device_name = device_name

        print(f"🎙️ DISPOSITIVO DE WINDOWS: {device_name}")
        return True

    def _calibrate_microphone(self):
        """Calibra el umbral para el dispositivo de entrada actual."""
        print()
        print("🎙️ CALIBRANDO MICRÓFONO...")

        try:
            with self.microphone as source:
                # 2 segundos en vez de 1: calibración más estable
                # frente a ruido de fondo (ventilador, eco, etc.)
                self.recognizer.adjust_for_ambient_noise(source, duration=2)

            calibrated_threshold = self.recognizer.energy_threshold
            safe_threshold = min(
                max(calibrated_threshold, self.MIN_ENERGY_THRESHOLD),
                self.MAX_ENERGY_THRESHOLD,
            )

            if safe_threshold != calibrated_threshold:
                print(
                    f"⚠️ Umbral calibrado en {calibrated_threshold:.0f}. "
                    f"Se ajusta a {safe_threshold:.0f} para voz normal."
                )
                self.recognizer.energy_threshold = safe_threshold

            # El umbral se sigue ajustando al ruido mientras Eco espera
            # que hables (sube si pones música, baja si la quitas); en
            # cada escucha se mantiene entre el piso y el tope.
            self.recognizer.dynamic_energy_threshold = True
            print(
                f"✅ MICRÓFONO LISTO (umbral de energía inicial: "
                f"{self.recognizer.energy_threshold:.0f})"
            )
        except Exception as error:
            print("⚠️ No se pudo calibrar el micrófono:", error)

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
    # ANULACIÓN DE RUIDO PROPIA
    #
    # El umbral de energía (arriba, en __init__) solo decide CUÁNDO
    # empezaste y terminaste de hablar; no limpia el ruido de fondo
    # constante (ventilador, eco de las bocinas, etc.) que queda
    # DENTRO de lo ya grabado. Esto aplica reducción de ruido
    # espectral sobre ese audio, antes de mandarlo a reconocer.
    #
    # stationary=True asume que el ruido de fondo es más o menos
    # constante durante toda la frase (el caso típico de un
    # ventilador o el zumbido de la habitación), y lo estima del
    # propio audio capturado, sin necesitar una muestra de ruido
    # aparte.
    # =========================================================

    def _reduce_noise(self, audio):

        if np is None or nr is None:
            return audio

        try:

            samples = np.frombuffer(
                audio.get_raw_data(), dtype=np.int16
            ).astype(np.float32)

            cleaned = nr.reduce_noise(
                y=samples,
                sr=audio.sample_rate,
                stationary=True,
            )

            cleaned = np.clip(
                cleaned, -32768, 32767
            ).astype(np.int16)

            return sr.AudioData(
                cleaned.tobytes(),
                audio.sample_rate,
                audio.sample_width,
            )

        except Exception as error:

            print(
                "⚠️ No se pudo aplicar la anulación de ruido:",
                error
            )

            return audio

    # =========================================================
    # ESCUCHAR
    # =========================================================

    def listen(self):

        try:

            # Windows puede cambiar de entrada mientras Eco está
            # esperando la siguiente orden. El stream anterior ya no se
            # reutiliza: al detectar el nuevo predeterminado, se crea uno
            # nuevo y se calibra antes de escuchar.
            if self._refresh_microphone():
                print("🔄 CAMBIO DE MICRÓFONO DETECTADO.")
                self._calibrate_microphone()

            self.recognizer.energy_threshold = min(
                max(
                    self.recognizer.energy_threshold,
                    self.MIN_ENERGY_THRESHOLD,
                ),
                self.MAX_ENERGY_THRESHOLD,
            )

            print()
            print("🎙️ ESCUCHANDO...")

            t_listen = time.time()

            with self.microphone as source:

                audio = self.recognizer.listen(
                    source,
                    timeout=None,
                    phrase_time_limit=15
                )

            # Duración real de la frase: el tiempo total desde
            # t_listen también incluye la espera en silencio.
            phrase_seconds = len(audio.frame_data) / (
                audio.sample_rate * audio.sample_width
            )

            self.last_phrase_started = time.time() - phrase_seconds

            print(
                f"🧠 PROCESANDO... (grabó {phrase_seconds:.1f}s, "
                f"esperó {time.time() - t_listen - phrase_seconds:.1f}s, "
                f"umbral actual: {self.recognizer.energy_threshold:.0f})"
            )

            if phrase_seconds >= 14.5:
                print(
                    "⚠️ Se grabó hasta el tope de 15s. Esto casi "
                    "siempre significa que el umbral de energía está "
                    "mal calibrado para el ruido de tu ambiente "
                    "(no detecta el silencio al terminar de hablar)."
                )

            # =================================================
            # ANULACIÓN DE RUIDO PROPIA
            # =================================================

            if self.noise_reduction_enabled:
                t_denoise = time.time()
                audio = self._reduce_noise(audio)
                print(
                    f"🔇 ANULACIÓN DE RUIDO: "
                    f"{time.time() - t_denoise:.2f}s"
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
