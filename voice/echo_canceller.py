"""
Quita del micrófono la música que está sonando en la PC.

Eco escucha también lo que sale por los altavoces ("loopback"), así sabe
exactamente qué música hay, y un filtro adaptativo aprende cómo llega esa
música al micrófono y la resta. Lo que queda es, sobre todo, tu voz.

Es opcional: si falta el paquete "soundcard" o no se puede capturar el
audio de salida, Eco escucha el micrófono normal, sin este paso.

Limitación: reduce la música, no la borra del todo. Funciona mejor con el
volumen moderado, porque unos altavoces saturados suenan distinto de lo
que la PC les manda y esa parte no se puede restar.
"""

import threading
import warnings
from collections import deque

import numpy as np
import speech_recognition as sr

try:
    import soundcard
except Exception:  # en algunos Windows falla al importar, no solo si falta
    soundcard = None


SAMPLE_RATE = 16000
BLOCK = 512             # 32 ms a 16 kHz
PARTITIONS = 16         # 16 bloques = ~0.5 s de retardo/eco de la habitación
STEP = 0.5
MAX_QUEUE_SECONDS = 1
SILENCE_RMS = 1e-4


class EchoCanceller:

    def __init__(self):
        self._queue = deque()
        self._queued = 0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self.available = False

        bins = BLOCK + 1
        self._weights = np.zeros((PARTITIONS, bins), dtype=np.complex128)
        self._spectra = np.zeros((PARTITIONS, bins), dtype=np.complex128)
        self._power = np.zeros(bins)
        self._previous = np.zeros(BLOCK)
        self._reduction = 0.0
        self._usual_error = 0.0
        self._frozen = 0

    # =========================================================
    # CAPTURA DE LO QUE SUENA EN LA PC
    # =========================================================

    def start(self):
        if soundcard is None:
            print("Info: falta 'soundcard'; Eco no podrá restar la música.")
            return False

        self._thread = threading.Thread(target=self._capture, daemon=True)
        self._thread.start()
        self.available = True
        return True

    def stop(self):
        self._stop.set()

    def _capture(self):
        # Avisa de cada microcorte al capturar; no afecta al filtro.
        warnings.filterwarnings(
            "ignore", category=soundcard.SoundcardRuntimeWarning
        )

        try:
            speaker = soundcard.default_speaker()
            loopback = soundcard.get_microphone(
                str(speaker.name), include_loopback=True
            )
            with loopback.recorder(
                samplerate=SAMPLE_RATE, channels=1, blocksize=BLOCK
            ) as recorder:
                while not self._stop.is_set():
                    data = recorder.record(numframes=BLOCK)
                    self._push(np.asarray(data, dtype=np.float64).reshape(-1))
        except Exception as error:
            self.available = False
            print("⚠️ No pude capturar el audio de la PC:", error)

    def _push(self, samples):
        with self._lock:
            self._queue.append(samples)
            self._queued += len(samples)
            while self._queued > SAMPLE_RATE * MAX_QUEUE_SECONDS:
                self._queued -= len(self._queue.popleft())

    def _pop_block(self):
        """
        Siguiente bloque de referencia. Si se acumuló de más (los relojes
        del micrófono y la tarjeta de sonido nunca van iguales) se
        descartan los viejos; si no llegó nada, es silencio.
        """
        with self._lock:
            while self._queued > BLOCK * 3:
                self._queued -= len(self._queue.popleft())

            block = np.zeros(BLOCK)
            filled = 0
            while filled < BLOCK and self._queue:
                chunk = self._queue.popleft()
                take = min(BLOCK - filled, len(chunk))
                block[filled:filled + take] = chunk[:take]
                filled += take
                if take < len(chunk):
                    self._queue.appendleft(chunk[take:])
                self._queued -= take

        return block

    # =========================================================
    # RESTAR LA MÚSICA DE UN BLOQUE DEL MICRÓFONO
    # =========================================================

    def process(self, data):
        if not self.available or len(data) != BLOCK * 2:
            return data

        mic = np.frombuffer(data, dtype=np.int16).astype(np.float64) / 32768.0
        reference = self._pop_block()
        cleaned = self.cancel(mic, reference)
        return (np.clip(cleaned, -1, 1) * 32767).astype(np.int16).tobytes()

    def cancel(self, mic, reference):
        spectrum = np.fft.rfft(np.concatenate((self._previous, reference)))
        self._previous = reference

        self._spectra = np.roll(self._spectra, 1, axis=0)
        self._spectra[0] = spectrum

        if not np.any(self._spectra):
            return mic

        estimate = np.fft.irfft(
            np.sum(self._weights * self._spectra, axis=0)
        )[BLOCK:]
        error = mic - estimate

        music_playing = np.sqrt(np.mean(reference ** 2)) > SILENCE_RMS
        if music_playing and not self._is_talking(mic, error):
            self._adapt(spectrum, error)

        return error

    def _is_talking(self, mic, error):
        """
        Si lo que queda tras restar sube de golpe respecto a lo normal,
        es que estás hablando: aprender en ese momento lo desajustaría.
        Tras 5 s sigue aprendiendo por si lo que cambió fue la posición
        de los altavoces o del micrófono.
        """
        mic_power = np.mean(mic ** 2) + 1e-12
        error_power = np.mean(error ** 2) + 1e-12
        ratio = min(error_power / mic_power, 1.0)

        talking = (
            self._reduction > 3
            and error_power > 3 * self._usual_error
            and self._frozen < 150
        )

        if talking:
            self._frozen += 1
            return True

        self._frozen = 0
        self._usual_error = 0.95 * self._usual_error + 0.05 * error_power
        self._reduction = 0.98 * self._reduction + 0.02 * (
            -10 * np.log10(ratio)
        )
        return False

    def _adapt(self, spectrum, error):
        self._power = 0.9 * self._power + 0.1 * np.abs(spectrum) ** 2

        error_spectrum = np.fft.rfft(
            np.concatenate((np.zeros(BLOCK), error))
        )
        gradient = (
            STEP * np.conj(self._spectra) * error_spectrum
            / (self._power * PARTITIONS + 1e-9)
        )

        # Sin esto la multiplicación en frecuencia mezclaría bloques.
        constrained = np.fft.irfft(gradient, axis=1)
        constrained[:, BLOCK:] = 0
        self._weights += np.fft.rfft(constrained, axis=1)


class _CleanStream:
    """Se hace pasar por el stream del micrófono, ya sin la música."""

    def __init__(self, stream, canceller):
        self._stream = stream
        self._canceller = canceller

    def read(self, size):
        return self._canceller.process(self._stream.read(size))

    def close(self):
        self._stream.close()


class EchoCancelledMicrophone(sr.Microphone):
    """sr.Microphone normal, pero lo que lee ya viene sin la música."""

    def __init__(self, canceller, **kwargs):
        super().__init__(sample_rate=SAMPLE_RATE, chunk_size=BLOCK, **kwargs)
        self._canceller = canceller

    def __enter__(self):
        source = super().__enter__()
        self.stream = _CleanStream(self.stream, self._canceller)
        return source
